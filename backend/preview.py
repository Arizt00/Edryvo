"""Isolated-origin preview: workspace pages never share the authenticated IDE origin."""
import mimetypes
import secrets
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote,quote,urlparse

class WebPreview:
    def __init__(self):self.server=None;self.token=secrets.token_urlsafe(24);self.root=None;self.buffers={}
    def start(self,workspace,path,buffers=None):
        if not workspace.trusted:raise PermissionError('Autoriza el proyecto para ejecutar su contenido web.')
        overlays={};total=0
        for entry in buffers or []:
            if not isinstance(entry,dict) or not isinstance(entry.get('content'),str):raise ValueError('Búfer web no válido.')
            file=workspace.resolve(entry.get('path',''),must_exist=False)
            raw=entry['content'].encode('utf-8');total+=len(raw)
            if total>8_000_000 or len(overlays)>=100:raise ValueError('La vista web admite hasta 8 MB de búferes.')
            overlays[file]=raw
        selected=workspace.resolve(path)
        if selected.suffix.lower()=='.css':
            html=selected.with_suffix('.html')
            if not html.exists():html=workspace.root/'index.html'
            if not html.exists():raise ValueError('Crea index.html o un HTML con el mismo nombre para previsualizar esta hoja CSS.')
            selected=workspace.resolve(html.relative_to(workspace.root).as_posix())
        if selected.suffix.lower() not in ('.html','.htm','.htmll'):raise ValueError('Selecciona HTML o su hoja CSS.')
        if self.root!=workspace.root:self.stop()
        self.root=workspace.root
        self.buffers=overlays
        if not self.server:
            outer=self
            class Handler(BaseHTTPRequestHandler):
                def log_message(self,*args):pass
                def do_GET(self):
                    try:
                        if self.headers.get('Host')!=f'127.0.0.1:{self.server.server_port}':raise PermissionError()
                        path=unquote(urlparse(self.path).path)
                        prefix='/'+outer.token+'/'
                        authorized=path.startswith(prefix)
                        if not authorized and ('lumen_preview_'+str(self.server.server_port)+'='+outer.token) not in self.headers.get('Cookie','').split('; '):raise PermissionError()
                        relative=path[len(prefix):] if authorized else path.lstrip('/');file=workspace.resolve(relative or 'index.html')
                        if file.is_dir():file=workspace.resolve((file/'index.html').relative_to(workspace.root).as_posix())
                        if any(part in ('.git','.lumen','.env','.venv','node_modules') for part in Path(relative).parts):raise PermissionError()
                        raw=outer.buffers.get(file)
                        if raw is None:
                            if file.stat().st_size>20_000_000:raise ValueError()
                            raw=file.read_bytes()
                        mime='text/javascript' if file.suffix in ('.js','.mjs') else 'text/html' if file.suffix=='.htmll' else mimetypes.guess_type(str(file))[0] or 'application/octet-stream'
                        if mime.startswith('text/') or mime in ('application/javascript','application/json'):mime+='; charset=utf-8'
                        self.send_response(200);self.send_header('Set-Cookie',f'lumen_preview_{self.server.server_port}={outer.token}; Path=/; HttpOnly; SameSite=Strict');self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.end_headers();self.wfile.write(raw)
                    except (BrokenPipeError,ConnectionError):pass
                    except (OSError,ValueError,PermissionError):
                        try:self.send_error(404)
                        except (BrokenPipeError,ConnectionError):pass
            self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.daemon_threads=True
            threading.Thread(target=self.server.serve_forever,daemon=True).start()
        return {'url':f'http://127.0.0.1:{self.server.server_port}/{self.token}/'+quote(selected.relative_to(workspace.root).as_posix()),'path':selected.relative_to(workspace.root).as_posix()}
    def stop(self):
        if self.server:self.server.shutdown();self.server.server_close();self.server=None
        self.root=None;self.buffers={};self.token=secrets.token_urlsafe(24)
