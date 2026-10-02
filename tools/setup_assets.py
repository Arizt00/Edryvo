#!/usr/bin/env python3
"""Fetch pinned visual dependencies from npm into this project.

No npm executable, build pipeline or global package installation is required.
The base editor and CSS pearl remain usable if the network is unavailable.
Package archives are integrity checked and only allowlisted files are extracted.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import io
import json
import shutil
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "web/vendor"
PACKAGES = {"monaco": ("monaco-editor", "0.52.2"), "babylon": ("babylonjs", "8.32.0"), "three": ("three", "0.180.0"), "xterm": ("@xterm/xterm", "5.5.0"), "xterm-fit": ("@xterm/addon-fit", "0.10.0")}
ENTRYPOINTS = {"monaco":"vs/loader.js", "babylon":"babylon.js", "three":"three.core.js", "xterm":"xterm.js", "xterm-fit":"addon-fit.js"}
MAX_DOWNLOAD = 60 * 1024 * 1024


def fetch(url: str, limit: int = MAX_DOWNLOAD) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "LumenStudio-AssetInstaller/0.4"})
    with urllib.request.urlopen(request, timeout=25) as response:
        chunks = []
        total = 0
        while chunk := response.read(128 * 1024):
            total += len(chunk)
            if total > limit:
                raise ValueError("La descarga excede el límite de tamaño.")
            chunks.append(chunk)
        return b"".join(chunks)


def install(kind: str, force=False):
    package, version = PACKAGES[kind]
    target = VENDOR / kind
    marker = target / "lumen-package.json"
    if marker.is_file() and not force:
        data = json.loads(marker.read_text())
        required = target / ENTRYPOINTS[kind]
        if data.get("version") == version and required.is_file():
            print(f"  {package} {version}: ya instalado.", flush=True)
            return
    print(f"  Descargando {package} {version} desde registry.npmjs.org...", flush=True)
    metadata = json.loads(fetch(f"https://registry.npmjs.org/{package}/{version}", 2_000_000))
    if metadata.get("name") != package or metadata.get("version") != version:
        raise ValueError("La identidad del paquete no coincide con la versión fijada.")
    dist = metadata["dist"]
    tarball = dist["tarball"]
    expected_prefix = f"https://registry.npmjs.org/{package}/-/"
    if not tarball.startswith(expected_prefix):
        raise ValueError("El paquete apunta a un origen de descarga no permitido.")
    integrity = dist.get("integrity", "")
    digest_entry = next((part for part in integrity.split() if part.startswith("sha512-")), None)
    if not digest_entry:
        raise ValueError("El registro no devuelve una integridad SHA-512 verificable.")
    raw = fetch(tarball)
    actual = base64.b64encode(hashlib.sha512(raw).digest()).decode()
    if actual != digest_entry.split("-", 1)[1]:
        raise ValueError("La comprobación SHA-512 del archivo descargado ha fallado.")
    VENDOR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".lumen-assets-", dir=VENDOR) as temp:
        staging = Path(temp) / kind
        staging.mkdir()
        total_unpacked = 0
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
            for item in archive.getmembers():
                if not item.isfile():
                    continue
                name = PurePosixPath(item.name)
                if name.is_absolute() or ".." in name.parts:
                    raise ValueError("El archivo contiene una ruta no segura.")
                relative = None
                if kind == "monaco" and item.name.startswith("package/min/vs/"):
                    relative = PurePosixPath("vs") / name.relative_to("package/min/vs")
                if kind == "babylon" and item.name == "package/babylon.js":
                    relative = PurePosixPath("babylon.js")
                if kind == "three" and item.name == "package/build/three.core.js":
                    relative = PurePosixPath("three.core.js")
                if kind == "xterm" and item.name in ("package/lib/xterm.js", "package/css/xterm.css"):
                    relative = PurePosixPath(name.name)
                if kind == "xterm-fit" and item.name == "package/lib/addon-fit.js":
                    relative = PurePosixPath("addon-fit.js")
                if item.name.lower() in ("package/license", "package/license.md", "package/license.txt", "package/thirdpartynotices.txt"):
                    relative = PurePosixPath(name.name)
                if relative is None:
                    continue
                total_unpacked += item.size
                if total_unpacked > 120 * 1024 * 1024 or item.size > 30 * 1024 * 1024:
                    raise ValueError("El contenido extraído supera el límite de tamaño.")
                destination = staging / str(relative)
                destination.parent.mkdir(parents=True, exist_ok=True)
                handle = archive.extractfile(item)
                if handle is None:
                    continue
                with handle, destination.open("wb") as output:
                    shutil.copyfileobj(handle, output)
        required = staging / ENTRYPOINTS[kind]
        if not required.is_file():
            raise ValueError("El paquete no incluye el archivo de inicio esperado.")
        (staging / "lumen-package.json").write_text(json.dumps({"name": package, "version": version, "integrity": integrity, "source": tarball}, indent=2), encoding="utf-8")
        old = VENDOR / (kind + ".previous")
        if old.exists():
            shutil.rmtree(old)
        if target.exists():
            target.rename(old)
        try:
            staging.rename(target)
        except Exception:
            if old.exists() and not target.exists():
                old.rename(target)
            raise
        if old.exists():
            shutil.rmtree(old)
    print(f"  {package}: instalado y verificado.", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Instala Monaco + Babylon + xterm localmente (una vez, con Internet).")
    parser.add_argument("--force", action="store_true", help="Volver a descargar las versiones fijadas")
    parser.add_argument("--only", choices=list(PACKAGES))
    args = parser.parse_args()
    failures = []
    for kind in ([args.only] if args.only else PACKAGES):
        try:
            install(kind, args.force)
        except (OSError, ValueError, KeyError, tarfile.TarError, urllib.error.URLError) as exc:
            failures.append(kind)
            print(f"  No se pudo instalar {kind}: {exc}", file=sys.stderr, flush=True)
    if failures:
        print("\nLumen puede arrancar con su editor base y la esfera CSS. Repite este comando cuando tengas conexión.")
        return 1
    print("\nMonaco, Babylon y xterm están en web/vendor. Desde ahora la interfaz funciona sin CDN ni conexión.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
