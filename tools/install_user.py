#!/usr/bin/env python3
"""Per-user source installer. No administrative changes or embedded credentials.

Installs a private Python environment and native webview dependencies. This is
not a self-contained frozen executable; use build_desktop.py for those bundles.
"""
from __future__ import annotations
import argparse
import json
import os
import plistlib
import shlex
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
VERSION='0.5.2'
MARKER='.lumen-source-install.json'

def locations(platform_name=None,home=None):
    platform_name=platform_name or sys.platform;home=Path(home or Path.home())
    if platform_name=='win32':
        base=Path(os.environ.get('LOCALAPPDATA',home/'AppData/Local'))
        return base/'Programs/LumenStudio',base/'Programs/LumenStudio/bin'
    if platform_name=='darwin':return home/'Library/Application Support/LumenStudio/application',home/'.local/bin'
    return home/'.local/share/lumen-studio/application',home/'.local/bin'

def write_executable(path,text):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8');path.chmod(0o755)

def main(argv=None):
    p=argparse.ArgumentParser(description='Instalador local de Lumen 0.4. No requiere administrador.')
    p.add_argument('--plan',action='store_true',help='Mostrar las rutas sin modificar el equipo')
    p.add_argument('--target',type=Path,help='Carpeta nueva alternativa de instalación')
    p.add_argument('--skip-dependencies',action='store_true',help='Solo instalación base, sin ventana nativa ni pip; también útil para QA sin red')
    p.add_argument('--skip-assets',action='store_true',help='No descargar Monaco, Babylon o xterm')
    p.add_argument('--copilot',action='store_true',help='Instalar además el SDK oficial de Copilot (Python 3.11+)')
    p.add_argument('--launch',action='store_true',help='Abrir la aplicación al terminar')
    a=p.parse_args(argv)
    if sys.version_info<(3,10):p.error('Se necesita Python 3.10 o posterior; Copilot necesita 3.11 o posterior.')
    if a.copilot and sys.version_info<(3,11):p.error('Copilot necesita Python 3.11 o posterior.')
    appbase,binbase=locations();appbase=(a.target or appbase).expanduser().resolve()
    if a.target:binbase=appbase/'bin'
    destination=appbase/('versions/'+VERSION);python=destination/('.venv/Scripts/python.exe' if os.name=='nt' else '.venv/bin/python')
    plan={'version':VERSION,'application':str(destination),'launcherDirectory':str(binbase),'python':str(python),'nativeDependencies':not a.skip_dependencies,'downloadAssets':not a.skip_assets,'copilotSDK':a.copilot}
    print(json.dumps(plan,ensure_ascii=False,indent=2),flush=True)
    if a.plan:return 0
    if destination.exists():p.error('Esta versión ya existe en destino. Conserva tus datos y utiliza otra carpeta o desinstala esa copia antes de repetir.')
    if destination==ROOT or ROOT.is_relative_to(destination) or destination.is_relative_to(ROOT):p.error('La instalación no puede sobrescribir el código fuente.')
    destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copytree(ROOT,destination,ignore=shutil.ignore_patterns('.git','.venv','__pycache__','*.pyc','dist','build','node_modules','*.log'))
    (destination/MARKER).write_text(json.dumps(plan,indent=2),encoding='utf-8')
    try:
        venv.EnvBuilder(with_pip=not a.skip_dependencies).create(destination/'.venv')
        if not a.skip_dependencies:
            subprocess.run([str(python),'-m','pip','install','-r',str(destination/'requirements-desktop.txt')],check=True)
            if a.copilot:subprocess.run([str(python),'-m','pip','install','-r',str(destination/'requirements-copilot.txt')],check=True)
        if not a.skip_assets:
            result=subprocess.run([str(python),str(destination/'tools/setup_assets.py')])
            if result.returncode:print('Dependencias visuales pendientes: el editor integrado sigue disponible.',flush=True)
    except (OSError,subprocess.CalledProcessError) as error:
        print(f'Instalación incompleta: {error}\nLa carpeta se conserva para diagnosticar o desinstalar. No se ha cambiado el Python global.',file=sys.stderr)
        return 1
    binbase.mkdir(parents=True,exist_ok=True)
    launcher=binbase/('lumen.cmd' if os.name=='nt' else 'lumen')
    if os.name=='nt':
        # Installation paths are quoted. Reject cmd expansion characters rather
        # than embedding an unsafe path in a command launcher.
        if any(c in str(destination) for c in '%!\r\n'):raise ValueError('Usa una ruta sin %, ! ni saltos de línea.')
        launcher.write_text('@echo off\r\n"'+str(python)+'" "'+str(destination/'app.py')+'" %*\r\n',encoding='utf-8')
        desktop=binbase/'Lumen Studio.cmd';desktop.write_text('@echo off\r\n"'+str(python)+'" "'+str(destination/'app.py')+'" --desktop %*\r\n',encoding='utf-8')
        # Own Start menu directory; no registry or system PATH modifications.
        start=Path(os.environ.get('APPDATA',Path.home()/'AppData/Roaming'))/'Microsoft/Windows/Start Menu/Programs/Lumen Studio'
        if not a.target:
            start.mkdir(parents=True,exist_ok=True);shutil.copy2(desktop,start/desktop.name)
    else:
        write_executable(launcher,'#!/bin/sh\nexec '+shlex.quote(str(python))+' '+shlex.quote(str(destination/'app.py'))+' "$@"\n')
        desktop=binbase/'lumen-studio'
        write_executable(desktop,'#!/bin/sh\nexec '+shlex.quote(str(python))+' '+shlex.quote(str(destination/'app.py'))+' --desktop "$@"\n')
        if not a.target and sys.platform=='darwin':
            bundle=Path.home()/'Applications/Lumen Studio.app';contents=bundle/'Contents';(contents/'MacOS').mkdir(parents=True,exist_ok=True)
            write_executable(contents/'MacOS/lumen',desktop.read_text())
            with (contents/'Info.plist').open('wb') as f:plistlib.dump({'CFBundleExecutable':'lumen','CFBundleIdentifier':'studio.lumen.ide','CFBundleName':'Lumen Studio','CFBundleVersion':VERSION,'CFBundleShortVersionString':VERSION,'CFBundlePackageType':'APPL'},f)
        elif not a.target:
            entry=Path.home()/'.local/share/applications/lumen-studio.desktop';entry.parent.mkdir(parents=True,exist_ok=True)
            # Desktop entries have their own quoting rules, not shell quoting.
            escaped=str(desktop).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')
            entry.write_text('[Desktop Entry]\nType=Application\nName=Lumen Studio\nComment=Entorno de desarrollo local\nExec="'+escaped+'"\nTerminal=false\nCategories=Development;IDE;\n',encoding='utf-8')
    plan['launchers']=[str(launcher),str(desktop)]
    (destination/MARKER).write_text(json.dumps(plan,indent=2),encoding='utf-8')
    print(f'\nInstalado: {destination}\nAbrir: {desktop}\nComandos: {launcher} focus\nDesinstalar: {sys.executable} "{destination}/tools/uninstall_user.py"\n')
    print('El instalador no altera PATH. Usa la ruta mostrada o añade su carpeta bin a tu PATH de usuario. Los proyectos y las preferencias se conservan al desinstalar.')
    if a.launch:subprocess.Popen([str(python),str(destination/'app.py'),'--desktop'])
    return 0

if __name__=='__main__':raise SystemExit(main())
