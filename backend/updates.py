"""GitHub release checks and verified background downloads for Edryvo desktop."""
import copy
import json
import re
import platform
import sys
import threading
import time
import urllib.request

from .version import RELEASE_TAG,REPOSITORY
CURRENT=RELEASE_TAG
API='https://api.github.com/repos/'+REPOSITORY+'/releases?per_page=15'


def version_key(tag):
    m=re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(?:-preview\.(\d+))?',str(tag))
    return (*map(int,m.groups()[:3]),int(m[4]) if m[4] else 1_000_000) if m else None


def package_matches(name, system=None, machine=None):
    """Never offer a Windows installer to Linux/macOS or the wrong CPU build."""
    system=system or sys.platform
    machine=(machine or platform.machine()).lower()
    architecture={'amd64':'x86_64','x64':'x86_64','aarch64':'arm64'}.get(machine,machine)
    if system=='win32':
        return architecture=='x86_64' and bool(re.fullmatch(r'(?:Edryvo|LumenStudio)[-_].*(?:Setup|Installer|Instalador).*\.exe',name,re.I))
    if system=='darwin':
        return bool(re.fullmatch(r'(?:Edryvo|LumenStudio)[-_].*-macOS-'+re.escape(architecture)+r'\.dmg',name,re.I))
    if system.startswith('linux'):
        arch={'x86_64':'amd64','arm64':'arm64'}.get(architecture,architecture)
        return bool(re.fullmatch(r'(?:Edryvo|LumenStudio)[-_].*-Linux-'+re.escape(arch)+r'\.deb',name,re.I))
    return False


def update_asset(releases, current=CURRENT, system=None, machine=None):
    if not isinstance(releases,list):raise ValueError('GitHub no devolvió una lista de versiones.')
    newer=[r for r in releases if isinstance(r,dict) and not r.get('draft') and version_key(r.get('tag_name')) and version_key(r['tag_name'])>version_key(current)]
    for release in sorted(newer,key=lambda r:version_key(r['tag_name']),reverse=True):
        for asset in release.get('assets',[]):
            if isinstance(asset,dict) and isinstance(asset.get('name'),str) and package_matches(asset['name'],system,machine):
                digest=asset.get('digest','')
                url=asset.get('browser_download_url','')
                if not isinstance(digest,str) or not re.fullmatch(r'sha256:[a-f0-9]{64}',digest):continue
                if not isinstance(url,str) or not any(url.startswith('https://github.com/'+repo+'/releases/download/') for repo in (REPOSITORY,'Arizt00/LumenStudio')):continue
                if type(asset.get('size')) is not int or not 0<asset['size']<4_000_000_000:continue
                return {'version':release['tag_name'],'name':asset['name'],'url':url,'sha256':digest[7:],'size':asset['size'],'release':release['html_url']}
    return None


class Updates:
    def __init__(self,prefs,downloads):
        self.prefs=prefs;self.downloads=downloads;self.lock=threading.RLock();self.stop_event=threading.Event()
        self.data={'current':CURRENT,'status':'idle','available':None,'error':'','checkedAt':None,'download':None}
        self.busy=False

    def snapshot(self):
        with self.lock:
            result=copy.deepcopy(self.data)
            if result['download']:
                with self.downloads.lock:item=copy.deepcopy(self.downloads.items.get(result['download']))
                result['transfer']=item
                if item and item['status']=='complete':result['status']='ready'
                elif item and item['status']=='error':result['status']='error';result['error']=item['error']
            return result

    def check(self,download=False):
        with self.lock:
            if self.busy:return self.snapshot()
            self.busy=True;self.data.update(status='checking',error='')
        def work():
            try:
                req=urllib.request.Request(API,headers={'User-Agent':'Edryvo/'+CURRENT,'Accept':'application/vnd.github+json'})
                with urllib.request.urlopen(req,timeout=20) as response:raw=response.read(2_000_001)
                if len(raw)>2_000_000:raise ValueError('Respuesta de actualización demasiado grande.')
                releases=json.loads(raw);asset=update_asset(releases)
                with self.lock:self.data.update(status='available' if asset else 'up_to_date',available=asset,checkedAt=time.time(),download=None)
                if asset and download and not self.stop_event.is_set():self.download()
            except Exception as error:
                with self.lock:self.data.update(status='error',error=str(error)[:300])
            finally:
                with self.lock:self.busy=False
        threading.Thread(target=work,daemon=True,name='lumen-update-check').start()
        return self.snapshot()

    def download(self):
        with self.lock:
            asset=self.data['available']
            if not asset:raise ValueError('Comprueba primero si hay actualizaciones.')
            with self.downloads.lock:
                existing=next((x for x in self.downloads.items.values() if x['url']==asset['url'] and x['sha256']==asset['sha256']),None)
            if existing:
                key=existing['id']
                if existing['status'] in ('paused','error'):self.downloads.resume(key)
            else:
                state=self.downloads.start(asset['url'],asset['name'],asset['sha256'])
                key=next(x['id'] for x in state['items'] if x['url']==asset['url'] and x['sha256']==asset['sha256'])
            self.data.update(status='downloading',download=key)
            return self.snapshot()

    def installer(self):
        state=self.snapshot()
        if state['status']!='ready':raise ValueError('La actualización aún no se ha descargado y verificado.')
        from pathlib import Path
        file=Path(state['transfer']['path']).resolve()
        if file.parent!=self.downloads.root.resolve() or not package_matches(file.name):raise ValueError('Instalador no válido para este sistema.')
        # Recheck before execution, even if the user modified the downloaded file.
        import hashlib
        digest=hashlib.sha256()
        with file.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
        sha=digest.hexdigest()
        if sha!=state['available']['sha256']:raise ValueError('El instalador no coincide con la versión publicada.')
        return file

    def start(self):
        def monitor():
            while not self.stop_event.is_set():
                if self.prefs.get('updates.automatic'):self.check(download=True)
                if self.stop_event.wait(6*3600):break
        threading.Thread(target=monitor,daemon=True,name='lumen-update-monitor').start()

    def shutdown(self):self.stop_event.set()
