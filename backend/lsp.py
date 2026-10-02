"""Small explicit LSP stdio client. No VS Code extension host or shell execution.

Supports initialize, text sync, completion, hover, definition and symbols.
Language servers are independent, user-installed executables in trusted projects.
"""
from __future__ import annotations
import json
import os
import queue
import signal
import subprocess
import threading
import uuid
from pathlib import Path
from urllib.parse import urlparse,unquote
from .toolchains import validate_argv
from .terminals import child_environment

METHODS={'textDocument/inlayHint','textDocument/semanticTokens/full','textDocument/references','textDocument/completion','completionItem/resolve','textDocument/hover','textDocument/definition','textDocument/documentSymbol'}
NOTIFICATIONS={'textDocument/didOpen','textDocument/didChange','textDocument/didClose','textDocument/didSave'}
MAX_MESSAGE=4_000_000


class LanguageSession:
    def __init__(self,profile,ws):
        self.id=uuid.uuid4().hex;self.profile=profile;self.root=ws.root;self.pending={};self.lock=threading.RLock();self.write_lock=threading.Lock()
        self.sequence=0;self.events=[];self.event_seq=0;self.closed=False;self.stderr=''
        argv=validate_argv(profile['argv'])
        opts={'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {'start_new_session':True}
        self.process=subprocess.Popen(argv,cwd=self.root,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=child_environment(),**opts)
        self.reader=threading.Thread(target=self._read,daemon=True);self.reader.start()
        threading.Thread(target=self._stderr,daemon=True).start()
        try:
            self.capabilities=self.request('initialize',{'processId':os.getpid(),'clientInfo':{'name':'Lumen','version':'0.4.0'},'rootUri':self.root.as_uri(),
                'workspaceFolders':[{'uri':self.root.as_uri(),'name':self.root.name}],
                'capabilities':{'general':{'positionEncodings':['utf-16']},'textDocument':{'synchronization':{'didSave':True},
                    'completion':{'completionItem':{'snippetSupport':True}},'hover':{'contentFormat':['plaintext','markdown']},
                    'definition':{'linkSupport':True},'inlayHint':{'dynamicRegistration':False},'semanticTokens':{'requests':{'full':True},'tokenTypes':['namespace','type','class','enum','interface','struct','typeParameter','parameter','variable','property','enumMember','event','function','method','macro','keyword','modifier','comment','string','number','regexp','operator'],'tokenModifiers':['declaration','definition','readonly','static','deprecated','abstract','async','modification','documentation','defaultLibrary'],'formats':['relative']},'publishDiagnostics':{'versionSupport':True}},'workspace':{'applyEdit':False,'configuration':True}},
                'initializationOptions':profile.get('initializationOptions')},timeout=12).get('capabilities',{})
            if self.capabilities.get('positionEncoding','utf-16')!='utf-16':raise ValueError('Este cliente requiere posiciones LSP UTF-16.')
            self.notify('initialized',{})
        except Exception:self.close();raise
    def _stderr(self):
        try:
            for line in iter(self.process.stderr.readline,b''):
                with self.lock:self.stderr=(self.stderr+line.decode('utf-8','replace'))[-12000:]
        finally:self.process.stderr.close()
    def _emit(self,method,params):
        with self.lock:
            self.event_seq+=1;self.events.append({'seq':self.event_seq,'method':method,'params':params})
            self.events=self.events[-300:]
    def _read(self):
        try:
            stream=self.process.stdout
            while not self.closed:
                headers={};budget=0
                while True:
                    line=stream.readline(4096)
                    if not line:return
                    budget+=len(line)
                    if budget>8192:raise ValueError('Cabecera LSP demasiado grande.')
                    if line in (b'\r\n',b'\n'):break
                    key,sep,value=line.partition(b':')
                    if sep:headers[key.lower().strip()]=value.strip()
                length=int(headers.get(b'content-length',b'0'))
                if not 0<length<=MAX_MESSAGE:raise ValueError('Longitud LSP inválida.')
                raw=stream.read(length)
                if len(raw)!=length:return
                message=json.loads(raw)
                if not isinstance(message,dict):continue
                if 'method' in message:
                    if 'id' in message:
                        method=message['method']
                        if method=='workspace/configuration':
                            result=[]
                            for item in message.get('params',{}).get('items',[])[:100]:
                                value=self.profile.get('settings',{})
                                for key in str(item.get('section','')).split('.'):
                                    if key:value=value.get(key,{}) if isinstance(value,dict) else {}
                                result.append(value)
                        elif method=='workspace/applyEdit':result={'applied':False,'failureReason':'Lumen requires explicit user review.'}
                        else:result=None
                        self._write({'jsonrpc':'2.0','id':message['id'],'result':result})
                    else:self._emit(message['method'],message.get('params',{}))
                elif 'id' in message:
                    with self.lock:channel=self.pending.get(message['id'])
                    if channel:channel.put(message)
        except (OSError,ValueError,TypeError) as e:self._emit('lumen/error',{'message':str(e)})
        finally:
            self.closed=True
            with self.lock:
                for channel in self.pending.values():channel.put({'error':{'message':'El servidor LSP ha terminado.'}})
    def _write(self,message):
        raw=json.dumps(message,ensure_ascii=False).encode('utf-8')
        if len(raw)>MAX_MESSAGE:raise ValueError('Mensaje LSP demasiado grande.')
        if self.closed or self.process.poll() is not None:raise ValueError('Servidor LSP detenido.')
        with self.write_lock:self.process.stdin.write(f'Content-Length: {len(raw)}\r\n\r\n'.encode()+raw);self.process.stdin.flush()
    def request(self,method,params,timeout=12):
        with self.lock:self.sequence+=1;ident=self.sequence;channel=queue.Queue();self.pending[ident]=channel
        try:
            self._write({'jsonrpc':'2.0','id':ident,'method':method,'params':params})
            try:response=channel.get(timeout=timeout)
            except queue.Empty:
                self.notify('$/cancelRequest',{'id':ident});raise ValueError('Tiempo de espera LSP agotado.')
            if 'error' in response:raise ValueError(str(response['error'].get('message','Error LSP'))[:600])
            return response.get('result')
        finally:
            with self.lock:self.pending.pop(ident,None)
    def notify(self,method,params):self._write({'jsonrpc':'2.0','method':method,'params':params})
    def validate_params(self,params):
        if not isinstance(params,dict):raise ValueError('Parámetros LSP no válidos.')
        if len(json.dumps(params))>2_000_000:raise ValueError('Documento LSP demasiado grande.')
        def visit(obj):
            if isinstance(obj,dict):
                for key,val in obj.items():
                    if key=='uri' and isinstance(val,str):
                        p=urlparse(val)
                        if p.scheme!='file' or p.netloc not in ('','localhost'):raise PermissionError('Solo archivos locales del proyecto.')
                        raw=unquote(p.path)
                        if os.name=='nt' and re.match(r'^/[A-Za-z]:',raw):raw=raw[1:]
                        if not Path(raw).resolve().is_relative_to(self.root.resolve()):raise PermissionError('URI fuera del proyecto.')
                    else:visit(val)
            elif isinstance(obj,list):
                for item in obj:visit(item)
        import re
        visit(params);return params
    def poll(self,after):
        with self.lock:return {'events':[x for x in self.events if x['seq']>after],'sequence':self.event_seq,'closed':self.closed,'stderr':self.stderr}
    def close(self):
        if self.process.poll() is None:
            if not self.closed:
                try:self.request('shutdown',None,timeout=1);self.notify('exit',None)
                except (ValueError,OSError):pass
            try:self.process.wait(timeout=.7)
            except subprocess.TimeoutExpired:
                if os.name=='nt':self.process.kill()
                else:
                    try:os.killpg(self.process.pid,signal.SIGTERM)
                    except OSError:pass
                try:self.process.wait(timeout=1)
                except subprocess.TimeoutExpired:self.process.kill()
        self.closed=True
        for stream in (self.process.stdin,self.process.stdout):
            try:stream.close()
            except OSError:pass


class LanguageServers:
    def __init__(self,prefs,toolchains):self.prefs=prefs;self.toolchains=toolchains;self.sessions={};self.lock=threading.RLock()
    def start(self,ws,profile_id,consent=False):
        if not ws.trusted or consent is not True:raise PermissionError('Autoriza este ejecutable LSP en un proyecto de confianza.')
        profile=next((p for p in self.toolchains.config['servers'] if p['id']==profile_id),None)
        if not profile:raise FileNotFoundError('Servidor de lenguaje no configurado.')
        with self.lock:
            if len(self.sessions)>=5:raise ValueError('Detén un servidor antes de abrir otro.')
            session=LanguageSession(profile,ws);self.sessions[session.id]=session
        self.prefs.audit('lsp.start',id=profile_id)
        return {'id':session.id,'capabilities':session.capabilities,'rootUri':ws.root.as_uri(),'languages':profile['languages'],'profile':profile_id}
    def get(self,sid):
        with self.lock:
            if sid not in self.sessions:raise FileNotFoundError('Sesión LSP desconocida.')
            return self.sessions[sid]
    def request(self,sid,method,params):
        if method not in METHODS:raise PermissionError('Método LSP no expuesto por Lumen.')
        s=self.get(sid);return {'result':s.request(method,s.validate_params(params))}
    def notify(self,sid,method,params):
        if method not in NOTIFICATIONS:raise PermissionError('Notificación LSP no admitida.')
        s=self.get(sid);s.notify(method,s.validate_params(params));return {'ok':True}
    def stop(self,sid):
        with self.lock:s=self.sessions.pop(sid,None)
        if s:s.close()
        return {'stopped':bool(s)}
    def shutdown(self):
        for sid in list(self.sessions):self.stop(sid)
