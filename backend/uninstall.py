"""Manifest-bounded removal. The UI never supplies a filesystem target."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import re
import shutil
import threading


def no_links(path):
    """Reject junctions as well as symlinks, including parent components."""
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError('La ruta contiene un enlace o una unión: ' + str(part))
    return path.resolve()


class Uninstaller:
    def __init__(self, root, data_dir, *, integrate_windows=True):
        self.root = no_links(root)
        self.data_dir = no_links(data_dir)
        if self.root == self.data_dir or self.root.is_relative_to(self.data_dir) or self.data_dir.is_relative_to(self.root):
            raise ValueError('La instalación y el perfil deben estar en carpetas independientes.')
        if len(self.root.parts) < 3 or len(self.data_dir.parts) < 3:
            raise ValueError('No se puede desinstalar una carpeta del sistema.')
        self.integrate_windows = integrate_windows
        self.lock = threading.RLock()
        self.state = {'status': 'ready', 'progress': 0, 'message': '', 'removed': [], 'warnings': []}
        self.manifest = json.loads((self.root / 'installation.json').read_text(encoding='utf-8'))
        names = self.manifest.get('directories', [self.manifest.get('directory', '')])
        if not isinstance(names, list) or not names or len(names) > 100:
            raise ValueError('Manifiesto de instalación no válido.')
        self.targets = []
        for name in dict.fromkeys(names):
            if not isinstance(name, str) or not re.fullmatch(r'app-\d+\.\d+\.\d+(?:-previous-\d+)?', name):
                raise ValueError('Versión de instalación no válida.')
            target = no_links(self.root / name)
            if target.parent != self.root:
                raise ValueError('La versión está fuera de la instalación.')
            self.targets.append(target)

    def info(self):
        return {'name': 'Edryvo', 'version': self.manifest.get('version', '0.5.2'),
                'installation': str(self.root), 'dataDirectory': str(self.data_dir),
                'versions': [p.name for p in self.targets],
                'dataExists': self.data_dir.exists(),
                'internalProjects': str(self.data_dir / 'workspaces'),
                'hasInternalProjects': (self.data_dir / 'workspaces').exists()}

    def status(self):
        with self.lock:
            return copy.deepcopy(self.state)

    def start(self, options):
        if not isinstance(options, dict) or options.get('confirm') is not True:
            raise ValueError('Confirma la desinstalación desde la pantalla de revisión.')
        for key in ('deleteData', 'deleteProjects'):
            if type(options.get(key, False)) is not bool:
                raise ValueError('Selección no válida.')
        if options.get('deleteProjects') and not options.get('deleteData'):
            raise ValueError('Selecciona primero el borrado de datos.')
        with self.lock:
            if self.state['status'] in ('removing', 'finished'):
                raise ValueError('La desinstalación ya ha comenzado.')
            self.state.update(status='removing', progress=0, message='Comprobando la instalación…', warnings=[])
        threading.Thread(target=self._remove, args=(copy.deepcopy(options),), daemon=True).start()
        return self.status()

    def _tree(self, path, parent):
        target = no_links(path)
        if target.parent != no_links(parent):
            raise ValueError('Destino de borrado fuera de la carpeta autorizada.')
        if not target.exists():
            return
        # Reject reparse points before any recursive delete (never traverse them).
        for folder, dirs, files in os.walk(target, followlinks=False):
            for name in dirs + files:
                no_links(Path(folder) / name)
        shutil.rmtree(target)
        with self.lock:
            self.state['removed'].append(str(target))

    def _running(self):
        if not self.integrate_windows:
            return False
        import psutil
        for process in psutil.process_iter(['exe']):
            try:
                exe = process.info.get('exe')
                if exe and Path(exe).resolve().is_relative_to(self.root) and Path(exe).name.lower() == 'lumen.exe':
                    return True
            except (OSError, psutil.Error):
                pass
        return False

    def _remove(self, options):
        try:
            if self._running():
                raise ValueError('Edryvo sigue abierto. Guarda tu trabajo, cierra todas sus ventanas y pulsa Reintentar.')
            for index, target in enumerate(self.targets):
                self._tree(target, self.root)
                with self.lock:
                    self.state.update(progress=15 + int(45 * (index + 1) / len(self.targets)), message='Retirando Edryvo…')
            if options.get('deleteData') and self.data_dir.exists():
                if options.get('deleteProjects'):
                    self._tree(self.data_dir, self.data_dir.parent)
                else:
                    # Built-in workspaces can contain the user's only source copy.
                    for child in self.data_dir.iterdir():
                        if child.name == 'workspaces':
                            continue
                        no_links(child)
                        if child.is_dir(): self._tree(child, self.data_dir)
                        else: child.unlink()
                    if not any(self.data_dir.iterdir()): self.data_dir.rmdir()
            if options.get('deleteData') and self.integrate_windows:
                import keyring as native
                for provider in ('openai', 'anthropic', 'gemini'):
                    if native:
                        try:
                            if native.get_password('LumenStudio', provider): native.delete_password('LumenStudio', provider)
                        except Exception:
                            self.state['warnings'].append('No se pudo retirar la credencial de ' + provider + ' del almacén de Windows.')
            with self.lock:
                self.state.update(progress=85, message='Retirando accesos de Windows…')
            if self.integrate_windows and os.name == 'nt':
                import pythoncom
                pythoncom.CoInitialize()
                try:self._windows()
                finally:pythoncom.CoUninitialize()
            for name in ('installation.json', 'Uninstall-Lumen.ps1', 'Uninstall-Lumen.exe', 'Uninstall-Edryvo.exe'):
                path = no_links(self.root / name)
                if path.is_file(): path.unlink()
            # User-added files in the install root are not application files.
            if self.root.exists() and not any(self.root.iterdir()): self.root.rmdir()
            with self.lock:
                self.state.update(status='finished', progress=100, message='Edryvo se ha desinstalado.')
        except Exception as exc:
            with self.lock:
                self.state.update(status='error', message=str(exc))

    def _windows(self):
        import winreg
        from win32com.client import Dispatch
        shell = Dispatch('WScript.Shell')
        for folder in (Path(os.environ['APPDATA']) / 'Microsoft/Windows/Start Menu/Programs', Path(shell.SpecialFolders('Desktop'))):
            for name in ('Edryvo.lnk', 'Desinstalar Edryvo.lnk', 'Lumen Studio.lnk', 'Desinstalar Lumen Studio.lnk'):
                link = folder / name
                if link.is_file() and not link.is_symlink():
                    target = shell.CreateShortcut(str(link)).TargetPath
                    if target and Path(target).resolve().is_relative_to(self.root): link.unlink()
        key = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\LumenStudio'
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as entry:
                location = winreg.QueryValueEx(entry, 'InstallLocation')[0]
            if Path(location).resolve().is_relative_to(self.root): winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
        except FileNotFoundError:
            pass
