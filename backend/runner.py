"""Explicit local task execution. This is a command console, not a PTY."""
from __future__ import annotations
import ast
import os
import platform
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from .workspace import Workspace
from .terminals import child_environment


@dataclass
class Job:
    id: str
    commands: list
    cwd: Path
    shell: bool = False
    output: str = ""
    done: bool = False
    code: int | None = None
    process: object = None
    cancelled: bool = False
    timeout: float = 120
    stop_on_output_limit: bool = True
    extra_env: dict = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock)

    def append(self, text: str):
        with self.lock:
            if not self.stop_on_output_limit:
                self.output=(self.output+text)[-512_000:]
                return
            available = 512_000 - len(self.output)
            if available > 0:
                self.output += text[:available]

    def cancel(self):
        self.cancelled = True
        p = self.process
        if p and p.poll() is None:
            try:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    os.killpg(p.pid, signal.SIGKILL)
            except (OSError, subprocess.SubprocessError):
                p.kill()

    def write(self,text):
        if not isinstance(text,str) or len(text)>65536:raise ValueError('Entrada demasiado larga.')
        with self.lock:
            if self.done or not self.process or self.process.poll() is not None:raise ValueError('No hay un programa esperando entrada.')
            try:self.process.stdin.write(text.encode('utf-8'));self.process.stdin.flush()
            except OSError as exc:raise ValueError('El programa ha cerrado su entrada.') from exc

    def environment(self):
        env=child_environment();folders=[]
        for command in self.commands:
            if isinstance(command,list) and command and Path(command[0]).is_absolute():folders.append(str(Path(command[0]).parent))
        env['PATH']=os.pathsep.join(dict.fromkeys(folders))+os.pathsep+env.get('PATH','')
        env.update(self.extra_env)
        return env

    def run(self):
        started = time.monotonic()
        try:
            for command in self.commands:
                if self.cancelled:
                    break
                shown = command if isinstance(command, str) else shlex.join(command)
                self.append(f"$ {shown}\n")
                opts = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
                self.process = subprocess.Popen(command, cwd=self.cwd, shell=self.shell,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, env=self.environment(), **opts)
                if self.cancelled:self.cancel()
                stream = self.process.stdout
                def read_output(stream=stream):
                    import codecs
                    decoder = codecs.getincrementaldecoder("utf-8")("replace")
                    with stream:
                        while True:
                            chunk = stream.read1(4096)
                            if not chunk:
                                self.append(decoder.decode(b"", final=True))
                                break
                            self.append(decoder.decode(chunk))
                reader = threading.Thread(target=read_output, daemon=True)
                reader.start()
                while self.process.poll() is None:
                    if self.timeout and time.monotonic() - started > self.timeout:
                        self.append(f"\nTime limit reached ({self.timeout:g} s).\n")
                        self.cancel()
                    if self.stop_on_output_limit and len(self.output) >= 512_000:
                        self.cancel()
                    time.sleep(0.05)
                self.code = self.process.wait()
                self.process.stdin.close()
                reader.join(timeout=2)
                if self.code:
                    break
            if self.cancelled:
                self.code = -1
                self.append("\nTask stopped.\n")
            else:
                self.append(f"\nProcess exited with code {self.code or 0} · {time.monotonic() - started:.2f}s\n")
        except (OSError, subprocess.SubprocessError) as exc:
            self.code = -1
            self.append(f"\nCannot run task: {exc}\n")
        finally:
            self.done = True


class Runner:
    def __init__(self, allow_shell=False):
        self.allow_shell = allow_shell
        self.jobs: dict[str, Job] = {}
        self.lock = threading.RLock()

    def start(self, commands: list, cwd: Path, shell=False, timeout=120, env=None, stop_on_output_limit=True) -> dict:
        with self.lock:
            if sum(not j.done for j in self.jobs.values()) >= 2:
                raise ValueError("Ya hay dos tareas activas. Detén una antes de iniciar otra.")
            if len(self.jobs) > 40:
                for old in [k for k, v in self.jobs.items() if v.done][:-20]:
                    del self.jobs[old]
            job = Job(uuid.uuid4().hex, commands, cwd, shell)
            job.timeout = timeout
            job.stop_on_output_limit = stop_on_output_limit
            job.extra_env = dict(env or {})
            self.jobs[job.id] = job
        threading.Thread(target=job.run, daemon=True).start()
        return {"job": job.id}

    def task(self, ws: Workspace, name: str, *, check=False) -> dict:
        if not ws.trusted:
            raise PermissionError("Confirma que confías en este proyecto antes de ejecutar código local.")
        path = ws.resolve(name)
        suffix = path.suffix.lower()
        if suffix == ".py":
            if check:
                ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
                return {"output": "Python syntax check passed.\n"}
            commands = [[sys.executable, "--python-child", str(path)]] if getattr(sys,"frozen",False) else [[sys.executable, "-u", str(path)]]
        elif suffix in (".js", ".mjs", ".cjs"):
            if not shutil.which("node"):
                raise ValueError("Node.js no está instalado o no está en PATH.")
            commands = [["node", *(["--check"] if check else []), str(path)]]
        elif suffix in (".c", ".cpp", ".cc", ".cxx", ".s"):
            cxx = suffix in (".cpp", ".cc", ".cxx")
            compiler = shutil.which("g++" if cxx else "gcc")
            if not compiler:
                raise ValueError("No se encuentra g++/gcc. Instala una toolchain o usa WSL con build-essential.")
            if suffix == ".s" and not (sys.platform.startswith("linux") and platform.machine().lower() in ("x86_64", "amd64")):
                raise ValueError("El ejemplo ASM incluido requiere Linux/WSL x86-64.")
            standard = ["-std=c++17"] if cxx else (["-std=c11"] if suffix == ".c" else [])
            if check and suffix != ".s":
                commands = [[compiler, *standard, "-Wall", "-Wextra", "-fsyntax-only", str(path)]]
            else:
                exe = ws.private_dir("run") / ("task_" + uuid.uuid4().hex + (".exe" if os.name == "nt" else ""))
                commands = [[compiler, *standard, "-Wall", "-Wextra", str(path), "-o", str(exe)]]
                if not check:
                    commands.append([str(exe)])
        else:
            raise ValueError("No hay un ejecutor configurado para este tipo. Los componentes C# necesitan Unity y no se ejecutan como programas independientes. Prueba Examples/hello.py.")
        return self.start(commands, ws.root)

    def git(self, ws: Workspace, mode="status") -> str:
        if not shutil.which("git"):
            return "Git no está instalado.\n"
        args = {"status": ["status", "--short", "--branch"], "diff": ["diff", "--no-ext-diff", "--no-textconv", "--stat"],
                "log": ["log", "-5", "--oneline", "--no-decorate"], "branch": ["branch", "--list"]}
        if mode not in args:
            raise ValueError("Operación Git no admitida.")
        result = subprocess.run(["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=" + os.devnull, "--no-pager", *args[mode]], cwd=ws.root, capture_output=True,
                                timeout=8, text=True, encoding="utf-8", errors="replace", creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if result.returncode and "not a git repository" in result.stderr.lower():
            return "Este proyecto no es un repositorio Git. No se ha creado ni modificado ninguno.\n"
        return (result.stdout + result.stderr)[:100_000] or "No changes.\n"

    def console(self, ws: Workspace, command: str, cwd_name="") -> dict:
        if len(command) > 4096:
            raise ValueError("Comando demasiado largo.")
        cwd = ws.resolve(cwd_name)
        if not cwd.is_dir():
            raise ValueError("El directorio de trabajo no es una carpeta.")
        try:
            parts = shlex.split(command, posix=True)
        except ValueError as exc:
            raise ValueError("Revisa las comillas del comando.") from exc
        if not parts:
            return {"output": ""}
        name, args = parts[0], parts[1:]
        if name in ("help", "?"):
            return {"output": ("LUMEN · local command console\n"
                "help · pwd · ls [path] · cd [path] · cat <file>\n"
                "check · stats <file> · run <file> · clear\n"
                "git status | diff | log | branch · version\n"
                "Programs run only after workspace trust. No interactive PTY.\n"
                + ("Unrestricted shell is enabled for this session.\n" if self.allow_shell else "Shell operators / arbitrary commands are disabled.\n"))}
        if name == "clear":
            return {"clear": True, "output": ""}
        if name == "pwd":
            return {"output": str(cwd) + "\n"}
        if name in ("ls", "dir"):
            target = ws.resolve(str(cwd.relative_to(ws.root) / (args[0] if args else ".")))
            if not target.is_dir():
                raise ValueError("ls necesita una carpeta.")
            children = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            return {"output": "\n".join(p.name + ("/" if p.is_dir() else "") for p in children if not p.is_symlink()) + "\n"}
        if name == "cd":
            target = ws.resolve(str(cwd.relative_to(ws.root) / (args[0] if args else ".")))
            if not target.is_dir():
                raise ValueError("La ruta no es una carpeta.")
            return {"cwd": target.relative_to(ws.root).as_posix(), "output": ""}
        if name in ("cat", "stats", "run"):
            if len(args) != 1:
                raise ValueError(f"Uso: {name} <archivo>")
            relative = str(cwd.relative_to(ws.root) / args[0])
            if name == "run":
                return self.task(ws, relative)
            result = ws.read(relative)
            if name == "cat":
                return {"output": result["content"] + "\n"}
            import json
            return {"output": json.dumps(result["stats"], ensure_ascii=False, indent=2) + "\n"}
        if name == "check":
            return {"output": ws.check()}
        if name == "version":
            return {"output": f"Lumen Studio 0.5.2\nPython {platform.python_version()}\n{ws.native.name}\n"}
        if name == "git" and len(args) == 1 and args[0] in ("status", "diff", "log", "branch"):
            return {"output": self.git(ws, args[0])}
        if self.allow_shell and ws.trusted:
            return self.start([command], cwd, shell=True)
        raise ValueError("Comando no habilitado. Escribe help. La consola no interpreta tuberías ni redirecciones en modo protegido.")

    def shutdown(self):
        for job in self.jobs.values():
            if not job.done:
                job.cancel()
