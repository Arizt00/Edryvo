"""Build an explicit, private Windows SDK payload from installed redistributable tools.

Never copies profiles, credentials or site-packages from the host. Downloads are
verified against the publisher's checksum. Keep this large payload out of Git.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

def fetch(url, destination, digest='', algorithm='sha256'):
    if destination.is_file() and digest and hashlib.new(algorithm, destination.read_bytes()).hexdigest() == digest:
        return
    part = destination.with_suffix(destination.suffix + '.part')
    h = hashlib.new(algorithm)
    with urllib.request.urlopen(url, timeout=60) as response, part.open('wb') as stream:
        while block := response.read(1024 * 1024):
            h.update(block); stream.write(block)
    if digest and h.hexdigest() != digest:raise ValueError('Checksum incorrecto: '+destination.name)
    part.replace(destination)
    print('VERIFIED', destination.name, destination.stat().st_size, h.hexdigest(), flush=True)

def copy(source, target):
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__','*.pyc','.git'))
    elif source.is_file():
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    else:raise FileNotFoundError(source)

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'sdk/foundation')
    p.add_argument('--ncc',type=Path,required=True);a=p.parse_args()
    if os.name!='nt':raise SystemExit('Prepara un payload propio de la plataforma; este constructor es Windows x64.')
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);cache=out/'downloads';cache.mkdir(exist_ok=True)
    tools={};components=[]
    def register(ident,rel):
        if not (out/rel).is_file():raise FileNotFoundError(rel)
        tools[ident]=rel
    # A complete CPython installation, excluding the host's third-party packages.
    py=Path(sys.base_prefix);target=out/'python'
    target.mkdir(exist_ok=True)
    for file in py.iterdir():
        if file.is_file() and (file.suffix.lower() in ('.exe','.dll','.txt') or file.name=='LICENSE.txt'):copy(file,target/file.name)
    for name in ('DLLs','include','libs','tcl'):
        if (py/name).exists():copy(py/name,target/name)
    shutil.copytree(py/'Lib',target/'Lib',dirs_exist_ok=True,ignore=shutil.ignore_patterns('site-packages','__pycache__','*.pyc','test'))
    register('python','python/python.exe')
    environment = {**os.environ, 'PYTHONNOUSERSITE':'1'}
    subprocess.run([tools_path:=str(out/tools['python']),'-m','ensurepip','--upgrade','--default-pip'],check=True,env=environment)
    subprocess.run([tools_path,'-m','pip','install','unicorn==2.1.4','capstone==5.0.6','pyelftools==0.32','pycdlib==1.14.0',
                    'requests','pytest','numpy','pandas','matplotlib','python-lsp-server'],check=True,env=environment)
    subprocess.run([tools_path,'-m','pip','check'],check=True,env=environment)
    frozen = subprocess.run([tools_path,'-m','pip','freeze'],check=True,capture_output=True,text=True,env=environment).stdout
    (out/'python/requirements-bundled.txt').write_text(frozen,encoding='utf-8')
    components.append({'id':'python','version':sys.version.split()[0],'license':'PSF-2.0','includes':['stdlib','pip','venv','pytest','requests','numpy','pandas','matplotlib','python-lsp-server']})
    # LLVM provides five integrated assemblers. MinGW supplies the native CRT,
    # headers, standard libraries and GCC; all installed prefix files are kept.
    llvm=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'LLVM'
    for file in ('clang.exe','clang++.exe','clangd.exe','llvm-objcopy.exe','llvm-objdump.exe','lld.exe','ld.lld.exe','lld-link.exe'):
        copy(llvm/'bin'/file,out/'llvm/bin'/file)
        register(file[:-4],'llvm/bin/'+file)
    for name in ('lib/clang','share'):
        if (llvm/name).exists():copy(llvm/name,out/'llvm'/name)
    mingw=Path('C:/msys64/ucrt64');copy(mingw,out/'mingw')
    for name in ('gcc','g++','gdb','cmake','ninja','as','ar'):
        if (out/f'mingw/bin/{name}.exe').exists():register(name,f'mingw/bin/{name}.exe')
    components.extend([{'id':'llvm','license':'Apache-2.0 WITH LLVM-exception','includes':['x86','x86_64','arm','arm64','riscv64']},
                       {'id':'gcc','license':'GPL-3.0 with GCC Runtime Library Exception','includes':['C standards','C++ standards','headers','CRT','libstdc++','GDB']}])
    java=Path(shutil.which('javac')).resolve().parents[1];copy(java,out/'java')
    for name in ('java','javac','jar','javadoc','jshell'):register(name,f'java/bin/{name}.exe')
    components.append({'id':'java','license':'GPL-2.0 WITH Classpath-exception','includes':['JDK','standard modules','compiler','jar','javadoc','jshell']})
    git=Path(shutil.which('git')).resolve().parents[1];copy(git,out/'bash')
    register('bash','bash/bin/bash.exe');register('git','bash/cmd/git.exe')
    components.append({'id':'bash','license':'GPL-3.0','includes':['Git Bash','MSYS POSIX tools','Git']})
    copy(a.ncc,out/'nc/ncc.exe');register('ncc','nc/ncc.exe')
    components.append({'id':'nc','license':'See publisher notices','includes':['NCC']})
    node=Path(shutil.which('node'));copy(node,out/'node/node.exe');register('node','node/node.exe')
    for name_license in ('LICENSE','LICENSE.txt'):
        if (node.parent/name_license).is_file():copy(node.parent/name_license,out/'node'/name_license)
    components.append({'id':'node','version':subprocess.check_output([str(node),'--version'],text=True).strip(),
                       'license':'MIT and bundled third-party notices','includes':['VSIX extension host','JavaScript runtime']})
    docker=Path(shutil.which('docker'));copy(docker,out/'docker/docker.exe');register('docker','docker/docker.exe')
    components.append({'id':'docker','license':'Apache-2.0','includes':['CLI'],'note':'El motor Docker se conecta por separado; no se redistribuye Docker Desktop.'})
    # Official Arch cloud image: persistent overlay + NoCloud serial console.
    base='https://geo.mirror.pkgbuild.com/images/latest/'
    listing=urllib.request.urlopen(base,timeout=30).read().decode()
    name=re.findall(r'href="(Arch-Linux-x86_64-cloudimg-[0-9.]+\.qcow2)"',listing)[-1]
    digest=urllib.request.urlopen(base+name+'.SHA256',timeout=30).read().decode().split()[0]
    qname='qemu-w64-setup-20260811.exe';qbase='https://qemu.weilnetz.de/w64/'
    qdigest=urllib.request.urlopen(qbase+qname.replace('.exe','.sha512'),timeout=30).read().decode().split()[0]
    (out/'images').mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda item:fetch(*item),[(base+name,out/'images'/name,digest,'sha256'),(qbase+qname,cache/qname,qdigest,'sha512')]))
    seven=Path('C:/Program Files/7-Zip/7z.exe')
    subprocess.run([str(seven),'x',str(cache/qname),'-o'+str(out/'qemu'),'-y'],check=True,stdout=subprocess.DEVNULL)
    for name_tool in ('qemu-system-x86_64','qemu-img'):register(name_tool,f'qemu/{name_tool}.exe')
    components.append({'id':'qemu','license':'GPL-2.0','source':qbase,'includes':['headless virtual machine','qemu-img']})
    components.append({'id':'arch','license':'Per-package open-source licences','file':'images/'+name,'sha256':digest,'source':base+name})
    # Maven/Gradle project dependencies are resolved by these actual tools.
    for ident,url,filename,folder,rel in (
        ('mvn','https://archive.apache.org/dist/maven/maven-3/3.9.11/binaries/apache-maven-3.9.11-bin.zip','maven.zip','maven','apache-maven-3.9.11/bin/mvn.cmd'),
        ('gradle','https://services.gradle.org/distributions/gradle-8.14.3-bin.zip','gradle.zip','gradle','gradle-8.14.3/bin/gradle.bat')):
        checksum_url=url+('.sha512' if ident=='mvn' else '.sha256')
        digest=urllib.request.urlopen(checksum_url,timeout=30).read().decode().split()[0]
        fetch(url,cache/filename,digest,'sha512' if ident=='mvn' else 'sha256')
        subprocess.run([str(seven),'x',str(cache/filename),'-o'+str(out/folder),'-y'],check=True,stdout=subprocess.DEVNULL)
        register(ident,folder+'/'+rel)
        components.append({'id':ident,'license':'Apache-2.0','source':url})
    from datetime import datetime,timezone
    data={'schema':1,'platform':sys.platform,'created':datetime.now(timezone.utc).isoformat(),'tools':tools,'components':components}
    (out/'tool-index.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    print('FOUNDATION_READY',out,flush=True)

if __name__=='__main__':main()
