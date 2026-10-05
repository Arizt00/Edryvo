"""Opt-in executable extensions. One killable Node process per extension, no UI blocking."""
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import uuid
from .extensions import localized_manifest
from .runtime_paths import find_tool
from .terminals import child_environment, terminal_profiles
from .extension_lsp import PyreflyHost, JavaLanguageHost
from .preferences import atomic_json


class Host:
    def __init__(self, node, root, entry, workspace, options, services=None):
        self.lock=threading.Lock();self.write_lock=threading.Lock();self.responses=queue.Queue();self.logs=''
        self.services=services;self.workspace=workspace;self.extension_id=options['extensionId'];self.extension_root=Path(root)
        self.process=subprocess.Popen([node,str(Path(__file__).with_name('extension_host.cjs'))],cwd=workspace.root,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=child_environment(),creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        threading.Thread(target=self.read,daemon=True).start();threading.Thread(target=self.read_errors,daemon=True).start()
        try:self.capabilities=self.request({'method':'activate','entry':str(entry),'root':str(root),'workspace':str(workspace.root),**options})
        except Exception:self.close();raise

    def read(self):
        try:
            while line:=self.process.stdout.readline(2_000_001):
                if len(line)>2_000_000:self.close();break
                try:
                    message=json.loads(line)
                    if message.get('type')=='service':threading.Thread(target=self.service,args=(message,),daemon=True).start()
                    else:self.responses.put(message)
                except ValueError:pass
        except (OSError,ValueError):pass
        finally:self.responses.put({'error':'El proceso de la extensión terminó.'})

    def read_errors(self):
        try:
            while data:=self.process.stderr.read1(4096):self.logs=(self.logs+data.decode('utf-8','replace'))[-12000:]
        except (OSError,ValueError):pass

    def send(self,message):
        raw=json.dumps(message,ensure_ascii=False).encode('utf-8')+b'\n'
        if len(raw)>2_000_000:raise ValueError('Mensaje de extensión demasiado grande.')
        with self.write_lock:self.process.stdin.write(raw);self.process.stdin.flush()

    def service(self,message):
        reply={'type':'serviceResult','id':message['id']}
        try:
            if self.services is None:raise ValueError('Servicios del IDE no conectados.')
            reply['result']=self.services.call(self,message['method'],message.get('params',{}))
        except Exception as error:reply['error']=str(error)
        try:self.send(reply)
        except (OSError,ValueError):pass

    def event(self,name,value):
        try:self.send({'type':'serviceEvent','name':name,'value':value})
        except (OSError,ValueError):pass

    def request(self, message):
        with self.lock:
            message={**message,'id':uuid.uuid4().hex}
            self.send(message)
            try:result=self.responses.get(timeout=60)
            except queue.Empty:self.close();raise ValueError('La extensión no respondió en 60 segundos. Se detuvo su proceso.')
            if result.get('error'):raise ValueError(result['error'])
            if result.get('id')!=message['id']:raise ValueError('Respuesta inesperada de la extensión.')
            return result['result']

    def close(self):
        if self.services:self.services.close_host(self)
        if self.process.poll() is None:
            if os.name=='nt':subprocess.run(['taskkill','/PID',str(self.process.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=5)
            else:self.process.kill()
        try:self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:self.process.kill()
        for stream in (self.process.stdin,self.process.stdout,self.process.stderr):
            try:stream.close()
            except (OSError,ValueError):pass


class ExtensionRuntime:
    def __init__(self, store):
        self.store=store;self.hosts={};self.lock=threading.RLock();self.errors={};self.services=None
        self.approvals_path=store.root/'runtime-approvals.json'
        try:self.approvals=json.loads(self.approvals_path.read_text(encoding='utf-8'))
        except (OSError,ValueError):self.approvals={}
        if not isinstance(self.approvals,dict):self.approvals={}
    def snapshot(self):
        with self.lock:return {'hosts':[{'id':key,'running':host.process.poll() is None,**host.capabilities,'logs':host.logs} for key,host in self.hosts.items()],'errors':dict(self.errors)}
    def approve(self,workspace,eid):
        key=str(workspace.root);self.approvals[key]=list(set(self.approvals.get(key,[]))|{eid});atomic_json(self.approvals_path,self.approvals);self.errors.pop(eid,None)
    def restore(self,workspace):
        if not workspace.trusted:return self.snapshot()
        with self.lock:
            for eid in self.approvals.get(str(workspace.root),[]):
                if eid in self.hosts or eid in self.errors:continue
                if not self.store.installed.get(eid,{}).get('enabled'):continue
                try:self.start(workspace,eid,True)
                except Exception as error:self.errors[eid]=str(error)
        return self.snapshot()
    def start(self, workspace, eid, consent):
        if consent is not True or not workspace.trusted:raise PermissionError('Autoriza la extensión ejecutable en un proyecto de confianza.')
        with self.lock:
            info=self.store.installed.get(eid)
            if not info or not info.get('enabled'):raise ValueError('Activa primero la extensión instalada.')
            root=(self.store.root/info['directory']/'extension').resolve();manifest=localized_manifest(root,self.store.prefs.get('general.locale'))
            if eid.lower()=='meta.pyrefly':
                self.stop(eid);self.hosts[eid]=PyreflyHost(root,workspace)
                self.approve(workspace,eid)
                self.store.prefs.audit('extension.execute',extension=eid,engine='native-lsp')
                return self.snapshot()
            if eid.lower()=='redhat.java':
                self.stop(eid);self.hosts[eid]=JavaLanguageHost(root,workspace,self.store.root/'.runtime-data'/eid)
                self.approve(workspace,eid)
                return self.snapshot()
            entry=(root/manifest.get('lumen',{}).get('main',manifest.get('main',''))).resolve()
            if entry.suffix not in ('.js','.cjs','.mjs') and entry.with_suffix('.js').is_file():entry=entry.with_suffix('.js')
            if not entry.is_relative_to(root) or not entry.is_file() or entry.suffix not in ('.js','.cjs','.mjs'):raise ValueError('La extensión necesita un main Node.js compatible con la API preview.')
            node=find_tool('node')
            if not node:raise ValueError('Instala Node.js para ejecutar extensiones.')
            extensions=[]
            for item in self.store.list():
                other=self.store.root/item['directory']/'extension'
                try:extensions.append({'id':item['id'],'root':str(other),'manifest':localized_manifest(other,self.store.prefs.get('general.locale'))})
                except (OSError,ValueError):pass
            profiles=terminal_profiles()
            options={'extensionId':eid,'manifest':manifest,'extensions':extensions,'storage':str(self.store.root/'.runtime-data'/eid),'locale':self.store.prefs.get('general.locale'),'shell':profiles[0]['argv'][0] if profiles else None}
            self.stop(eid);self.hosts[eid]=Host(node,root,entry,workspace,options,self.services)
            self.approve(workspace,eid)
            self.store.prefs.audit('extension.execute',extension=eid)
        return self.snapshot()
    def request(self, workspace, body):
        if not workspace.trusted:raise PermissionError('Proyecto no autorizado.')
        host=self.hosts.get(body.get('id'))
        if not host:raise ValueError('Inicia el motor de la extensión primero.')
        method=body.get('method')
        if method not in ('command','provide','virtual','willSave','didSave','tree','resolveAction','decorations','webviewMessage','webviewDispose'):raise ValueError('Operación no válida.')
        if method=='decorations':
            paths=body.get('paths')
            if not isinstance(paths,list) or len(paths)>300:raise ValueError('Lista de decoraciones no válida.')
            for path in paths:
                if not isinstance(path,str):raise ValueError('Ruta de decoración no válida.')
                workspace.resolve(path,must_exist=False)
        document=body.get('document',{})
        if document.get('path'):
            candidate=Path(document['path'])
            if candidate.is_absolute():
                from .extension_services import file_path
                file_path(str(candidate))
            else:workspace.resolve(document['path'],must_exist=False)
        return host.request({k:body[k] for k in ('method','command','kind','document','position','range','uri','arguments','reason','newName','view','element','context','options','character','positions','color','action','paths','revision','panel','message') if k in body})
    def stop(self,eid,forget=False):
        with self.lock:
            if forget:
                for key,ids in self.approvals.items():self.approvals[key]=[x for x in ids if x!=eid]
                atomic_json(self.approvals_path,self.approvals)
            self.errors.pop(eid,None)
            host=self.hosts.pop(eid,None)
            if host:host.close()
        return self.snapshot()
    def shutdown(self):
        for eid in list(self.hosts):self.stop(eid)
