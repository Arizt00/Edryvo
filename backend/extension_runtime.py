"""Opt-in executable extensions. One killable Node process per extension, no UI blocking."""
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import uuid
from .extensions import json_resource
from .runtime_paths import find_tool
from .terminals import child_environment


class Host:
    def __init__(self, node, root, entry, workspace, options):
        self.lock=threading.Lock();self.responses=queue.Queue();self.logs=''
        self.process=subprocess.Popen([node,str(Path(__file__).with_name('extension_host.cjs'))],cwd=workspace.root,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=child_environment(),creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        threading.Thread(target=self.read,daemon=True).start();threading.Thread(target=self.read_errors,daemon=True).start()
        try:self.capabilities=self.request({'method':'activate','entry':str(entry),'root':str(root),'workspace':str(workspace.root),**options})
        except Exception:self.close();raise

    def read(self):
        try:
            while line:=self.process.stdout.readline(2_000_001):
                if len(line)>2_000_000:self.close();break
                try:self.responses.put(json.loads(line))
                except ValueError:pass
        except (OSError,ValueError):pass
        finally:self.responses.put({'error':'El proceso de la extensión terminó.'})

    def read_errors(self):
        try:
            while data:=self.process.stderr.read1(4096):self.logs=(self.logs+data.decode('utf-8','replace'))[-12000:]
        except (OSError,ValueError):pass

    def request(self, message):
        with self.lock:
            message={**message,'id':uuid.uuid4().hex}
            raw=json.dumps(message).encode()+b'\n'
            if len(raw)>2_000_000:raise ValueError('Documento demasiado grande para la extensión.')
            self.process.stdin.write(raw);self.process.stdin.flush()
            try:result=self.responses.get(timeout=10)
            except queue.Empty:self.close();raise ValueError('La extensión no respondió en 10 segundos. Se detuvo su proceso.')
            if result.get('error'):raise ValueError(result['error'])
            if result.get('id')!=message['id']:raise ValueError('Respuesta inesperada de la extensión.')
            return result['result']

    def close(self):
        if self.process.poll() is None:
            if os.name=='nt':subprocess.run(['taskkill','/PID',str(self.process.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=5)
            else:self.process.kill()
        try:self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:self.process.kill()
        for stream in (self.process.stdin,self.process.stdout,self.process.stderr):
            try:stream.close()
            except (OSError,ValueError):pass


class ExtensionRuntime:
    def __init__(self, store):self.store=store;self.hosts={};self.lock=threading.RLock()
    def snapshot(self):
        with self.lock:return {'hosts':[{'id':key,'running':host.process.poll() is None,**host.capabilities,'logs':host.logs} for key,host in self.hosts.items()]}
    def start(self, workspace, eid, consent):
        if consent is not True or not workspace.trusted:raise PermissionError('Autoriza la extensión ejecutable en un proyecto de confianza.')
        with self.lock:
            info=self.store.installed.get(eid)
            if not info or not info.get('enabled'):raise ValueError('Activa primero la extensión instalada.')
            root=(self.store.root/info['directory']/'extension').resolve();manifest=json_resource(root,'package.json')
            entry=(root/manifest.get('lumen',{}).get('main',manifest.get('main',''))).resolve()
            if entry.suffix not in ('.js','.cjs','.mjs') and entry.with_suffix('.js').is_file():entry=entry.with_suffix('.js')
            if not entry.is_relative_to(root) or not entry.is_file() or entry.suffix not in ('.js','.cjs','.mjs'):raise ValueError('La extensión necesita un main Node.js compatible con la API preview.')
            node=find_tool('node')
            if not node:raise ValueError('Instala Node.js para ejecutar extensiones.')
            extensions=[]
            for item in self.store.list():
                other=self.store.root/item['directory']/'extension'
                try:extensions.append({'id':item['id'],'root':str(other),'manifest':json_resource(other,'package.json')})
                except (OSError,ValueError):pass
            options={'extensionId':eid,'manifest':manifest,'extensions':extensions,'storage':str(self.store.root/'.runtime-data'/eid),'locale':self.store.prefs.get('general.locale')}
            self.stop(eid);self.hosts[eid]=Host(node,root,entry,workspace,options)
            self.store.prefs.audit('extension.execute',extension=eid)
        return self.snapshot()
    def request(self, workspace, body):
        if not workspace.trusted:raise PermissionError('Proyecto no autorizado.')
        host=self.hosts.get(body.get('id'))
        if not host:raise ValueError('Inicia el motor de la extensión primero.')
        method=body.get('method')
        if method not in ('command','provide','virtual'):raise ValueError('Operación no válida.')
        document=body.get('document',{})
        if document.get('path'):workspace.resolve(document['path'],must_exist=False)
        return host.request({k:body[k] for k in ('method','command','kind','document','position','range','uri','arguments') if k in body})
    def stop(self,eid):
        with self.lock:
            host=self.hosts.pop(eid,None)
            if host:host.close()
        return self.snapshot()
    def shutdown(self):
        for eid in list(self.hosts):self.stop(eid)
