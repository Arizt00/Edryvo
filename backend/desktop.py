"""Explicit WebView2 bridge. Native objects MUST remain private to avoid JS introspection."""
import sys

class DesktopAPI:
    def __init__(self):
        self._window = None
        self._maximized = False
        self._application = None

    def status(self):
        return {'ready': self._window is not None, 'version': '0.5.2', 'revision': 6}

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
