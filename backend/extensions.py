"""Open VSX packages: streamed review, contributions and separate opt-in runtime."""
from __future__ import annotations
import hashlib
import base64
import io
import json
import os
import platform
import urllib.error
import re
import secrets
import shutil
import stat
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from .preferences import atomic_json

ID_PART=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$')
VERSION=re.compile(r'^[0-9][A-Za-z0-9.+_-]{0,79}$')
MAX_ARCHIVE=4*1024**3
MAX_UNPACKED=8*1024**3
MAX_MEMBER=2*1024**3
REGISTRY='https://open-vsx.org'

def target_platform():
    machine=platform.machine().lower()
    arch={'amd64':'x64','x86_64':'x64','aarch64':'arm64','arm64':'arm64','x86':'ia32','i386':'ia32','armv7l':'armhf'}.get(machine,machine)
    system={'Windows':'win32','Darwin':'darwin','Linux':'linux'}.get(platform.system(),platform.system().lower())
    return system+'-'+arch

def registry_metadata(parts,version):
    # The unqualified endpoint can return a package for an arbitrary architecture.
    base=REGISTRY+'/api/'+'/'.join(parts)
    for target in (target_platform(),'universal'):
        try:
            data=json.loads(download(base+'/'+target+'/'+version,2_000_000))
            if data.get('error'):continue
            if data.get('targetPlatform','universal') not in (target,'universal'):continue
            return data
        except urllib.error.HTTPError as exc:
            if exc.code!=404:raise
    raise ValueError('Esta extensión no ofrece una versión para '+target_platform()+'.')


class CheckedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        validate_remote(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def validate_remote(url):
    p=urllib.parse.urlparse(url)
    # The official registry now redirects package files to Eclipse's content CDN.
    if p.scheme!='https' or p.username or p.password or p.port not in (None,443) or not (p.hostname in ('open-vsx.org','openvsx.eclipsecontent.org') or (p.hostname=='storage.googleapis.com' and p.path.startswith('/open-vsx/'))):
        raise ValueError('Origen de extensiones no permitido.')
    return url


def download(url,limit=2_000_000):
    validate_remote(url)
    req=urllib.request.Request(url,headers={'User-Agent':'Zenit/0.5.3','Accept':'application/json, application/octet-stream'})
    opener=urllib.request.build_opener(CheckedRedirect())
    # HTTPError is also an OSError. Preserve 404 so platform resolution can try
    # universal packages, rather than misreporting a healthy registry as offline.
    for attempt in range(3):
        try:
            with opener.open(req,timeout=8) as r:
                validate_remote(r.geturl())
                if int(r.headers.get('Content-Length','0'))>limit: raise ValueError('Descarga demasiado grande.')
                data=r.read(limit+1)
                if len(data)>limit: raise ValueError('Descarga demasiado grande.')
                return data
        except urllib.error.HTTPError as e:
            code=e.code;e.close()
            if code==404:raise
            if code not in (408,429,500,502,503,504) or attempt==2:
                message='El registro está ocupado. Inténtalo de nuevo en unos momentos.' if code==429 else 'Open VSX devolvió un error HTTP '+str(code)+'. Puedes importar un VSIX local o volver a intentarlo.'
                raise ValueError(message) from e
        except (OSError,TimeoutError) as e:
            if attempt==2:raise ValueError('No se pudo contactar con Open VSX después de tres intentos. Comprueba la conexión o importa un VSIX local.') from e
        time.sleep(.4*(attempt+1))


def download_file(url, destination, progress=lambda **kw:None, cancelled=lambda:False):
    """Bounded memory, validated redirects, disk preflight and cancellable reads."""
    validate_remote(url)
    req=urllib.request.Request(url,headers={'User-Agent':'Zenit/0.5.3','Accept':'application/octet-stream'})
    opener=urllib.request.build_opener(CheckedRedirect())
    with opener.open(req,timeout=25) as response, destination.open('wb') as output:
        validate_remote(response.geturl())
        total=int(response.headers.get('Content-Length') or 0)
        if total>MAX_ARCHIVE:raise ValueError('El VSIX supera 4 GB. Los compiladores independientes se descargan desde Lenguajes y herramientas (hasta 500 GB).')
        if total and total+64*1024**2>shutil.disk_usage(destination.parent).free:raise ValueError('No hay espacio suficiente para descargar esta extensión.')
        received=0;progress(phase='download',received=0,total=total)
        while True:
            if cancelled():raise InterruptedError('Revisión cancelada.')
            block=response.read(1024*1024)
            if not block:break
            received+=len(block)
            if received>MAX_ARCHIVE:raise ValueError('El VSIX supera 4 GB.')
            output.write(block);progress(received=received)
        if total and received!=total:raise ValueError('Descarga incompleta. Inténtalo de nuevo; no se instaló el paquete.')


def localized_manifest(root,locale=None):
    manifest=json_resource(root,'package.json')
    try:messages=json_resource(root,'package.nls.json')
    except (OSError,ValueError):messages={}
    if not isinstance(messages,dict):messages={}
    if isinstance(locale,str) and re.fullmatch(r'[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})*',locale):
        language=locale.replace('_','-').lower()
        for candidate in dict.fromkeys((language.split('-')[0],language)):
            try:translation=json_resource(root,'package.nls.'+candidate+'.json')
            except (OSError,ValueError):continue
            if isinstance(translation,dict):messages.update(translation)
    def translate(value):
        if isinstance(value,str) and value.startswith('%') and value.endswith('%'):
            result=messages.get(value[1:-1],value)
            return result if isinstance(result,str) else value
        if isinstance(value,list):return [translate(item) for item in value]
        if isinstance(value,dict):return {key:translate(item) for key,item in value.items()}
        return value
    return translate(manifest)


def safe_member(name):
    p=PurePosixPath(name)
    if '\\' in name or ':' in name or '\x00' in name or p.is_absolute() or '..' in p.parts or not p.parts:
        raise ValueError('Ruta insegura en VSIX.')
    return p


def json_resource(root,relative):
    if not isinstance(relative,str): raise ValueError('Ruta de contribución no válida.')
    p=(root/str(safe_member(relative))).resolve()
    if not p.is_relative_to(root.resolve()) or not p.is_file() or p.stat().st_size>3_000_000: raise ValueError('Recurso de extensión no válido.')
    try:
        text=p.read_text(encoding='utf-8-sig')
        # Preserve quoted strings verbatim while removing JSONC comments/trailing commas.
        token=r'"(?:\\.|[^"\\])*"|/\*[\s\S]*?\*/|//[^\r\n]*'
        text=re.sub(token,lambda m:m[0] if m[0].startswith('"') else ' ',text)
        text=re.sub(r'("(?:\\.|[^"\\])*")|,\s*(?=[}\]])',lambda m:m[1] or '',text)
        return json.loads(text)
    except (UnicodeError,ValueError) as e: raise ValueError('El recurso no contiene JSON/JSONC válido.') from e

def color_theme(root,relative,seen=None):
    """Resolve JSONC theme inheritance strictly inside its installed package."""
    if not isinstance(relative,str) or not relative:raise ValueError('Ruta de tema no válida.')
    root=root.resolve()
    seen=set() if seen is None else seen
    target=(root/relative).resolve()
    if not target.is_relative_to(root.resolve()) or target in seen or len(seen)>=12:
        raise ValueError('Herencia de tema circular o fuera del paquete.')
    seen.add(target)
    data=json_resource(root,target.relative_to(root).as_posix())
    if not isinstance(data,dict):raise ValueError('Tema de color no válido.')
    parent=data.get('include')
    if parent:
        if not isinstance(parent,str):raise ValueError('Herencia de tema no válida.')
        base=color_theme(root,(target.parent/parent).resolve().relative_to(root.resolve()).as_posix(),seen)
        data={**base,**data,'colors':{**base.get('colors',{}),**data.get('colors',{})},
              'tokenColors':base.get('tokenColors',[])+data.get('tokenColors',[])}
    return data


def icon_theme(root,declaration,owner):
    theme_path=(root/str(safe_member(declaration.get('path','')))).resolve()
    data=json_resource(root,declaration.get('path'));definitions={};size=0
    for key,value in list(data.get('iconDefinitions',{}).items())[:4000]:
        relative=value.get('iconPath') if isinstance(value,dict) else None
        if not isinstance(relative,str) or ':' in relative or '\\' in relative:continue
        path=(theme_path.parent/relative).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file() or path.stat().st_size>50000:continue
        if path.suffix.lower()!='.svg':continue
        raw=path.read_text(encoding='utf-8-sig')
        if re.search(r'<(?:script|foreignObject|iframe|image)\b|\bon\w+\s*=|(?:href\s*=\s*[\"\'](?!#))|url\(\s*[\"\']?(?!#)|<!ENTITY|<!DOCTYPE',raw,re.I):continue
        size+=len(raw)
        if size>2_000_000:break
        definitions[key]='data:image/svg+xml;base64,'+base64.b64encode(raw.encode()).decode('ascii')
    return {'id':owner+':'+str(declaration.get('id','icons')),'label':str(declaration.get('label','Iconos'))[:160],
            'definitions':definitions,'fileExtensions':data.get('fileExtensions',{}),'fileNames':data.get('fileNames',{}),'file':data.get('file'),'owner':owner}


def image_data(raw):
    """Catalog images never become executable markup or external resource loaders."""
    if len(raw)>512_000:raise ValueError('Icono demasiado grande.')
    if raw.startswith(b'\x89PNG\r\n\x1a\n'):mime='image/png'
    elif raw.startswith(b'\xff\xd8\xff'):mime='image/jpeg'
    elif raw[:4]==b'RIFF' and raw[8:12]==b'WEBP':mime='image/webp'
    elif raw.startswith((b'GIF87a',b'GIF89a')):mime='image/gif'
    else:
        svg=raw.decode('utf-8-sig')
        if not re.search(r'<svg\b',svg,re.I) or re.search(r'<(?:script|foreignObject|iframe|image|use)\b|\bon\w+\s*=|(?:href\s*=\s*[\"\'](?!#))|url\(\s*[\"\']?(?!#)|<!ENTITY|<!DOCTYPE',svg,re.I):raise ValueError('Icono no válido.')
        mime='image/svg+xml'
    return 'data:'+mime+';base64,'+base64.b64encode(raw).decode('ascii')


def package_icon(root,manifest):
    relative=manifest.get('icon')
    if not relative:return None
    try:
        target=(root/str(safe_member(relative))).resolve()
        if not target.is_relative_to(root.resolve()) or not target.is_file() or target.stat().st_size>512_000:return None
        return image_data(target.read_bytes())
    except (OSError,ValueError,UnicodeError):return None


class ExtensionStore:
    def __init__(self,prefs):
        self.prefs=prefs; self.root=prefs.directory/'extensions';self.root.mkdir(exist_ok=True)
        self.lock=threading.RLock(); self.pending={}; self.jobs={}; self.index=self.root/'installed.json'
        try: self.installed=json.loads(self.index.read_text(encoding='utf-8-sig'))
        except (OSError,ValueError): self.installed={}
        if not isinstance(self.installed,dict): self.installed={}
        # Migrate older valid installs so a future damaged index is recoverable.
        for eid,item in list(self.installed.items()):
            try:
                folder=self.root/item['directory']
                if folder.resolve().parent!=self.root.resolve() or folder.is_symlink():continue
                manifest=localized_manifest(folder/'extension')
                if eid==manifest['publisher']+'.'+manifest['name'] and not (folder/'.lumen-install.json').exists():atomic_json(folder/'.lumen-install.json',item)
            except (OSError,ValueError,KeyError,TypeError):continue
        # Recover complete packages after a damaged/missing index. Pending reviews
        # have no receipt and are deliberately excluded from this scan.
        recovered=False
        for receipt in self.root.glob('*/.lumen-install.json'):
            try:
                item=json.loads(receipt.read_text(encoding='utf-8'))
                if receipt.parent.is_symlink() or item.get('directory')!=receipt.parent.name:continue
                manifest=localized_manifest(receipt.parent/'extension')
                if item['id']!=manifest['publisher']+'.'+manifest['name']:continue
                if item['id'] not in self.installed:self.installed[item['id']]=item;recovered=True
            except (OSError,ValueError,KeyError,TypeError):continue
        if recovered:atomic_json(self.index,self.installed)
    @contextmanager
    def index_transaction(self):
        """Serialize index changes across independent Zénit desktop processes."""
        with (self.root/'.index-lock').open('a+b') as stream:
            stream.seek(0,2)
            if stream.tell()==0:stream.write(b'0');stream.flush()
            stream.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_LOCK,1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(),fcntl.LOCK_EX)
            try:
                self.refresh_index();yield
            finally:
                stream.seek(0)
                if os.name=='nt':msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
                else:fcntl.flock(stream.fileno(),fcntl.LOCK_UN)
    def refresh_index(self):
        try:
            data=json.loads(self.index.read_text(encoding='utf-8-sig'))
            if isinstance(data,dict):self.installed=data
        except (OSError,ValueError):pass
    def _network(self):
        if not self.prefs.get('extensions.network'): raise PermissionError('La red de extensiones está desactivada en Seguridad / Extensiones.')
    def list(self):
        with self.lock:
            self.refresh_index()
            result=[]
            for x in self.installed.values():
                item=dict(x);item['supported']=list(x.get('supported',[]))
                try:
                    manifest=localized_manifest(self.root/x['directory']/'extension')
                    item.update({k:manifest.get(k,item.get(k,'')) for k in ('displayName','description')})
                    item['icon']=package_icon(self.root/x['directory']/'extension',manifest)
                    if (manifest.get('main') or manifest.get('lumen',{}).get('main')) and 'runtime' not in item['supported']:item['supported'].append('runtime')
                except (OSError,ValueError):pass
                result.append(item)
            return result
    def search(self,q='',offset=0):
        self._network()
        if not isinstance(q,str) or len(q)>180: raise ValueError('Consulta no válida.')
        url=REGISTRY+'/api/-/search?'+urllib.parse.urlencode({'query':q,'size':24,'offset':max(0,min(int(offset),5000)),'sortBy':'relevance'})
        data=json.loads(download(url,2_000_000))
        out=[]
        for e in data.get('extensions',[])[:24]:
            ns=e.get('namespace','');name=e.get('name','')
            if not ID_PART.fullmatch(ns) or not ID_PART.fullmatch(name): continue
            out.append({'id':ns+'.'+name,'namespace':ns,'name':name,'displayName':str(e.get('displayName') or name)[:160],
                'description':str(e.get('description',''))[:700],'version':str(e.get('version',''))[:80],
                'iconUrl':e.get('files',{}).get('icon'),
                'downloads':e.get('downloadCount',0),'installed':ns+'.'+name in self.installed})
        return {'extensions':out,'total':data.get('totalSize',len(out)),'offset':offset,'source':'Open VSX'}
    def catalog_icon(self,url):
        validate_remote(url);cache=self.root/'catalog-icons';cache.mkdir(exist_ok=True)
        target=cache/(hashlib.sha256(url.encode()).hexdigest()+'.image')
        if target.is_file() and target.stat().st_size<=512_000:return {'icon':image_data(target.read_bytes())}
        self._network();raw=download(url,512_000);icon=image_data(raw)
        if len(list(cache.glob('*.image')))>256:
            for stale in sorted(cache.glob('*.image'),key=lambda p:p.stat().st_mtime)[:32]:stale.unlink(missing_ok=True)
        target.write_bytes(raw);return {'icon':icon}
    def inspect_remote(self,extension_id,version='latest',progress=lambda **kw:None,cancelled=lambda:False):
        self._network();parts=str(extension_id).split('.')
        if len(parts)!=2 or any(not ID_PART.fullmatch(x) for x in parts): raise ValueError('Usa publisher.nombre.')
        if version!='latest' and not VERSION.fullmatch(str(version)): raise ValueError('Versión no válida.')
        meta=registry_metadata(parts,version)
        url=meta.get('files',{}).get('download')
        if not url: raise ValueError('Open VSX no devolvió el VSIX.')
        fd,name=tempfile.mkstemp(suffix='.vsix',prefix='.download-',dir=self.root);os.close(fd);package=Path(name)
        try:
            download_file(url,package,progress,cancelled)
            candidate=self.inspect_file(package,'Open VSX',progress,cancelled)
        finally:package.unlink(missing_ok=True)
        if candidate['id'].lower()!=extension_id.lower():
            self.discard(candidate['ticket']);raise ValueError('La identidad descargada no coincide.')
        return candidate
    def inspect_local(self,path,progress=lambda **kw:None,cancelled=lambda:False):
        p=Path(path).expanduser()
        if not p.is_absolute() or p.suffix.lower() not in ('.vsix','.zip') or not p.is_file(): raise ValueError('Selecciona un VSIX o paquete ZIP local mediante su ruta absoluta.')
        if p.stat().st_size>MAX_ARCHIVE: raise ValueError('VSIX demasiado grande.')
        return self.inspect_file(p,'Archivo local',progress,cancelled)
    def inspect_bytes(self,raw,source='Archivo local'):
        if len(raw)>MAX_ARCHIVE: raise ValueError('VSIX demasiado grande.')
        return self._inspect(io.BytesIO(raw),len(raw),hashlib.sha256(raw).hexdigest(),source)
    def inspect_file(self,path,source='Archivo local',progress=lambda **kw:None,cancelled=lambda:False):
        size=path.stat().st_size
        if size>MAX_ARCHIVE:raise ValueError('VSIX demasiado grande (máximo 4 GB).')
        sha=hashlib.sha256();progress(phase='verify',received=size,total=size)
        with path.open('rb') as stream:
            while block:=stream.read(1024*1024):
                if cancelled():raise InterruptedError('Revisión cancelada.')
                sha.update(block)
            stream.seek(0)
            return self._inspect(stream,size,sha.hexdigest(),source,progress,cancelled)
    def _inspect(self,stream,size,sha,source,progress=lambda **kw:None,cancelled=lambda:False):
        temp=Path(tempfile.mkdtemp(prefix='.review-',dir=self.root))
        try:
            with zipfile.ZipFile(stream) as z:
                members=z.infolist()
                if len(members)>20000: raise ValueError('Demasiados archivos en VSIX.')
                total=0;seen=set()
                for member in members:
                    if cancelled():raise InterruptedError('Revisión cancelada.')
                    p=safe_member(member.filename); folded=str(p).casefold()
                    if folded in seen: raise ValueError('Rutas duplicadas en VSIX.')
                    seen.add(folded)
                    mode=member.external_attr>>16
                    if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode))): raise ValueError('Enlaces o archivos especiales no admitidos.')
                    total+=member.file_size
                    if total>MAX_UNPACKED or member.file_size>MAX_MEMBER: raise ValueError('Contenido VSIX demasiado grande (8 GB descomprimidos, 2 GB por archivo).')
                if total+64*1024**2>shutil.disk_usage(temp).free:raise ValueError('No hay espacio suficiente para descomprimir esta extensión.')
                progress(phase='extract',unpacked=total)
                for member in members:
                    if cancelled():raise InterruptedError('Revisión cancelada.')
                    p=safe_member(member.filename)
                    if member.is_dir(): continue
                    # Store only extension payload. No metadata archive contents are executed.
                    if p.parts[0]!='extension': continue
                    dst=temp/str(p);dst.parent.mkdir(parents=True,exist_ok=True)
                    with z.open(member) as inp,dst.open('wb') as out:
                        while block:=inp.read(1024*1024):
                            if cancelled():raise InterruptedError('Revisión cancelada.')
                            out.write(block)
            manifest=localized_manifest(temp/'extension')
            if not isinstance(manifest,dict): raise ValueError('Manifest no válido.')
            ns=manifest.get('publisher','');name=manifest.get('name','');version=manifest.get('version','')
            if not all(isinstance(x,str) and ID_PART.fullmatch(x) for x in (ns,name)) or not isinstance(version,str) or not VERSION.fullmatch(version): raise ValueError('Identidad o versión del paquete no válida.')
            eid=ns+'.'+name;c=manifest.get('contributes',{})
            if not isinstance(c,dict): raise ValueError('Contributions no válido.')
            supported=[];warnings=[]
            for k in ('languages','snippets','themes','iconThemes'):
                if c.get(k): supported.append(k)
            custom=manifest.get('lumen',{})
            if isinstance(custom,dict) and custom.get('commands'): supported.append('lumen.commands')
            if manifest.get('main') or custom.get('main'):
                supported.append('runtime');warnings.append('Motor Python Pyrefly integrado mediante LSP: autocompletado, diagnósticos, definiciones, referencias e inlay hints. La interfaz y los comandos propios de VS Code no se ejecutan.' if eid.lower()=='meta.pyrefly' else 'Código Node.js ejecutable: requiere autorización para iniciar. API Zénit preview y subconjunto de VS Code; APIs no implementadas producen un error explícito.')
            elif manifest.get('browser'):warnings.append('La entrada browser de VS Code no es compatible con el host Node.js de esta preview.')
            if c.get('grammars'): warnings.append('Las gramáticas TextMate se conservan, pero no se ejecutan. El resaltado depende de los lenguajes integrados en Monaco.')
            if manifest.get('extensionDependencies') or manifest.get('extensionPack'): warnings.append('Las dependencias y paquetes agrupados no se instalan automáticamente.')
            extra=set(c)-{'languages','snippets','themes','grammars','iconThemes'}
            if extra: warnings.append('Contribuciones no implementadas: '+', '.join(sorted(extra)[:20]))
            if not supported: warnings.append('No hay contribuciones activables en este host. Instalación solo como paquete inactivo.')
            ticket=secrets.token_urlsafe(24)
            result={'id':eid,'name':name,'publisher':ns,'displayName':str(manifest.get('displayName') or name)[:160],
                'version':version,'description':str(manifest.get('description',''))[:1000],'license':str(manifest.get('license','No declarada'))[:200],
                'source':source,'sha256':sha,'size':size,'unpackedSize':total,'supported':supported,'warnings':warnings,
                'compatibility':'partial' if warnings else 'declarative','ticket':ticket,'enabled':bool(supported)}
            with self.lock:
                self._expire()
                if len(self.pending)>=8: raise ValueError('Cierra una revisión pendiente antes de abrir otra.')
                self.pending[ticket]=(time.monotonic(),temp,result)
            return dict(result)
        except Exception:
            shutil.rmtree(temp,ignore_errors=True);raise
    def start_review(self,request):
        with self.lock:
            self.jobs={key:job for key,job in self.jobs.items() if not job.get('done') or time.monotonic()-job['created']<600}
            if sum(not j.get('done') for j in self.jobs.values())>=2:raise ValueError('Ya hay dos revisiones en curso.')
            key=secrets.token_urlsafe(18);job={'id':key,'created':time.monotonic(),'phase':'metadata','received':0,'total':0,'done':False,'cancelled':False};self.jobs[key]=job
        def progress(**updates):
            with self.lock:job.update(updates)
        def run():
            try:
                result=self.inspect_local(request['path'],progress,lambda:job['cancelled']) if 'path' in request else self.inspect_remote(request.get('id',''),request.get('version','latest'),progress,lambda:job['cancelled'])
                if job['cancelled']:self.discard(result['ticket']);raise InterruptedError('Revisión cancelada.')
                progress(result=result,phase='ready')
            except Exception as exc:progress(error=str(exc),phase='cancelled' if job['cancelled'] else 'error')
            finally:progress(done=True)
        threading.Thread(target=run,daemon=True,name='extension-review').start()
        return {'id':key}
    def review_status(self,key,cancel=False):
        with self.lock:
            job=self.jobs.get(key)
            if not job:raise ValueError('Revisión no encontrada.')
            if cancel:
                job['cancelled']=True
                if job.get('result'):self.discard(job['result']['ticket'])
            return {k:v for k,v in job.items() if k!='created'}
    def _expire(self):
        for ticket,(t,folder,_) in list(self.pending.items()):
            if time.monotonic()-t>600:
                shutil.rmtree(folder,ignore_errors=True);del self.pending[ticket]
    def discard(self,ticket):
        with self.lock:
            item=self.pending.pop(ticket,None)
            if item: shutil.rmtree(item[1],ignore_errors=True)
    def install(self,ticket,consent=False):
        if consent is not True: raise PermissionError('Confirma el editor, licencia y compatibilidad antes de instalar.')
        with self.lock,self.index_transaction():
            self._expire();item=self.pending.get(ticket)
            if not item: raise ValueError('La revisión ha caducado. Inspecciona otra vez el paquete.')
            _,folder,result=item;result={k:v for k,v in result.items() if k!='ticket'}
            target=self.root/(result['id']+'-'+result['sha256'][:16])
            if not target.exists(): os.replace(folder,target)
            else: shutil.rmtree(folder,ignore_errors=True)
            result['directory']=target.name
            atomic_json(target/'.lumen-install.json',result)
            previous=self.installed.get(result['id'])
            next_index={**self.installed,result['id']:result}
            atomic_json(self.index,next_index);self.installed=next_index;del self.pending[ticket]
            if previous and previous.get('directory')!=target.name: self._remove_payload(previous)
            self.prefs.audit('extension.install',extension=result['id'])
            return dict(result)
    def _remove_payload(self,item):
        name=item.get('directory','')
        target=self.root/name
        if name and target.resolve().parent==self.root.resolve() and not target.is_symlink():
            shutil.rmtree(target,ignore_errors=True)
    def update_state(self,eid,enabled=None,remove=False):
        with self.lock,self.index_transaction():
            if eid not in self.installed: raise FileNotFoundError('Extensión no instalada.')
            item=dict(self.installed[eid]);next_index=dict(self.installed)
            if remove: del next_index[eid]
            else:
                if type(enabled) is not bool: raise ValueError('Estado no válido.')
                item['enabled']=enabled;next_index[eid]=item
                atomic_json(self.root/item['directory']/'.lumen-install.json',item)
            atomic_json(self.index,next_index);self.installed=next_index
            if remove: self._remove_payload(item)
            self.prefs.audit('extension.remove' if remove else 'extension.toggle',extension=eid)
            return {'extensions':self.list()}
    def export_package(self, eid):
        import base64
        with self.lock:
            item = self.installed.get(eid)
            if not item: raise FileNotFoundError('Extensión no instalada.')
            folder = self.root / item['directory'] / 'extension'
            if folder.is_symlink() or not folder.resolve().is_relative_to(self.root.resolve()):
                raise ValueError('Ruta de extensión no válida.')
            stream = io.BytesIO(); total = 0
            with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
                for file in folder.rglob('*'):
                    if file.is_symlink(): raise ValueError('La extensión contiene un enlace.')
                    if not file.is_file(): continue
                    total += file.stat().st_size
                    if total > 180*1024**2: raise ValueError('Para exportar este paquete grande, copia su carpeta desde el perfil de Zénit. La exportación web admite 180 MB.')
                    archive.write(file, 'extension/' + file.relative_to(folder).as_posix())
            if stream.tell() > 48*1024**2: raise ValueError('La exportación web admite VSIX de hasta 48 MB; el paquete instalado se conserva en el perfil de Zénit.')
            return {'filename': item['id'] + '-' + item['version'] + '.vsix', 'data': base64.b64encode(stream.getvalue()).decode('ascii')}
    def contributions(self):
        output={'languages':[],'snippets':[],'themes':[],'iconThemes':[],'commands':[],'errors':[]}
        if not self.prefs.get('extensions.loadContributions'): return output
        for info in self.list():
            if not info.get('enabled'): continue
            root=(self.root/info['directory']/'extension').resolve()
            if not root.is_relative_to(self.root.resolve()): continue
            try:
                manifest=json_resource(root,'package.json');c=manifest.get('contributes',{})
                for language in c.get('languages',[])[:200]:
                    lid=language.get('id','')
                    if not isinstance(lid,str) or not re.fullmatch(r'[a-zA-Z0-9_+.-]{1,80}',lid): continue
                    extensions=[x for x in language.get('extensions',[])[:60] if isinstance(x,str) and re.fullmatch(r'\.[\w.+-]{1,30}',x)]
                    output['languages'].append({'id':lid,'extensions':extensions,'aliases':[str(x)[:80] for x in language.get('aliases',[])[:4]],'owner':info['id']})
                for declaration in c.get('snippets',[])[:100]:
                    snippets=json_resource(root,declaration.get('path'))
                    if not isinstance(snippets,dict): continue
                    for name,value in list(snippets.items())[:500]:
                        if not isinstance(value,dict): continue
                        body=value.get('body','');body='\n'.join(map(str,body)) if isinstance(body,list) else str(body)
                        if len(body)>50000: continue
                        prefix=value.get('prefix',name);prefix=prefix[0] if isinstance(prefix,list) and prefix else prefix
                        output['snippets'].append({'name':str(name)[:160],'prefix':str(prefix)[:120],'body':body,'language':str(declaration.get('language','plaintext'))[:80],'owner':info['id']})
                for declaration in c.get('themes',[])[:30]:
                    data=color_theme(root,declaration.get('path'))
                    if isinstance(data,dict): output['themes'].append({'id':info['id']+':'+str(declaration.get('id',declaration.get('label','theme'))),'label':str(declaration.get('label','Theme'))[:160],'uiTheme':declaration.get('uiTheme','vs-dark'),'data':data,'owner':info['id']})
                custom=manifest.get('lumen',{})
                for declaration in c.get('iconThemes',[])[:5]:
                    output['iconThemes'].append(icon_theme(root,declaration,info['id']))
                for cmd in (custom.get('commands',[]) if isinstance(custom,dict) else [])[:80]:
                    if not isinstance(cmd,dict) or cmd.get('kind') not in ('insertSnippet','openSettings'): continue
                    output['commands'].append({'id':info['id']+':'+str(cmd.get('id','command'))[:100],'title':str(cmd.get('title','Command'))[:160],
                        'kind':cmd['kind'],'body':str(cmd.get('body',''))[:50000],'category':str(cmd.get('category','general'))[:80],'owner':info['id']})
            except (OSError,ValueError,TypeError,AttributeError) as e:
                output['errors'].append({'id':info['id'],'error':str(e)[:400]})
        return output
    def updates(self):
        self._network();out=[]
        for item in self.list()[:60]:
            meta=json.loads(download(REGISTRY+'/api/'+item['publisher']+'/'+item['name']+'/latest',2_000_000))
            latest=meta.get('version',item['version'])
            out.append({'id':item['id'],'installed':item['version'],'latest':latest,'different':latest!=item['version']})
        return {'updates':out}
    def shutdown(self):
        with self.lock:
            for _,folder,_ in self.pending.values(): shutil.rmtree(folder,ignore_errors=True)
            self.pending.clear()
