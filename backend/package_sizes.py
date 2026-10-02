"""Download sizes from the exact WinGet installer and its declared dependencies.

Installed footprint and secondary bootstrapper downloads are not invented.
"""
from concurrent.futures import ThreadPoolExecutor
import copy
import json
import os
import re
import shutil
import subprocess
import threading
import time
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

LIMIT=500_000_000_000

def download_size(url):
    if urlsplit(url).scheme!='https':raise ValueError('El catálogo debe proporcionar una descarga HTTPS.')
    with urlopen(Request(url,method='HEAD',headers={'User-Agent':'LumenStudio/0.5.2','Accept-Encoding':'identity'}),timeout=18) as response:
        if urlsplit(response.geturl()).scheme!='https':raise ValueError('El distribuidor ha redirigido a una URL sin HTTPS.')
        length=response.headers.get('Content-Length')
        if not length or not length.isdigit():return None
        size=int(length)
        if size>LIMIT:raise ValueError('El paquete supera 500 GB.')
        return size

def inspect_package(package, seen=None):
    if not re.fullmatch(r'[A-Za-z0-9.-]+',package):raise ValueError('Identificador de paquete no válido.')
    seen=set() if seen is None else set(seen)
    if package in seen or len(seen)>=16:return {'package':package,'bytes':None,'note':'Dependencia compartida o circular.'}
    seen.add(package)
    winget=shutil.which('winget')
    if not winget:raise ValueError('WinGet no está disponible.')
    result=subprocess.run([winget,'show','--id',package,'--exact','--source','winget','--accept-source-agreements','--disable-interactivity'],capture_output=True,timeout=25,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    text=result.stdout.decode('utf-8','replace')
    if result.returncode:raise ValueError('El catálogo no ha devuelto un instalador compatible.')
    # WinGet localizes labels. The version and SHA-256-bearing installer block
    # are identified independently of the current Windows display language.
    version=re.search(r'(?im)^Version\s*[^\w\r\n]+\s*([^\r\n]+)',text)
    sha=re.search(r'(?im)^.*SHA256[^\r\n]*?([a-f0-9]{64})',text)
    urls=re.findall(r'https://[^\s<>]+',text[:sha.start()] if sha else '')
    if not urls or not version or not sha:raise ValueError('No se ha podido identificar la versión exacta y su URL de descarga.')
    version=version[1].strip();url=urls[-1]
    data={'package':package,'version':version,'url':url,'sha256':sha[1],'bytes':download_size(url),'dependencies':[],
          'installedBytes':None,'checkedAt':time.time(),'complete':False,'note':'El espacio instalado no está publicado por WinGet.'}
    try:
        import yaml
        manifest_url='https://raw.githubusercontent.com/microsoft/winget-pkgs/master/manifests/'+package[0].lower()+'/'+package.replace('.','/')+'/'+quote(version,safe='')+'/'+package+'.installer.yaml'
        with urlopen(Request(manifest_url,headers={'User-Agent':'LumenStudio/0.5.2'}),timeout=15) as response:
            raw=response.read(2_000_001)
        if len(raw)>2_000_000:raise ValueError('Manifiesto demasiado grande.')
        manifest=yaml.safe_load(raw)
        selected=next((x for x in manifest.get('Installers',[]) if x.get('InstallerUrl')==url and x.get('InstallerSha256','').lower()==sha[1].lower()),None)
        if selected is None:raise ValueError('La variante del manifiesto no coincide con WinGet.')
        declared={**manifest.get('Dependencies',{}),**selected.get('Dependencies',{})}
        deps=declared.get('PackageDependencies',[])
        if len(deps)>16:raise ValueError('Demasiadas dependencias.')
        for dependency in deps:
            ident=dependency['PackageIdentifier']
            try:item=inspect_package(ident,seen)
            except Exception as exc:item={'package':ident,'bytes':None,'note':str(exc)}
            data['dependencies'].append(item)
        data['architecture']=selected.get('Architecture')
        data['complete']=data['bytes'] is not None and all(d.get('complete') for d in data['dependencies']) and not any(declared.get(k) for k in ('ExternalDependencies','WindowsFeatures','WindowsLibraries'))
    except Exception as exc:data['note']='Dependencias sin verificar: '+str(exc)[:220]
    if package in ('Rustlang.Rustup','Google.AndroidStudio','Microsoft.VisualStudio.2022.BuildTools'):
        data['complete']=False;data['note']='Este instalador descarga componentes adicionales según tu selección. Su total aún no está publicado; no se cuenta como un total verificado.'
    data['knownDownloadBytes']=package_total([data])['bytes']
    return data

def package_total(items):
    known={};complete=True
    def visit(item):
        nonlocal complete
        if not item.get('complete'):complete=False
        key=(item.get('package'),item.get('version'))
        if key in known:return
        known[key]=item.get('bytes') or 0
        for child in item.get('dependencies',[]):visit(child)
    for item in items:visit(item)
    return {'bytes':sum(known.values()),'complete':complete,'packages':len(known)}

class PackageCatalog:
    def __init__(self,packages):self.packages=packages;self.items={};self.lock=threading.Lock();self.running=False
    def snapshot(self):
        with self.lock:return {'running':self.running,'items':copy.deepcopy(self.items)}
    def start(self):
        with self.lock:
            if self.running or self.items:return self.snapshot_unlocked()
            self.running=True
        threading.Thread(target=self._load,daemon=True).start()
        return self.snapshot()
    def snapshot_unlocked(self):return {'running':self.running,'items':copy.deepcopy(self.items)}
    def _load(self):
        def one(entry):
            key,(_,package)=entry
            try:item=inspect_package(package)
            except Exception as exc:item={'package':package,'bytes':None,'complete':False,'note':str(exc)}
            with self.lock:self.items[key]=item
        with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(one,self.packages.items()))
        with self.lock:self.running=False
