"""Bounded workspace access, conflict detection and atomic saves."""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import tempfile
import threading
import time
from pathlib import Path
from .native import NativeCore

MAX_FILE = 2 * 1024 * 1024
EXCLUDED = {".git", ".lumen", "node_modules", "__pycache__", ".venv", "venv", "Library", "Temp", "obj", "bin", "vendor"}


class ConflictError(ValueError):
    pass


class Workspace:
    def __init__(self, root: Path, native: NativeCore):
        root = root.expanduser().resolve()
        if not root.is_dir():
            raise ValueError("La carpeta de proyecto no existe.")
        self.root = root
        self.native = native
        self.lock = threading.RLock()
        self.trusted = False

    def resolve(self, name: str, *, must_exist: bool = True) -> Path:
        if not isinstance(name, str) or "\x00" in name:
            raise ValueError("Ruta no válida.")
        normalized = name.replace("\\", "/")
        path = (self.root / normalized).resolve()
        if not path.is_relative_to(self.root):
            raise PermissionError("La ruta sale del proyecto abierto.")
        # Refuse symbolic-link components, even links that remain inside the root.
        walk = self.root
        for part in Path(normalized).parts:
            walk = walk / part
            if walk.is_symlink():
                raise PermissionError("Los enlaces simbólicos no se abren desde el IDE.")
        if must_exist and not path.exists():
            raise FileNotFoundError("No se encuentra el archivo o la carpeta.")
        return path

    def private_dir(self, child: str) -> Path:
        path = self.resolve(".lumen/" + child, must_exist=False)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def tree(self) -> list[dict]:
        count = [0]
        def visit(path: Path, depth: int) -> list[dict]:
            if depth > 9 or count[0] >= 3000:
                return []
            try:
                preferred = {
                    ".": ["Assets", "Packages", "Settings", "Examples", "README.md"],
                    "Assets": ["Scripts", "Scenes", "Prefabs", "Materials", "Textures", "UI"],
                    "Assets/Scripts": ["TopDownAvatarController.cs", "Player.cs", "Camera.cs"],
                    "Assets/Prefabs": ["Player.prefab", "CameraRig.prefab"],
                    "Settings": ["ProjectSettings.json", "InputSystem.actions"],
                } if (self.root / "Assets/Scripts/TopDownAvatarController.cs").is_file() else {}
                order = preferred.get(path.relative_to(self.root).as_posix(), [])
                children = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), order.index(p.name) if p.name in order else len(order), p.name.lower()))
            except OSError:
                return []
            result = []
            for p in children:
                if count[0] >= 3000:
                    break
                if p.is_symlink() or p.name in EXCLUDED or p.name.startswith(".env"):
                    continue
                count[0] += 1
                item = {"name": p.name, "path": p.relative_to(self.root).as_posix(), "directory": p.is_dir()}
                if p.is_dir():
                    item["children"] = visit(p, depth + 1)
                result.append(item)
            return result
        return visit(self.root, 0)

    def files(self) -> list[str]:
        result = []
        def collect(nodes):
            for n in nodes:
                if n["directory"]:
                    collect(n.get("children", []))
                else:
                    result.append(n["path"])
        collect(self.tree())
        return result

    def read(self, name: str) -> dict:
        path = self.resolve(name)
        if not path.is_file():
            raise ValueError("Selecciona un archivo, no una carpeta.")
        if path.stat().st_size > MAX_FILE:
            raise ValueError("Esta edición admite archivos de texto de hasta 2 MiB.")
        raw = path.read_bytes()
        if b"\x00" in raw:
            raise ValueError("El archivo es binario; no se abrirá como texto.")
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("El archivo no es UTF-8. Conviértelo antes de editarlo.") from exc
        newline = "CRLF" if b"\r\n" in raw else "LF"
        text = text.replace("\r\n", "\n")
        return {"path": path.relative_to(self.root).as_posix(), "content": text,
                "revision": hashlib.sha256(raw).hexdigest(), "newline": newline,
                "bom": raw.startswith(b"\xef\xbb\xbf"), "stats": self.native.stats(text)}

    def save(self, name: str, content: str, revision: str | None, *, create=False, newline="LF", bom=False) -> dict:
        if not isinstance(content, str):
            raise ValueError("El contenido debe ser texto.")
        encoded = content.replace("\r\n", "\n")
        if newline == "CRLF":
            encoded = encoded.replace("\n", "\r\n")
        data = (b"\xef\xbb\xbf" if bom else b"") + encoded.encode("utf-8")
        if len(data) > MAX_FILE:
            raise ValueError("El archivo excede 2 MiB.")
        with self.lock:
            path = self.resolve(name, must_exist=False)
            if path == self.root or path.is_dir():
                raise ValueError("Selecciona un nombre de archivo.")
            previous = None
            if path.exists():
                if create:
                    raise ConflictError("Ya existe un archivo con ese nombre.")
                previous = path.read_bytes()
                current = hashlib.sha256(previous).hexdigest()
                if revision != current:
                    raise ConflictError("El archivo cambió fuera del editor. Recarga antes de guardar para no sobrescribir cambios.")
                backup = self.private_dir("backups") / f"{time.time_ns()}_{hashlib.sha256(name.encode()).hexdigest()[:10]}_{path.name}"
                backup.write_bytes(previous)
            elif not create and revision:
                raise ConflictError("El archivo se eliminó fuera del editor. Usa Nuevo archivo para recrearlo.")
            path.parent.mkdir(parents=True, exist_ok=True)
            # Same-directory temp + replace: failed saves do not truncate the original.
            fd, temp_name = tempfile.mkstemp(prefix=".lumen-save-", dir=str(path.parent))
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                if previous is not None:
                    shutil.copymode(path, temp_name)
                os.replace(temp_name, path)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
            return self.read(name)

    def search(self, query: str, *, content=False, folder='') -> list[dict]:
        if not query or len(query) > 200:
            return []
        results = []
        scope = self.resolve(folder).relative_to(self.root).as_posix() if folder else ''
        if scope == '.': scope = ''
        for name in self.files():
            if scope and not name.startswith(scope + '/'): continue
            if content:
                try:
                    data = self.read(name)
                except (ValueError, OSError):
                    continue
                for number, line in enumerate(data["content"].splitlines(), 1):
                    if query.lower() in line.lower():
                        results.append({"path": name, "line": number, "text": line.strip()[:200]})
                        if len(results) >= 200:
                            return results
            else:
                score = self.native.fuzzy(query, name)
                if score != -1:
                    results.append({"path": name, "score": score})
        if not content:
            results.sort(key=lambda x: (-x["score"], x["path"]))
        return results[:200]

    def check(self) -> str:
        names = self.files()
        byte_count = 0
        lines = 0
        readable = 0
        for name in names:
            try:
                item = self.read(name)
                byte_count += item["stats"]["bytes"]
                lines += item["stats"]["lines"]
                readable += 1
            except (ValueError, OSError):
                continue
        return (f"Workspace indexed: {self.root.name}\n"
                f"  {len(names)} files · {readable} text files · {lines} lines\n"
                f"  {byte_count:,} UTF-8 bytes\n"
                f"  Text engine: {self.native.name}\n"
                "Workspace check completed. This is not a compiler build.\n")
