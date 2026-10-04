"""Loopback-only HTTP bridge for the desktop/browser UI. Not a public web server."""
from __future__ import annotations
import json
import mimetypes
import os
import platform
import secrets
import sys
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
from .native import NativeCore
from .workspace import Workspace, ConflictError
from .runner import Runner
from .ai import LocalAssistant
from .platform_services import PlatformServices


class Application:
    def __init__(self, project: Path, workspace: Path, allow_shell=False, data_dir=None):
        self.project = project
        self.native = NativeCore(project)
        self.workspace = Workspace(workspace, self.native)
        self.runner = Runner(allow_shell)
        self.assistant = LocalAssistant()
        self.token = secrets.token_urlsafe(32)
        self.features = PlatformServices(self, data_dir)
        from .session import remember_workspace
        remember_workspace(self.workspace.root, self.features.prefs.directory)

    def state(self):
        return {"version": "0.5.2", "startup":getattr(self,'startup',{}), "workspace": str(self.workspace.root), "name": self.workspace.root.name,
                "python": platform.python_version(), "platform": platform.system(), "native": self.native.name,
                "trusted": self.workspace.trusted, "shell": self.runner.allow_shell,
                "monaco": (self.project / "web/vendor/monaco/vs/loader.js").is_file(),
                "babylon": (self.project / "web/vendor/babylon/babylon.js").is_file(),
                "ai": {"connected": self.assistant.connected, "model": self.assistant.model, "base": self.assistant.base}}


class LumenServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    def __init__(self, port: int, application: Application):
        self.app = application
        super().__init__(("127.0.0.1", port), Handler)


class Handler(BaseHTTPRequestHandler):
    server_version = "Lumen/0.5.2"
    sys_version = ""

    @property
    def app(self) -> Application:
        return self.server.app

    def log_message(self, format, *args):
        # Avoid printing code contents, prompts, tokens, or full private paths.
        if args and str(args[0]).startswith("GET /api/job"):
            return
        if os.environ.get("LUMEN_VERBOSE"):
            super().log_message(format, *args)

    def valid_host(self):
        port = self.server.server_port
        return self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}")

    def auth(self, *, bootstrap=False):
        if not self.valid_host():
            raise PermissionError("Host no permitido.")
        origin = self.headers.get("Origin")
        valid = (f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}")
        if origin and origin not in valid:
            raise PermissionError("Origen no permitido.")
        site = self.headers.get("Sec-Fetch-Site", "none")
        if site not in ("same-origin", "none"):
            raise PermissionError("Petición entre sitios no permitida.")
        from http.cookies import SimpleCookie
        cookies = SimpleCookie()
        cookies.load(self.headers.get("Cookie", ""))
        cookie = cookies.get("lumen_session")
        if not cookie or not secrets.compare_digest(cookie.value, self.app.token):
            raise PermissionError("Sesión no válida. Recarga Lumen desde su dirección local.")
        if not bootstrap and not secrets.compare_digest(self.headers.get("X-Lumen-Token", ""), self.app.token):
            raise PermissionError("Token de sesión no válido.")
        expected_workspace=self.headers.get('X-Lumen-Workspace')
        if expected_workspace and unquote(expected_workspace)!=str(self.app.workspace.root):
            raise ConflictError('La carpeta cambió en otra ventana. Conserva o copia tu búfer antes de volver a abrir el editor.')

    def reply(self, data, code=200, content_type="application/json; charset=utf-8", session=False):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8") if isinstance(data, (dict, list)) else data
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store" if content_type.startswith("application/json") or session else "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self'; worker-src 'self' blob:; frame-src http://127.0.0.1:*; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        if session:
            self.send_header("Set-Cookie", f"lumen_session={self.app.token}; HttpOnly; SameSite=Strict; Path=/")
        try:
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def failure(self, exc):
        code = 409 if isinstance(exc, ConflictError) else 403 if isinstance(exc, PermissionError) else 404 if isinstance(exc, FileNotFoundError) else 400
        if not isinstance(exc, (ValueError, PermissionError, OSError, KeyError, SyntaxError)):
            code = 500
            if os.environ.get("LUMEN_VERBOSE"):
                traceback.print_exc()
        self.reply({"error": str(exc) if code != 500 else "Error interno. Revisa la consola de Python."}, code)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        try:
            if not self.valid_host():
                raise PermissionError("Host no permitido.")
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)
            if path.startswith("/api/"):
                self.auth(bootstrap=path == "/api/bootstrap")
                ws = self.app.workspace
                if path == "/api/bootstrap":
                    return self.reply({**self.app.state(), "token": self.app.token, "tree": ws.tree()})
                if path.startswith("/api/platform/"):
                    return self.reply(self.app.features.get(path[len("/api/platform"):], query))
                if path == "/api/state":
                    return self.reply(self.app.state())
                if path == "/api/tree":
                    return self.reply({"tree": ws.tree(), "name": ws.root.name})
                if path == "/api/file":
                    return self.reply(ws.read(query.get("path", [""])[0]))
                if path == "/api/search":
                    return self.reply({"results": ws.search(query.get("q", [""])[0], content=query.get("content", ["0"])[0] == "1", folder=query.get('folder',[''])[0])})
                if path == "/api/git":
                    return self.reply({"output": self.app.runner.git(ws, query.get("mode", ["status"])[0])})
                if path == "/api/job":
                    job = self.app.runner.jobs.get(query.get("id", [""])[0])
                    if not job:
                        raise FileNotFoundError("La tarea ya no está disponible.")
                    offset = max(0, int(query.get("offset", ["0"])[0]))
                    with job.lock:
                        return self.reply({"output": job.output[offset:], "offset": len(job.output), "done": job.done, "code": job.code})
                raise FileNotFoundError("API desconocida.")
            base = (self.app.project / "web").resolve()
            relative = "index.html" if path == "/" else unquote(path).lstrip("/")
            file = (base / relative).resolve()
            if not file.is_relative_to(base) or not file.is_file():
                raise FileNotFoundError("Recurso no encontrado.")
            mime = mimetypes.guess_type(str(file))[0] or "application/octet-stream"
            if file.suffix in (".js", ".mjs"):
                mime = "text/javascript"
            if file.suffix in (".html", ".css", ".js", ".mjs", ".svg"):
                mime += "; charset=utf-8"
            return self.reply(file.read_bytes(), content_type=mime, session=file.name == "index.html")
        except Exception as exc:
            self.failure(exc)

    def do_POST(self):
        try:
            self.auth()
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 3_000_000:
                raise ValueError("Tamaño de petición no válido.")
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                raise ValueError("Se requiere JSON.")
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError("El cuerpo debe ser un objeto JSON.")
            path = urlparse(self.path).path
            ws = self.app.workspace
            if path.startswith("/api/platform/"):
                return self.reply(self.app.features.post(path[len("/api/platform"):], body))
            if path == "/api/save":
                result=ws.save(body["path"], body["content"], body.get("revision"), create=bool(body.get("create")), newline=body.get("newline", "LF"), bom=bool(body.get("bom")))
                self.app.features.lantern.saved(ws,body['path'])
                return self.reply(result)
            if path == "/api/workspace":
                if any(not job.done for job in self.app.runner.jobs.values()):
                    raise ValueError("Detén las tareas activas antes de cambiar de proyecto.")
                next_workspace = Workspace(Path(body["path"]), self.app.native)
                self.app.features.workspace_changed()
                self.app.workspace = next_workspace
                from .session import remember_workspace
                remember_workspace(next_workspace.root, self.app.features.prefs.directory)
                return self.reply({**self.app.state(), "tree": self.app.workspace.tree()})
            if path == "/api/trust":
                ws.trusted = body.get("trusted") is True
                if not ws.trusted: self.app.features.workspace_changed()
                return self.reply({"trusted": ws.trusted})
            if path == "/api/console":
                import shlex
                parts=shlex.split(body.get('command',''))
                if parts and parts[0]=='run' and len(parts)==2:
                    from pathlib import PurePosixPath
                    target=str(PurePosixPath(body.get('cwd',''))/parts[1])
                    plan=self.app.features.runtimes.plan(ws,target)
                    if plan.get('preview'):return self.reply({'preview':self.app.features.preview.start(ws,target)})
                    return self.reply(self.app.runner.start(plan['commands'],ws.root,timeout=0))
                return self.reply(self.app.runner.console(ws, body.get("command", ""), body.get("cwd", "")))
            if path == "/api/task":
                from .runtimes import language
                if language(body['path']):
                    plan=self.app.features.runtimes.plan(ws,body['path'],check=bool(body.get('check')))
                    if plan.get('preview'):return self.reply({'preview':self.app.features.preview.start(ws,body['path'])})
                    if not plan['commands']:return self.reply({'output':'Comprobación completada.\n'})
                    return self.reply(self.app.runner.start(plan['commands'],ws.root,timeout=120 if body.get('check') else 0))
                return self.reply(self.app.runner.task(ws, body['path'], check=bool(body.get('check'))))
            if path == "/api/task-input":
                if not ws.trusted:raise PermissionError('Autoriza el proyecto antes de interactuar con su programa.')
                job=self.app.runner.jobs.get(body.get('id'))
                if not job:raise ValueError('Tarea no encontrada.')
                job.write(body.get('text'))
                return self.reply({'ok':True})
            if path == "/api/stop":
                job = self.app.runner.jobs.get(body.get("id"))
                if job:
                    job.cancel()
                return self.reply({"stopped": bool(job)})
            if path == "/api/stats":
                return self.reply(self.app.native.stats(body.get("content", "")))
            if path == "/api/ai/connect":
                return self.reply(self.app.assistant.connect(body.get("base", "http://127.0.0.1:11434"), body.get("model", "")))
            if path == "/api/ai/disconnect":
                self.app.assistant.connected = False
                return self.reply({"connected": False})
            if path == "/api/ai/chat":
                return self.reply(self.app.assistant.chat(body.get("question", ""), body.get("path", "untitled"), body.get("content", "")))
            raise FileNotFoundError("API desconocida.")
        except Exception as exc:
            self.failure(exc)
