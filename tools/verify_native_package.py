#!/usr/bin/env python3
"""Verify the generated manifest, executable and native GUI on its target OS."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.build_desktop import architecture,sha256
from backend.version import VERSION,REVISION


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--bundle',type=Path);args=parser.parse_args()
    prefix=f'Edryvo-{VERSION}-R{REVISION}'
    manifest=json.loads((ROOT/f'dist/{prefix}-{sys.platform}-{architecture()}-manifest.json').read_text(encoding='utf-8'))
    for item in manifest['outputs']:
        file=ROOT/'dist'/item['name'];assert file.stat().st_size==item['bytes'] and sha256(file)==item['sha256'],file
    if sys.platform=='win32':
        from PyInstaller.archive.readers import CArchiveReader
        installer=next(ROOT/'dist'/item['name'] for item in manifest['outputs'] if item['name'].endswith('-Windows-Setup.exe'))
        archive=CArchiveReader(str(installer))
        uninstaller='Uninstall-Edryvo.exe'
        assert uninstaller in archive.toc, 'Windows installer is missing its graphical uninstaller'
        assert hashlib.sha256(archive.extract(uninstaller)).hexdigest()==sha256(ROOT/'dist'/uninstaller)
    if sys.platform=='darwin':
        dmg=ROOT/'dist'/manifest['outputs'][0]['name'];subprocess.run(['hdiutil','verify',str(dmg)],check=True)
        with tempfile.TemporaryDirectory(prefix='lumen-dmg-mount-') as temp:
            subprocess.run(['hdiutil','attach',str(dmg),'-readonly','-nobrowse','-mountpoint',temp],check=True)
            try:
                assert (Path(temp)/'Applications').is_symlink()
                executable=Path(temp)/'Edryvo.app/Contents/MacOS/lumen-python'
                probe(executable,prefix)
            finally:subprocess.run(['hdiutil','detach',temp],check=True)
    else:
        bundle=args.bundle or ROOT/'dist/LumenStudio'
        probe(bundle/('lumen-python.exe' if sys.platform=='win32' else 'lumen-python'),prefix)


def probe(executable,prefix):
    report=ROOT/f'dist/{prefix}-{sys.platform}-{architecture()}-verification.json'
    env={**os.environ,'QT_QPA_PLATFORM':'xcb','QTWEBENGINE_CHROMIUM_FLAGS':'--disable-gpu','QTWEBENGINE_DISABLE_SANDBOX':'1'}
    subprocess.run([str(executable),'--python-child',str(ROOT/'tests/native_smoke_worker.py'),'--report',str(report)],env=env,check=True,timeout=180)
    result=json.loads(report.read_text(encoding='utf-8'));assert not result['errors'] and len(result['checks'])==4,result
    print('PASS installer integrity and actual packaged native GUI:',sys.platform,architecture(),flush=True)

if __name__=='__main__':main()
