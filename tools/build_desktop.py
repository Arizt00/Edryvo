#!/usr/bin/env python3
"""Build and package on the target OS. macOS signing/notarization is separate."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.version import VERSION, REVISION, RELEASE_TAG


def sha256(file):
    digest=hashlib.sha256()
    with file.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def architecture():
    machine=platform.machine().lower()
    return {'amd64':'x86_64','x64':'x86_64','aarch64':'arm64'}.get(machine,machine)


def collect_licenses():
    """Record actual dependency versions and preserve their distributed licenses."""
    destination=ROOT/'licenses/native-python'
    destination.mkdir(parents=True,exist_ok=True)
    inventory=[]
    for distribution in importlib.metadata.distributions():
        name=distribution.metadata.get('Name','unknown')
        folder=destination/name.lower().replace('_','-')
        files=[]
        for relative in distribution.files or []:
            if '..' in relative.parts or not any(part.lower().startswith(('license','copying','notice')) for part in relative.parts):continue
            source=Path(distribution.locate_file(relative))
            if not source.is_file() or source.stat().st_size>2_000_000:continue
            target=folder/Path(*relative.parts[1:])
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)
            files.append(target.relative_to(destination).as_posix())
        inventory.append({'name':name,'version':distribution.version,'license':distribution.metadata.get('License-Expression') or distribution.metadata.get('License',''),'files':files})
    (destination/'PACKAGE_INVENTORY.json').write_text(json.dumps(sorted(inventory,key=lambda x:x['name'].lower()),ensure_ascii=False,indent=2),encoding='utf-8')


def prepare_mac_icon():
    from PIL import Image
    target=ROOT/'packaging/macos/lumen.icns';target.parent.mkdir(parents=True,exist_ok=True)
    with Image.open(ROOT/'web/assets/lumen.ico') as image:
        image.convert('RGBA').resize((1024,1024),Image.Resampling.LANCZOS).save(target,format='ICNS')


def desktop_entry(executable,icon):
    return '[Desktop Entry]\nType=Application\nName=Zénit\nComment=Editor, Lantern Live y Forge\nExec="'+executable+'"\nIcon='+icon+'\nTerminal=false\nCategories=Development;IDE;\nStartupWMClass=Zénit\n'


def linux_packages(bundle,prefix):
    if not shutil.which('dpkg-deb'):raise RuntimeError('dpkg-deb es necesario para crear el instalador .deb.')
    arch={'x86_64':'amd64','arm64':'arm64'}.get(architecture())
    if not arch:raise RuntimeError('Arquitectura Linux no admitida.')
    deb=ROOT/f'dist/{prefix}-Linux-{arch}.deb'
    with tempfile.TemporaryDirectory(prefix='lumen-deb-') as temp:
        stage=Path(temp);install=stage/'opt/zenit'
        shutil.copytree(bundle,install,symlinks=True)
        control=stage/'DEBIAN';control.mkdir()
        kib=sum(p.stat().st_size for p in install.rglob('*') if p.is_file())//1024
        libc=__import__('platform').libc_ver()[1] or '2.39'
        (control/'control').write_text(f'Package: zenit\nVersion: {VERSION}~preview.{REVISION}\nConflicts: lumen-studio\nReplaces: lumen-studio\nSection: devel\nPriority: optional\nArchitecture: {arch}\nMaintainer: Zénit <zenit@users.noreply.github.com>\nInstalled-Size: {kib}\nDepends: libc6 (>= {libc}), libstdc++6, libgl1, libopengl0, libegl1, libxkbcommon0, libxkbcommon-x11-0, libxcb-cursor0, libxcb-xinerama0, libxcb-icccm4, libxcb-keysyms1, libxcb-image0, libxcb-render-util0, libnss3, libnspr4, libasound2 | libasound2t64, libxcomposite1, libxdamage1, libxrandr2, libxtst6, libxi6, libdbus-1-3, xdg-utils\nHomepage: https://github.com/Arizt00/Zenit\nDescription: Zénit IDE preview\n Editor Monaco, Lantern Live, Forge y ventanas nativas independientes.\n Incluye su runtime; los SDK de proyectos se preparan aparte.\n',encoding='utf-8')
        bin_dir=stage/'usr/bin';bin_dir.mkdir(parents=True)
        (bin_dir/'zenit').write_text('#!/bin/sh\nexec /opt/zenit/zenit "$@"\n',encoding='utf-8');(bin_dir/'zenit').chmod(0o755);(bin_dir/'lumen').symlink_to('zenit')
        apps=stage/'usr/share/applications';apps.mkdir(parents=True)
        (apps/'zenit.desktop').write_text(desktop_entry('/opt/zenit/zenit','zenit'),encoding='utf-8')
        icons=stage/'usr/share/icons/hicolor/scalable/apps';icons.mkdir(parents=True)
        shutil.copy2(ROOT/'web/assets/lumen.svg',icons/'zenit.svg')
        notices=stage/'usr/share/doc/zenit';notices.mkdir(parents=True)
        shutil.copy2(ROOT/'LICENSE',notices/'copyright')
        subprocess.run(['dpkg-deb','--root-owner-group','--build',str(stage),str(deb)],check=True)
    portable=ROOT/f'dist/{prefix}-Linux-{arch}.tar.gz'
    with tarfile.open(portable,'w:gz') as archive:
        archive.add(bundle,arcname='Zenit')
        info=archive.gettarinfo(str(ROOT/'packaging/linux/install-bundle.sh'),arcname='install.sh');info.mode=0o755
        with (ROOT/'packaging/linux/install-bundle.sh').open('rb') as stream:archive.addfile(info,stream)
    return [deb,portable]


def mac_package(prefix):
    output=ROOT/f'dist/{prefix}-macOS-{architecture()}.dmg'
    with tempfile.TemporaryDirectory(prefix='lumen-dmg-') as temp:
        stage=Path(temp)
        shutil.copytree(ROOT/'dist/Zenit.app',stage/'Zenit.app',symlinks=True)
        (stage/'Applications').symlink_to('/Applications',target_is_directory=True)
        (stage/'LEEME.txt').write_text('Zénit '+VERSION+f' R{REVISION}\n\nArrastra Zenit.app a Applications.\nIncluye Python; prepara los SDK de tus proyectos por separado.\nPreview sin firma de Developer ID ni notarización de Apple.\nSi macOS bloquea esta preview, revisa Privacidad y seguridad tras verificar la descarga.\nNo es necesario desactivar Gatekeeper.\n',encoding='utf-8')
        subprocess.run(['hdiutil','create','-volname','Zénit','-srcfolder',str(stage),'-ov','-format','UDZO',str(output)],check=True)
    return [output]


def main():
    parser=argparse.ArgumentParser(description='Construir Zénit en el sistema de destino')
    parser.add_argument('--installer',action='store_true')
    parser.add_argument('--plan',action='store_true')
    parser.add_argument('--require-assets',action='store_true')
    parser.add_argument('--package-only',action='store_true',help='Empaquetar un bundle ya construido en este sistema')
    args=parser.parse_args()
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean',str(ROOT/'packaging/lumen.spec')]
    print(json.dumps({'platform':sys.platform,'architecture':architecture(),'version':RELEASE_TAG,'argv':command,'signed':False,'installerRequested':args.installer},indent=2),flush=True)
    if args.plan:return 0
    if not args.package_only:
        if not importlib.util.find_spec('PyInstaller') or not importlib.util.find_spec('webview'):parser.error('Instala requirements-build.txt en un entorno virtual de construcción.')
        if args.require_assets:
            for path in ('monaco/vs/loader.js','babylon/babylon.js','xterm/xterm.js','xterm-fit/addon-fit.js','three/three.core.js'):
                if not (ROOT/'web/vendor'/path).is_file():parser.error('Falta '+path+'. Ejecuta tools/setup_assets.py.')
        collect_licenses()
        if sys.platform=='darwin':prepare_mac_icon()
        subprocess.run(command,cwd=ROOT,check=True)
    outputs=[];prefix=f'Zenit-{VERSION}-R{REVISION}'
    if args.installer:
        if sys.platform=='win32':
            for name in ('uninstaller','installer'):
                subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean',str(ROOT/f'packaging/{name}.spec')],check=True,cwd=ROOT)
            output=ROOT/f'dist/{prefix}-Windows-Setup.exe'
            if not output.is_file():raise RuntimeError('No se generó el instalador .exe.')
            outputs=[output]
            portable=ROOT/f'dist/{prefix}-Windows-Portable.zip'
            with zipfile.ZipFile(portable,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
                for file in (ROOT/'dist/Zenit').rglob('*'):
                    if file.is_file():archive.write(file,'Zenit/'+file.relative_to(ROOT/'dist/Zenit').as_posix())
            outputs.append(portable)
        elif sys.platform=='darwin':outputs=mac_package(prefix)
        elif sys.platform.startswith('linux'):outputs=linux_packages(ROOT/'dist/Zenit',prefix)
        else:parser.error('Sistema de distribución no admitido.')
    try:commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    except (OSError,subprocess.SubprocessError):commit=None
    manifest={'version':RELEASE_TAG,'platform':sys.platform,'architecture':architecture(),'sourceCommit':commit,'signed':False,'outputs':[{'name':x.name,'bytes':x.stat().st_size,'sha256':sha256(x)} for x in outputs]}
    name=f'{prefix}-{sys.platform}-{architecture()}'
    (ROOT/f'dist/{name}-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (ROOT/f'dist/{name}-SHA256.txt').write_text(''.join(f"{x['sha256']}  {x['name']}\n" for x in manifest['outputs']),encoding='utf-8')
    print('Paquetes nativos generados con manifiesto y SHA-256.',flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
