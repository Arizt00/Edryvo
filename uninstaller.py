"""Edryvo's graphical uninstaller. Relocates itself before removing its own bundle."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
from backend.preferences import user_data_dir
from backend.uninstall import Uninstaller, no_links

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))

def retire_temporary_launcher():
    if os.name!='nt' or not getattr(sys,'frozen',False):return
    executable=no_links(sys.executable);folder=executable.parent
    if folder.parent!=no_links(tempfile.gettempdir()) or not folder.name.startswith('LumenUninstall-') or executable.name!='Uninstall-Edryvo.exe':return
    quote=lambda value:"'"+str(value).replace("'","''")+"'"
    # Remove only our executable, then the empty directory; never recurse.
    script=f"Wait-Process -Id {os.getpid()} -ErrorAction SilentlyContinue; for($attempt=0;$attempt -lt 30;$attempt++){{Start-Sleep -Milliseconds 500; Remove-Item -LiteralPath {quote(executable)} -Force -ErrorAction SilentlyContinue; if(-not(Test-Path -LiteralPath {quote(executable)})){{Remove-Item -LiteralPath {quote(folder)} -ErrorAction SilentlyContinue;break}}}}"
    subprocess.Popen(['powershell.exe','-NoProfile','-NonInteractive','-WindowStyle','Hidden','-Command',script],creationflags=subprocess.CREATE_NO_WINDOW,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

class UninstallerAPI:
    def __init__(self, service): self._service = service; self._window = None
    def info(self): return self._service.info()
    def status(self): return self._service.status()
    def start(self, options): return self._service.start(options)
    def close(self):
        if self._service.status()['status'] == 'removing': return False
        self._window.destroy(); return True

class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}': self.send_error(403); return
        if self.path == '/': self.path = '/uninstall.html'
        super().do_GET()
    def end_headers(self):
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
        self.send_header('X-Content-Type-Options', 'nosniff')
        super().end_headers()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', type=Path)
    args = parser.parse_args()
    target = args.target or Path(sys.executable).parent
    service = Uninstaller(target, user_data_dir())  # Validate before starting any helper.
    if getattr(sys, 'frozen', False) and Path(sys.executable).resolve().is_relative_to(service.root):
        temporary = Path(tempfile.mkdtemp(prefix='LumenUninstall-'))
        relocated = temporary / 'Uninstall-Edryvo.exe'
        shutil.copy2(sys.executable, relocated)
        child = subprocess.Popen([str(relocated), '--target', str(service.root)], creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        # This supervisor remains outside all application version folders. The UI
        # may delete the installed launcher only after this process exits.
        return
    import webview
    api = UninstallerAPI(service)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(ROOT / 'web')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    api._window = webview.create_window('Desinstalar Edryvo', f'http://127.0.0.1:{server.server_port}/', js_api=api,
        width=960, height=760, min_size=(740, 620), background_color='#F6F7FD')
    api._window.events.closing += lambda: False if service.status()['status'] == 'removing' else None
    try: webview.start()
    finally: server.shutdown(); server.server_close(); retire_temporary_launcher()

if __name__ == '__main__': main()
