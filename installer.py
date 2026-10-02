"""Lumen's standalone, per-user Windows installer with the Lenon web interface."""
from __future__ import annotations
import argparse
import copy
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from backend.preferences import atomic_json
from backend.package_sizes import PackageCatalog

VERSION = '0.5.2'
ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
PACKAGES = {
    'python': ('Python', 'Python.Python.3.12'), 'javascript': ('JavaScript / TypeScript · Node.js', 'OpenJS.NodeJS.LTS'),
    'csharp': ('C# / F# · .NET 8 SDK', 'Microsoft.DotNet.SDK.8'), 'cpp': ('C / C++ · LLVM', 'LLVM.LLVM'),
    'java': ('Java · OpenJDK 21', 'Microsoft.OpenJDK.21'), 'go': ('Go', 'GoLang.Go'),
    'asm': ('ASM · NASM', 'NASM.NASM'), 'android': ('Android Studio · desarrollo móvil', 'Google.AndroidStudio'), 'android-tools': ('Android · Platform Tools / ADB', 'Google.PlatformTools'),
    'rust': ('Rust · rustup', 'Rustlang.Rustup'), 'git': ('Git', 'Git.Git'), 'cmake': ('CMake', 'Kitware.CMake'),
}


def ps_quote(text):
    return "'" + str(text).replace("'", "''") + "'"


class Installer:
    def __init__(self, payload=None, target=None):
        self.payload = Path(payload or ROOT / 'payload')
        self.target = Path(target or Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'Programs/LumenStudio')
        self.catalog = PackageCatalog(PACKAGES)
        self.window = None
        self.lock = threading.RLock()
        self.skip = threading.Event()
        self.state = {'status': 'idle', 'progress': 0, 'message': '', 'log': [], 'warnings': [], 'phase': 'idle', 'packages': [], 'elapsed': 0}

    def info(self):
        size = sum(p.stat().st_size for p in self.payload.rglob('*') if p.is_file()) if self.payload.is_dir() else 0
        return {'version': VERSION, 'target': str(self.target), 'bytes': size, 'available': (self.payload / 'lumen.exe').is_file(),
                'winget': bool(shutil.which('winget')), 'packages': [{'id': k, 'name': v[0], 'package': v[1]} for k, v in PACKAGES.items()]}

    def status(self):
        with self.lock:
            snapshot = copy.deepcopy(self.state)
            snapshot['elapsed'] = round(time.monotonic() - getattr(self, 'started', time.monotonic()))
            return snapshot

    def skip_tools(self):
        """Finish the IDE installation while cancelling only our optional SDK worker."""
        with self.lock:
            if self.state.get('phase') != 'tools': return False
            self.skip.set()
            self.state['message'] = 'Finalizando sin las herramientas pendientes…'
        return True

    def choose_directory(self):
        import webview
        paths = self.window.create_file_dialog(webview.FileDialog.FOLDER)
        if paths: self.target = Path(paths[0]) / 'LumenStudio'
        return str(self.target)

    def start(self, options):
        if not isinstance(options, dict): raise ValueError('Configuración no válida.')
        packages = options.get('packages', [])
        if not isinstance(packages, list) or any(p not in PACKAGES for p in packages) or len(packages) != len(set(packages)):
            raise ValueError('Paquetes no válidos.')
        if options.get('locale', 'es') not in ('es', 'en'): raise ValueError('Idioma no válido.')
        if not (self.payload / 'lumen.exe').is_file(): raise ValueError('No se encuentra el programa que debe instalarse.')
        with self.lock:
            if self.state['status'] == 'installing': raise ValueError('La instalación ya está en curso.')
            self.skip.clear(); self.started = time.monotonic()
            self.state = {'status': 'installing', 'progress': 0, 'message': 'Preparando tu espacio…', 'log': [], 'warnings': [], 'phase': 'copy',
                          'packages': [{'id': p, 'name': PACKAGES[p][0], 'status': 'pending'} for p in packages]}
        threading.Thread(target=self._install, args=(copy.deepcopy(options),), daemon=True).start()
        return self.status()

    def _progress(self, value, message):
        with self.lock:
            self.state['progress'] = value; self.state['message'] = message

    def _package_state(self, key, status, detail=''):
        with self.lock:
            for item in self.state['packages']:
                if item['id'] == key: item.update(status=status, detail=detail)

    def _run_tool(self, command, timeout=300):
        # Drain pipes on a worker: polling/cancellation never wait on a silent installer.
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        chunks = []
        def drain():
            while True:
                chunk = process.stdout.read1(2048)
                if not chunk: break
                chunks.append(chunk)
                if sum(map(len, chunks)) > 24000: chunks.pop(0)
                with self.lock:
                    self.state['log'] = [b''.join(chunks).decode('utf-8', 'replace')[-12000:]]
        reader = threading.Thread(target=drain, daemon=True); reader.start()
        deadline = time.monotonic() + timeout
        reason = ''
        while process.poll() is None:
            if self.skip.wait(.15) or time.monotonic() >= deadline:
                reason = 'omitido' if self.skip.is_set() else 'tiempo de espera agotado'
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, timeout=8, creationflags=subprocess.CREATE_NO_WINDOW)
                else: process.kill()
                break
        process.wait(timeout=10); reader.join(timeout=1)
        process.stdout.close()
        return process.returncode, b''.join(chunks).decode('utf-8', 'replace'), reason

    def _install_tools(self, selected):
        with self.lock: self.state['phase'] = 'tools'
        winget = shutil.which('winget')
        for index, key in enumerate(selected):
            name, package = PACKAGES[key]
            if self.skip.is_set(): self._package_state(key, 'skipped', 'Puedes instalarlo después desde Ajustes.'); continue
            self._progress(87 + int(11 * index / max(1, len(selected))), 'Comprobando ' + name + '…')
            self._package_state(key, 'checking')
            if not winget:
                self._package_state(key, 'warning', 'WinGet no está disponible.'); continue
            try:
                code, output, reason = self._run_tool([winget, 'list', '--id', package, '--exact', '--source', 'winget', '--accept-source-agreements', '--disable-interactivity'], timeout=20)
                if reason == 'omitido': self._package_state(key, 'skipped'); continue
                if code == 0 and package.lower() in output.lower():
                    self._package_state(key, 'available', 'Ya está instalado.'); continue
                self._package_state(key, 'installing')
                self._progress(self.state['progress'], 'Instalando ' + name + '…')
                reviewed=self.catalog.snapshot()['items'].get(key,{})
                version_args=['--version',reviewed['version']] if reviewed.get('version') else []
                code, output, reason = self._run_tool([winget, 'install',*version_args, '--id', package, '--exact', '--source', 'winget', '--scope', 'user', '--no-upgrade', '--silent', '--accept-source-agreements', '--accept-package-agreements', '--disable-interactivity'])
                if reason == 'omitido': self._package_state(key, 'skipped', 'Preparación interrumpida. Revisa esta herramienta antes de usarla.'); continue
                if code == 0 or (code & 0xffffffff) == 0x8A15002B:
                    self._package_state(key, 'available', 'Disponible.'); continue
                detail = 'El paquete no admite instalación por usuario.' if (code & 0xffffffff) == 0x8A150010 else reason or 'WinGet no pudo completar la preparación (' + hex(code & 0xffffffff) + ').'
                self._package_state(key, 'warning', detail)
                with self.lock: self.state['warnings'].append(name + ': ' + detail + ' Puedes prepararlo después desde Ajustes.')
            except (OSError, subprocess.SubprocessError) as exc:
                self._package_state(key, 'warning', str(exc)[:180])
                with self.lock: self.state['warnings'].append(name + ': no se pudo completar la preparación.')

    @staticmethod
    def _rename_directory(source,destination):
        # Windows antivirus/indexers can briefly retain a handle after a copy.
        for attempt in range(12):
            try:source.rename(destination);return
            except PermissionError:
                if attempt==11:raise PermissionError('Windows mantiene abierta la carpeta de instalación. Cierra Lumen y vuelve a intentarlo: '+str(destination))
                time.sleep(.2)

    def _install(self, options):
        staging = None
        try:
            target = self.target.expanduser().resolve()
            if target == Path(target.anchor) or len(target.parts) < 3 or target.is_symlink():
                raise ValueError('Selecciona una carpeta de instalación válida.')
            target.mkdir(parents=True, exist_ok=True)
            destination = target / ('app-' + VERSION)
            staging = Path(tempfile.mkdtemp(prefix='.install-', dir=target))
            files = [p for p in self.payload.rglob('*') if p.is_file()]
            total = sum(p.stat().st_size for p in files)
            if shutil.disk_usage(target).free < total * 2 + 50_000_000:
                raise ValueError('No hay espacio suficiente para instalar Lumen.')
            copied = 0
            for file in files:
                if file.is_symlink() or not file.resolve().is_relative_to(self.payload.resolve()):
                    raise ValueError('El paquete contiene un enlace no permitido.')
                relative = file.relative_to(self.payload)
                out = staging / relative; out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, out); copied += file.stat().st_size
                self._progress(round(copied / max(1, total) * 82), 'Preparando los archivos de Lumen…')
            backup = None
            if destination.exists():
                backup = target / ('app-' + VERSION + '-previous-' + str(time.time_ns()))
                self._rename_directory(destination,backup)
            try: self._rename_directory(staging,destination); staging = None
            except OSError:
                if backup and not destination.exists(): self._rename_directory(backup,destination)
                raise
            self.target = target
            self._progress(85, 'Preparando preferencias y accesos…')
            previous_manifest={}
            try:previous_manifest=json.loads((target/'installation.json').read_text(encoding='utf-8'))
            except (OSError,ValueError):pass
            directories=list(dict.fromkeys([*previous_manifest.get('directories',[]),*([previous_manifest['directory']] if previous_manifest.get('directory') else []),destination.name,*([backup.name] if backup else [])]))
            atomic_json(target / 'installation.json', {'version': VERSION, 'directory': destination.name, 'directories':directories, 'packages': options.get('packages', []), 'locale': options.get('locale', 'es')})
            # The app consumes this only if there is no profile yet.
            atomic_json(destination / 'first-launch.json', {'general.locale': options.get('locale', 'es')})
            if options.get('shortcuts', True): self._shortcuts(destination, options.get('desktop', False))
            if options.get('register', True): self._register(destination)
            self._install_tools(options.get('packages', []))
            self._progress(100, 'Lumen Studio está instalado.')
            with self.lock: self.state['status'] = 'finished'; self.state['phase'] = 'finished'
        except Exception as exc:
            with self.lock: self.state['status'] = 'error'; self.state['message'] = str(exc)
        finally:
            # Delete only this install's staging directory after resolving its parent.
            if staging and staging.is_dir() and staging.resolve().parent == self.target.resolve() and staging.name.startswith('.install-'):
                shutil.rmtree(staging)

    def _shortcuts(self, destination, desktop):
        if os.name != 'nt': return
        locations = [Path(os.environ['APPDATA']) / 'Microsoft/Windows/Start Menu/Programs/Lumen Studio.lnk']
        if desktop:
            # Ask Windows for the actual desktop, including OneDrive redirection.
            locations.append('DESKTOP')
        commands = ['$w = New-Object -ComObject WScript.Shell']
        for location in locations:
            name = "(Join-Path ([Environment]::GetFolderPath('Desktop')) 'Lumen Studio.lnk')" if location == 'DESKTOP' else ps_quote(location)
            commands += [f'$s = $w.CreateShortcut({name})', '$s.TargetPath = ' + ps_quote(destination / 'lumen.exe'), '$s.WorkingDirectory = ' + ps_quote(destination), '$s.Save()']
        subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', '\n'.join(commands)], check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)

    def _register(self, destination):
        if os.name != 'nt': return
        import winreg
        uninstaller = self.target / 'Uninstall-Lumen.exe'
        bundled = ROOT / 'Uninstall-Lumen.exe'
        if not bundled.is_file():
            bundled = Path(__file__).resolve().parent / 'dist/Uninstall-Lumen.exe'
        if not bundled.is_file():raise ValueError('Falta el desinstalador gráfico en el paquete.')
        shutil.copy2(bundled,uninstaller)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Uninstall\LumenStudio') as key:
            values = {'DisplayName': 'Lumen Studio', 'DisplayVersion': VERSION, 'Publisher': 'Lumen Studio', 'InstallLocation': str(destination), 'DisplayIcon': str(destination / 'lumen.exe'),
                'UninstallString': f'"{uninstaller}"'}
            for name, value in values.items(): winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)

    def launch(self):
        if self.status()['status'] != 'finished': raise ValueError('Completa la instalación antes de abrir Lumen.')
        path = self.target / ('app-' + VERSION) / 'lumen.exe'
        subprocess.Popen([str(path)], cwd=path.parent)
        self.window.destroy()
        return True

    def close(self):
        if self.status()['status'] == 'installing': return False
        self.window.destroy(); return True


class InstallerAPI:
    """Only these operations cross the native bridge; no Path, lock or Window objects."""
    def __init__(self, installer): self._installer = installer
    def info(self): return self._installer.info()
    def status(self): return self._installer.status()
    def package_sizes(self): return self._installer.catalog.start()
    def package_sizes_status(self): return self._installer.catalog.snapshot()
    def choose_directory(self): return self._installer.choose_directory()
    def start(self, options): return self._installer.start(options)
    def skip_tools(self): return self._installer.skip_tools()
    def launch(self): return self._installer.launch()
    def close(self): return self._installer.close()


class StaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
            self.send_error(403); return
        if self.path == '/': self.path = '/setup.html'
        return super().do_GET()
    def end_headers(self):
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
        self.send_header('X-Content-Type-Options', 'nosniff')
        super().end_headers()


def main():
    import webview
    api = Installer()
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(StaticHandler, directory=str(ROOT / 'web')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    api.window = webview.create_window('Instalar Lumen Studio 0.5.2 · R5', f'http://127.0.0.1:{server.server_port}/', js_api=InstallerAPI(api),
        width=1100, height=850, min_size=(850, 660), background_color='#F6F7FD')
    api.window.events.closing += lambda: False if api.status()['status'] == 'installing' else None
    try: webview.start()
    finally: server.shutdown(); server.server_close()


if __name__ == '__main__': main()
