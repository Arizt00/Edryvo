#!/usr/bin/env python3
"""Build the current platform's standalone bundle; optional native installer.

Dependencies are explicit. This script never acquires certificates, silently
installs build tools, signs a release or pretends to cross-compile.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import platform
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description='Construir Lumen en el sistema de destino')
    p.add_argument('--installer',action='store_true');p.add_argument('--plan',action='store_true');p.add_argument('--require-assets',action='store_true');a=p.parse_args()
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean',str(ROOT/'packaging/lumen.spec')]
    print(json.dumps({'platform':sys.platform,'machine':platform.machine(),'argv':command,'signed':False,'installerRequested':a.installer},indent=2))
    if a.plan:return 0
    if not importlib.util.find_spec('PyInstaller') or not importlib.util.find_spec('webview'):
        p.error('Instala requirements-build.txt en un entorno virtual de construcción antes de continuar.')
    if a.require_assets:
        for path in ('monaco/vs/loader.js','babylon/babylon.js','xterm/xterm.js','xterm-fit/addon-fit.js','three/three.core.js'):
            if not (ROOT/'web/vendor'/path).is_file():p.error('Falta '+path+'. Ejecuta tools/setup_assets.py.')
    subprocess.run(command,cwd=ROOT,check=True)
    outputs=[]
    if a.installer:
        if sys.platform=='win32':
            subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean',str(ROOT/'packaging/uninstaller.spec')],check=True,cwd=ROOT)
            subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean',str(ROOT/'packaging/installer.spec')],check=True,cwd=ROOT)
            outputs=list((ROOT/'dist').glob('LumenStudio-*-Windows-Setup.exe'))
        elif sys.platform=='darwin':
            out=ROOT/'dist/LumenStudio-0.5.2-macOS.dmg'
            subprocess.run(['hdiutil','create','-volname','Lumen Studio','-srcfolder',str(ROOT/'dist/Lumen Studio.app'),'-ov','-format','UDZO',str(out)],check=True);outputs=[out]
        else:
            out=ROOT/('dist/LumenStudio-0.5.2-linux-'+platform.machine()+'.tar.gz')
            with tarfile.open(out,'w:gz') as archive:
                archive.add(ROOT/'dist/LumenStudio',arcname='LumenStudio')
                archive.add(ROOT/'packaging/linux/install-bundle.sh',arcname='install.sh')
            outputs=[out]
    manifest={'version':'0.5.2','platform':sys.platform,'architecture':platform.machine(),'signed':False,'outputs':[{'name':x.name,'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in outputs]}
    (ROOT/'dist/BUILD_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Bundle generado. Las firmas, notarización y pruebas en destino siguen siendo pasos explícitos de publicación.')
    return 0
if __name__=='__main__':raise SystemExit(main())
