#!/usr/bin/env python3
"""Start Lumen Studio locally. Python 3.10+; no Python dependencies for browser mode."""
from __future__ import annotations
import argparse
import platform
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from backend.server import Application, LumenServer

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def restore_child_streams():
    """Windowed bundles still need inherited pipes for Python tasks/debug workers."""
    if sys.platform != 'win32': return
    import ctypes
    import io
    import msvcrt
    import os
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetStdHandle.restype = ctypes.c_void_p
    for name, number, mode in [('stdin', -10, 'rb'), ('stdout', -11, 'wb'), ('stderr', -12, 'wb')]:
        if getattr(sys, name) is not None: continue
        handle = kernel.GetStdHandle(number)
        if handle in (None, 0, ctypes.c_void_p(-1).value): continue
        try:
            fd = msvcrt.open_osfhandle(handle, os.O_BINARY | (os.O_RDONLY if name == 'stdin' else os.O_WRONLY))
            stream = io.TextIOWrapper(os.fdopen(fd, mode, closefd=False), encoding='utf-8', errors='replace', line_buffering=True)
            setattr(sys, name, stream)
        except OSError: pass


def open_browser(url: str):
    """Prefer the Windows browser when Python runs inside WSL."""
    try:
        if sys.platform.startswith("linux") and "microsoft" in platform.release().lower():
            command = shutil.which("wslview")
            if command:
                subprocess.Popen([command, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            command = shutil.which("cmd.exe")
            if command:
                subprocess.Popen([command, "/c", "start", "", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
        if not webbrowser.open(url):
            print(f"  Abre esta dirección en tu navegador: {url}", flush=True)
    except (OSError, subprocess.SubprocessError):
        print(f"  Abre esta dirección en tu navegador: {url}", flush=True)


def main():
    if any(arg in sys.argv for arg in ('--python-child', '--debug-child', '--lantern-child', '--no-browser')):
        restore_child_streams()
    if len(sys.argv) > 2 and sys.argv[1] == "--python-child":
        import runpy
        sys.argv = sys.argv[2:]
        sys.path.insert(0, str(Path(sys.argv[0]).resolve().parent))
        runpy.run_path(sys.argv[0], run_name="__main__")
        return
    if len(sys.argv) > 1 and sys.argv[1] == "--lantern-child":
        from backend.lantern_memory import main as lantern_main
        return lantern_main(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "--debug-child":
        from backend.debug_worker import main as debug_main
        return debug_main(sys.argv[2:])
    if len(sys.argv) > 2 and sys.argv[1] == "--pty-child":
        if sys.platform == "win32": raise SystemExit("POSIX PTY child only")
        import fcntl, termios, os
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)
        os.execvpe(sys.argv[2], sys.argv[2:], os.environ)
    if len(sys.argv)>1 and sys.argv[1] in ("focus", "concentracion", "settings", "extensions", "lantern"):
        from lumen import main as cli_main
        return cli_main(sys.argv[1:])
    parser = argparse.ArgumentParser(description="Lumen Studio · local developer preview")
    parser.add_argument("--workspace", type=Path, default=None)
    parser.add_argument('--open-file', default='')
    parser.add_argument('--draft', type=Path, default=None)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--desktop", action="store_true", help="Use optional pywebview instead of a browser")
    parser.add_argument("--allow-shell", action="store_true", help="Enable unrestricted commands after workspace trust; not a sandbox")
    args = parser.parse_args()
    if getattr(sys, 'frozen', False) and not args.no_browser: args.desktop=True
    if args.workspace is None:
        if args.desktop or getattr(sys, 'frozen', False):
            from backend.preferences import user_data_dir
            args.workspace=user_data_dir()/'workspaces/MyProject'
            if not args.workspace.exists(): shutil.copytree(ROOT/'workspace/MyProject', args.workspace)
        else: args.workspace=ROOT/'workspace/MyProject'
    if args.desktop and args.port==8765: args.port=0
    if sys.version_info < (3, 10):
        parser.error("Python 3.10 o posterior es necesario.")
    if not 0 <= args.port <= 65535:
        parser.error("El puerto no es válido.")
    try:
        application = Application(ROOT, args.workspace, args.allow_shell)
        application.startup={'path':args.open_file}
        if args.draft:
            import json
            draft_root=application.features.prefs.directory/'window-drafts'
            if args.draft.resolve().parent==draft_root.resolve() and args.draft.stat().st_size<8_000_000:
                application.startup=json.loads(args.draft.read_text(encoding='utf-8'));args.draft.unlink()
        first_launch = Path(sys.executable).parent / 'first-launch.json' if getattr(sys, 'frozen', False) else ROOT / 'first-launch.json'
        if first_launch.is_file() and not application.features.prefs.path.exists():
            import json
            try:
                initial = json.loads(first_launch.read_text(encoding='utf-8'))
                application.features.prefs.update({'general.locale': initial.get('general.locale', 'es')})
            except (OSError, ValueError): pass
        server = LumenServer(args.port, application)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"No se pudo iniciar Lumen: {exc}\nPrueba --port 8766 si el puerto está ocupado.\n")
    url = f"http://127.0.0.1:{server.server_port}"
    import os
    from backend.preferences import atomic_json
    atomic_json(application.features.prefs.directory/'instance.json', {'url':url,'pid':os.getpid(),'version':'0.5.2'})
    print(f"\n  LUMEN STUDIO  0.5.2\n  {url}\n  Proyecto: {application.workspace.root}\n  Núcleo: {application.native.name}\n", flush=True)
    if args.allow_shell:
        print("  ATENCIÓN: consola sin restricciones habilitada; el código se ejecuta con tus permisos.\n", flush=True)
    state = application.state()
    if not state["babylon"] or not state["monaco"]:
        print("  Modo base disponible. Para Monaco + Babylon: python tools/setup_assets.py\n", flush=True)
    if args.desktop:
        try:
            import webview
        except ImportError:
            print("pywebview no está instalado. Se abrirá en el navegador.\n", flush=True)
        else:
            from backend.desktop import DesktopAPI
            api = DesktopAPI()
            api._application=application
            webview.settings['ALLOW_DOWNLOADS'] = True
            # Windows owns dragging/maximizing. Webview's delegated drag handler
            # also catches children of a custom title bar, including its buttons.
            webview.settings['DRAG_REGION_SELECTOR'] = '[data-native-drag-disabled]'
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            api._window = webview.create_window("Lumen Studio", url, js_api=api, width=1648, height=928,
                min_size=(1050, 680), frameless=False, easy_drag=False, maximized=True, background_color="#F4F6FC")
            api._window.events.maximized += lambda: setattr(api, "_maximized", True)
            api._window.events.restored += lambda: setattr(api, "_maximized", False)
            try:
                webview.start()
            finally:
                application.features.shutdown()
                application.runner.shutdown()
                server.shutdown()
                server.server_close()
            return
    if not args.no_browser:
        threading.Timer(0.5, lambda: open_browser(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nCerrando Lumen.")
    finally:
        application.features.shutdown()
        application.runner.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
