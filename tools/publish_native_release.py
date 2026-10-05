#!/usr/bin/env python3
"""Publish native CI artifacts only after their reports and digests agree."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.build_desktop import sha256
from backend.version import VERSION,REVISION,RELEASE_TAG


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,required=True);args=parser.parse_args()
    directory=args.directory.resolve();prefix=f'Zenit-{VERSION}-R{REVISION}';commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    manifests=list(directory.glob('*-manifest.json'));assert len(manifests)==4,'Expected Windows, Linux and two macOS manifests'
    expected={('win32','x86_64'),('linux','x86_64'),('darwin','arm64'),('darwin','x86_64')}
    files=[]
    for file in manifests:
        manifest=json.loads(file.read_text());key=(manifest['platform'],manifest['architecture']);assert key in expected,key;expected.remove(key)
        assert manifest['sourceCommit']==commit and manifest['version']==RELEASE_TAG,'Unexpected source/version'
        report=file.with_name(file.name.replace('-manifest.json','-verification.json'))
        verified=json.loads(report.read_text());assert verified['revision']==REVISION and not verified['errors'] and len(verified['checks'])==4,'Native verification incomplete'
        for item in manifest['outputs']:
            asset=directory/item['name'];assert asset.parent==directory and asset.is_file()
            assert asset.stat().st_size==item['bytes'] and sha256(asset)==item['sha256'],'Asset integrity mismatch'
            files.append(asset)
        files.extend([file,report,file.with_name(file.name.replace('-manifest.json','-SHA256.txt'))])
    assert not expected
    body=directory/'release-notes.md'
    body.write_text((ROOT/'docs/PREVIEW_053_R2.md').read_text(encoding='utf-8'),encoding='utf-8')
    result=subprocess.run(['gh','release','view',RELEASE_TAG,'--json','targetCommitish,assets'],capture_output=True,text=True)
    if result.returncode:
        subprocess.run(['gh','release','create',RELEASE_TAG,'--target',commit,'--title',f'Zénit {VERSION} · Preview R{REVISION} · Windows, Linux y macOS','--prerelease','--notes-file',str(body)],check=True)
    else:
        existing=json.loads(result.stdout)
        # Never overwrite a released binary or silently retarget a published tag.
        assert existing['targetCommitish']==commit,'Existing release targets another commit'
        assert not existing['assets'],'Existing assets are preserved; use a new revision'
    subprocess.run(['gh','release','upload',RELEASE_TAG,*map(str,files)],check=True)
    print('Published',RELEASE_TAG,len(files),'native installer/report files',flush=True)

if __name__=='__main__':main()
