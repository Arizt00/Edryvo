"""Explicit WebView2 bridge. Native objects MUST remain private to avoid JS introspection."""
import sys
from .version import PRODUCT_NAME, VERSION, REVISION

class DesktopAPI:
    def __init__(self):
        self._window = None
        self._maximized = False
        self._application = None
        self._url = None
        self._children = {}
        self._owner = None
        self._panel = None

    def status(self):
        return {'ready': self._window is not None, 'version': VERSION, 'revision': REVISION, 'panel': self._panel}

    def detach_panel(self, panel, path='', position=None):
        """Independent native window, sharing backend processes and document hub."""
        import webview
        from urllib.parse import urlencode
        titles={'project':'Proyecto','assistant':'Melody','console':'Terminal','editor':path or 'Editor','forge':'Forge','preview':'Vista web','lantern':'Lantern','profile-general':'Desarrollo general','profile-web':'Desarrollo web','profile-data':'Ciencia de datos','profile-design':'Diseño y UI'}
        if panel not in titles:raise ValueError('Panel desconocido.')
        if self._owner is not None:
            self.close_panel()
            return {'opened':False,'returned':True,'panel':self._panel}
        if path:self._application.workspace.resolve(path)
        key=panel+':'+path if panel=='editor' else panel
        if key in self._children:
            self._children[key].destroy()
            return {'opened':False,'returned':True,'panel':panel}
        api=DesktopAPI();api._application=self._application;api._url=self._url;api._panel=panel;api._owner=self
        query=urlencode({'panel':panel,'file':path})
        coordinates={}
        if isinstance(position,dict):
            for axis in ('x','y'):
                value=position.get(axis)
                if isinstance(value,(int,float)) and -100_000<=value<=100_000:coordinates[axis]=round(value)
        child=webview.create_window(PRODUCT_NAME+' · '+titles[panel],self._url+'/?'+query,js_api=api,width=1060 if panel in ('editor','forge','preview','lantern') or panel.startswith('profile-') else 640,height=760,min_size=(380,320),easy_drag=False,background_color='#191d28',**coordinates)
        api._window=child;self._children[key]=child
        def closed():
            self._children.pop(key,None)
            # Qt evaluation can wait for a renderer already closing. Never keep
            # the native closed-event thread alive waiting for its JS response.
            if self._window.events.closed.is_set():return
            def notify_parent():
                if self._window.events.closed.is_set():return
                try:self._window.evaluate_js('window.dispatchEvent(new CustomEvent("lumen:native-return",{detail:'+__import__('json').dumps({'panel':panel,'path':path})+'}))')
                except Exception:pass
            __import__('threading').Thread(target=notify_parent,daemon=True).start()
        child.events.closed+=closed
        return {'opened':True,'panel':panel}

    def close_panel(self):
        """Return this shared child to its original application, without stopping jobs."""
        if self._owner is None:raise ValueError('Esta ventana ya está acoplada.')
        self._window.destroy()
        return {'returned':True,'panel':self._panel}

    def close_forge(self):
        if getattr(self,'_panel',None)!='forge':raise ValueError('Esta ventana no es Forge.')
        self._window.destroy()

    def install_update(self):
        import subprocess
        from pathlib import Path
        installer=self._application.features.updates.installer()
        # The user launches the downloaded installer when ready. The current
        # editor stays open, so unsaved buffers are never forcibly discarded.
        if sys.platform=='darwin':
            command=['/usr/bin/open',str(installer)]
        elif sys.platform.startswith('linux'):
            import shutil
            opener=shutil.which('xdg-open')
            if not opener:raise ValueError('Instala xdg-utils para abrir el paquete de actualización.')
            command=[opener,str(installer)]
        else:command=[str(installer)]
        process=subprocess.Popen(command,cwd=installer.parent,creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
        return {'opened':True,'pid':process.pid}

    def new_window(self, path='', content=None):
        import subprocess
        import uuid
        from pathlib import Path
        from .preferences import atomic_json
        app=self._application
        if path: app.workspace.resolve(path)
        if content is not None and (not isinstance(content,str) or len(content)>2_000_000): raise ValueError('Archivo demasiado grande para transferir.')
        args=[sys.executable,*([] if getattr(sys,'frozen',False) else [str(app.project/'app.py')]),'--desktop','--port','0','--workspace',str(app.workspace.root)]
        if path: args+=['--open-file',path]
        if content is not None:
            folder=app.features.prefs.directory/'window-drafts';folder.mkdir(parents=True,exist_ok=True)
            draft=folder/(uuid.uuid4().hex+'.json');atomic_json(draft,{'path':path,'content':content});args+=['--draft',str(draft)]
        process=subprocess.Popen(args,cwd=app.project,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
        return {'opened':True,'pid':process.pid}

    def save_as(self, name, content):
        import webview
        from pathlib import Path
        if not isinstance(content,str) or len(content)>2_000_000:raise ValueError('Archivo demasiado grande.')
        result=self._window.create_file_dialog(webview.FileDialog.SAVE,save_filename=Path(name).name)
        if not result:return None
        target=Path(result[0] if isinstance(result,(list,tuple)) else result)
        # The native save dialog asks before replacing an existing file.
        target.write_text(content,encoding='utf-8',newline='')
        try:relative=target.resolve().relative_to(self._application.workspace.root).as_posix()
        except ValueError:relative=None
        return {'path':str(target),'relative':relative}

    def choose_folder(self):
        import webview
        result = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        return result[0] if result else None

    def choose_file(self):
        import webview
        result = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=False)
        return result[0] if result else None

    def choose_extension(self):
        import webview
        result = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=False, file_types=('Extension package (*.vsix;*.zip)',))
        return result[0] if result else None

    def lock_session(self):
        if sys.platform == 'win32':
            import ctypes
            return bool(ctypes.windll.user32.LockWorkStation())
        return False

    def window_action(self, action):
        if action == 'minimize': self._window.minimize()
        elif action == 'maximize':
            if self._maximized: self._window.restore()
            else: self._window.maximize()
        elif action == 'close': self._window.destroy()
