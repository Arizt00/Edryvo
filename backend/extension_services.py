"""Bidirectional extension services backed by real terminals, buffers and DAP."""
import base64
import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
import uuid
from urllib.parse import unquote,urlsplit
from .terminals import TerminalSession,terminal_profiles,child_environment
from .debug_adapters import ProtocolDebugger


def file_path(uri):
    value=uri.get('external') or uri.get('value') if isinstance(uri,dict) else uri
    if isinstance(uri,dict) and uri.get('fsPath'):value=uri['fsPath']
    if not isinstance(value,str) or '\x00' in value:raise ValueError('URI de archivo inválida.')
    if value.startswith('file:'):
        parsed=urlsplit(value)
        if parsed.netloc not in ('','localhost'):raise ValueError('No se admiten archivos remotos.')
        value=unquote(parsed.path)
        if os.name=='nt' and len(value)>2 and value[0]=='/' and value[2]==':':value=value[1:]
    elif '://' in value:raise ValueError('Esta operación requiere un URI file.')
    p=Path(value).resolve()
    if not Path(value).is_absolute():raise ValueError('Se necesita una ruta absoluta.')
    return p


def text_edit(text,edits):
    """LSP/VS Code positions count UTF-16 code units, including CRLF offsets."""
    lines=text.splitlines(keepends=True)
    if not lines or text.endswith(('\n','\r')):lines.append('')
    def offset(p):
        line=p.get('line');column=p.get('character')
        if type(line) is not int or type(column) is not int or not 0<=line<len(lines) or column<0:raise ValueError('Posición de edición inválida.')
        body=lines[line].rstrip('\r\n');units=0
        for index,char in enumerate(body):
            if units==column:return sum(map(len,lines[:line]))+index
            units+=2 if ord(char)>0xffff else 1
        if units!=column:raise ValueError('Columna de edición inválida.')
        return sum(map(len,lines[:line]))+len(body)
    ranges=[]
    for e in edits:
        a=offset(e['range']['start']);b=offset(e['range']['end']);new=e['newText']
        if b<a or not isinstance(new,str):raise ValueError('Edición de texto inválida.')
        ranges.append((a,b,new))
    ranges.sort(key=lambda x:(x[0],x[1]))
    for first,second in zip(ranges,ranges[1:]):
        if first[1]>second[0]:raise ValueError('Las ediciones se solapan.')
    for a,b,new in reversed(ranges):text=text[:a]+new+text[b:]
    if len(text)>2_000_000:raise ValueError('Búfer de extensión demasiado grande.')
    return text


class ExtensionDebugger(ProtocolDebugger):
    def __init__(self,owner,ident):super().__init__();self.owner=owner;self.ident=ident;self.inline=False;self.notified=False;self.pipe=None;self.source_breakpoints=set()
    def send(self,message):
        if self.inline:self.owner.event('debug.send',{'id':self.ident,'message':message})
        elif self.pipe:
            raw=json.dumps(message).encode('utf-8')
            with self.write_lock:self.pipe.write(f'Content-Length: {len(raw)}\r\n\r\n'.encode()+raw)
        else:super().send(message)
    def receive(self,message):
        if message.get('type')=='response':
            target=self.pending.get(message.get('request_seq'))
            if target:target.put(message)
        elif message.get('type')=='event':self.event(message.get('event'),message.get('body',{}))
        elif message.get('type')=='request':threading.Thread(target=self.reverse_request,args=(message,),daemon=True).start()
    def event(self,name,body):
        super().event(name,body);self.owner.event('debug.event',{'id':self.ident,'message':{'type':'event','event':name,'body':body}})
        if name=='terminated':self.finished()
    def finished(self):
        if not self.notified:self.notified=True;self.owner.event('debug.stop',{'id':self.ident})
    def stop(self):
        if self.inline or self.pipe:
            try:self.request('disconnect',{'terminateDebuggee':True},wait=False)
            except (OSError,ValueError):pass
        super().stop()
        if self.pipe:
            try:self.pipe.close()
            except OSError:pass
        self.finished()
    def launch(self,ws,configuration,descriptor,breakpoints):
        self.root=ws.root;self.update(status='running',path=configuration.get('program',''),engine='DAP · '+configuration['type'])
        self.inline=descriptor.get('inline',False)
        if descriptor.get('command'):
            import subprocess
            env=child_environment()
            for key,value in (descriptor.get('options') or {}).get('env',{}).items():
                if value is None:env.pop(key,None)
                else:env[key]=str(value)
            argv=[descriptor['command'],*descriptor.get('args',[])]
            self.process=subprocess.Popen(argv,cwd=(descriptor.get('options') or {}).get('cwd') or ws.root,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            threading.Thread(target=self.stderr,daemon=True).start();stream=self.process.stdout
        elif descriptor.get('port'):
            import socket
            self.connection=socket.create_connection((descriptor.get('host','127.0.0.1'),int(descriptor['port'])),timeout=10);self.connection.settimeout(None);stream=self.connection.makefile('rb')
        elif descriptor.get('path'):
            if os.name=='nt':
                if not descriptor['path'].lower().startswith('\\\\.\\pipe\\'):raise ValueError('El adaptador debe usar un named pipe local.')
                self.pipe=open(descriptor['path'],'r+b',buffering=0);stream=self.pipe
            else:
                import socket
                self.connection=socket.socket(socket.AF_UNIX);self.connection.connect(descriptor['path']);stream=self.connection.makefile('rb')
        elif not self.inline:raise ValueError('Descriptor DAP inválido.')
        if not self.inline:threading.Thread(target=self.read,args=(stream,),daemon=True).start()
        caps=self.request('initialize',{'clientID':'zenit','clientName':'Zénit','adapterID':configuration['type'],'pathFormat':'path','linesStartAt1':True,'columnsStartAt1':True,'supportsVariableType':True,'supportsRunInTerminalRequest':True})
        ticket=self.request(configuration.get('request','launch'),configuration,wait=False)
        if not self.initialized.wait(15):raise ValueError('El adaptador no anunció initialized.')
        self.set_breakpoints(breakpoints)
        if caps.get('supportsConfigurationDoneRequest'):self.request('configurationDone')
        self.answer(ticket,25);return {'started':True}
    def set_breakpoints(self,breakpoints):
        sources={};functions=[]
        for bp in breakpoints:
            if not bp.get('enabled',True):continue
            if 'location' in bp:
                location=bp['location'];source=str(file_path(location['uri']));sources.setdefault(source,[]).append({'line':location['range']['start']['line']+1,**{key:bp[key] for key in ('condition','hitCondition','logMessage') if bp.get(key)}})
            elif 'functionName' in bp:functions.append({'name':bp['functionName']})
        result=[]
        for source in self.source_breakpoints|set(sources):result.extend(self.request('setBreakpoints',{'source':{'path':source},'breakpoints':sources.get(source,[])}).get('breakpoints',[]))
        self.source_breakpoints=set(sources)
        if functions or getattr(self,'had_function_breakpoints',False):result.extend(self.request('setFunctionBreakpoints',{'breakpoints':functions}).get('breakpoints',[]))
        self.had_function_breakpoints=bool(functions);return result


class ExtensionServices:
    def __init__(self,platform):
        self.platform=platform;self.lock=threading.RLock();self.terminals={};self.tasks={};self.panels={};self.debuggers={};self.contexts={};self.prompts={};self.documents={};self.file_workspaces={}
    def file_workspace(self,p):
        from .workspace import Workspace
        with self.lock:
            if p.parent not in self.file_workspaces:self.file_workspaces[p.parent]=Workspace(p.parent,self.platform.app.workspace.native)
            return self.file_workspaces[p.parent]
    def dispose_panel(self,ident):
        self.panels.pop(ident,None)
        for token,item in list(self.documents.items()):
            if item['panel']==ident:del self.documents[token]
    def webview_document(self,ident,html):
        with self.lock:
            if ident not in self.panels:raise FileNotFoundError('El panel se cerró.')
            if not isinstance(html,str) or len(html)>2_000_000:raise ValueError('Documento webview demasiado grande.')
            for token,item in list(self.documents.items()):
                if item['panel']==ident:del self.documents[token]
            token=uuid.uuid4().hex;self.documents[token]={'panel':ident,'html':html,'scripts':bool(self.panels[ident].get('options',{}).get('enableScripts'))};return {'url':'/extension-webview/'+token}
    def webview_content(self,token):
        with self.lock:
            item=self.documents.get(token)
            if not item or item['panel'] not in self.panels:raise FileNotFoundError('Documento webview cerrado.')
            return item.copy()
    def emit(self,command,**data):
        p=self.platform
        with p.command_lock:
            p.command_seq+=1;p.command_events.append({'seq':p.command_seq,'command':command,**data});p.command_events=p.command_events[-500:]
    def key(self,ws,path):
        try:return path.relative_to(ws.root).as_posix()
        except ValueError:return str(path)
    def close_host(self,host):
        for (owner,ident),terminal in list(self.terminals.items()):
            if owner is host:terminal.close()
        for (owner,ident),debugger in list(self.debuggers.items()):
            if owner is host:debugger.stop()
        with self.lock:
            for ident,panel in list(self.panels.items()):
                if panel['owner'] is host:self.dispose_panel(ident)
    def snapshot(self):
        with self.lock:return {'panels':[{k:copy.deepcopy(v) for k,v in panel.items() if k!='owner'} for panel in self.panels.values()]}
    def workspace_edit(self,ws,edit,documents=None):
        if not ws.trusted:raise PermissionError('Proyecto no autorizado.')
        operations=edit.get('operations') or [{'kind':'text',**item} for item in edit.get('changes',[])]
        if not isinstance(operations,list) or len(operations)>1000:raise ValueError('WorkspaceEdit inválido.')
        buffers=self.platform.buffers;undo=[];text={};original={};resources=[];resets=set()
        with self.lock,buffers.lock,tempfile.TemporaryDirectory(prefix='zenit-edit-') as scratch:
            scratch=Path(scratch)
            def safe(uri):
                p=file_path(uri)
                if p==ws.root or p==Path(p.anchor) or p==Path.home():raise ValueError('No se puede cambiar un directorio raíz.')
                return p
            def backup(p):
                if p.exists():
                    target=scratch/uuid.uuid4().hex;shutil.move(str(p),str(target));undo.append(('restore',p,target))
            def get_text(p):
                key=self.key(ws,p);cached=buffers.items.get(key) if p not in resets else None
                if p not in text:
                    text[p]=cached['text'] if cached else p.read_text(encoding='utf-8')
                    if documents and p not in resets:
                        doc=next((d for d in documents if file_path(d['uri'])==p),None)
                        if doc:
                            if cached and cached['text']!=doc['text']:raise ValueError('El archivo cambió en otra ventana.')
                            text[p]=doc['text']
                    original[p]=text[p]
                return text[p]
            try:
                for op in operations:
                    kind=op['kind'];opts=op.get('options') or {}
                    if kind=='text':
                        p=safe(op['uri'])
                        if not p.is_file():raise ValueError('El archivo de texto no existe: '+str(p))
                        text[p]=text_edit(get_text(p),op['edits'])
                    elif kind=='create':
                        p=safe(op['uri'])
                        if p.exists() and not opts.get('overwrite'):
                            if opts.get('ignoreIfExists'):continue
                            raise FileExistsError(str(p))
                        if not p.parent.is_dir():raise FileNotFoundError(str(p.parent))
                        backup(p);p.write_bytes(bytes(op.get('contents') or []));undo.append(('remove',p,None));text.pop(p,None);original.pop(p,None);resets.add(p);resources.append({'kind':kind,'path':self.key(ws,p)})
                    elif kind=='rename':
                        a=safe(op['oldUri']);b=safe(op['newUri'])
                        if a==b:continue
                        if b.is_relative_to(a):raise ValueError('No se puede mover una carpeta dentro de sí misma.')
                        if b.exists() and not opts.get('overwrite'):
                            if opts.get('ignoreIfExists'):continue
                            raise FileExistsError(str(b))
                        if not a.exists() or not b.parent.is_dir():raise FileNotFoundError(str(a))
                        # Preserve unsaved documents before their on-disk path moves.
                        for key in list(buffers.items):
                            source=Path(key) if Path(key).is_absolute() else ws.root/key
                            if source==a or source.is_relative_to(a):get_text(source)
                        for doc in documents or []:
                            source=file_path(doc['uri'])
                            if source==a or source.is_relative_to(a):get_text(source)
                        backup(b);a.rename(b);undo.append(('rename',b,a));resources.append({'kind':kind,'oldPath':self.key(ws,a),'path':self.key(ws,b)})
                        for source in list(text):
                            if source==a or source.is_relative_to(a):
                                target=b/source.relative_to(a);text[target]=text.pop(source);original[target]=original.pop(source)
                    elif kind=='delete':
                        p=safe(op['uri'])
                        if not p.exists():
                            if opts.get('ignoreIfNotExists'):continue
                            raise FileNotFoundError(str(p))
                        if p.is_dir() and not opts.get('recursive') and any(p.iterdir()):raise ValueError('La carpeta no está vacía.')
                        backup(p);resources.append({'kind':kind,'path':self.key(ws,p)})
                        for source in list(text):
                            if source==p or source.is_relative_to(p):text.pop(source)
                    else:raise ValueError('Operación WorkspaceEdit desconocida: '+str(kind))
                # Only after every resource and text operation succeeds, publish buffers.
                for resource in resources:
                    target=resource.get('oldPath',resource['path'])
                    for key in list(buffers.items):
                        if key==target or key.startswith(target+'/') or key.startswith(target+os.sep):
                            previous=buffers.items.pop(key)
                            if resource['kind']=='rename':new=resource['path']+key[len(target):];buffers.items[new]={**previous,'path':new,'sequence':previous['sequence']+1}
                changed=[]
                for p,value in text.items():
                    key=self.key(ws,p);old=buffers.items.get(key);record={'path':key,'text':value,'sequence':(old or {}).get('sequence',0)+1,'saved':False,'revision':(old or {}).get('revision')}
                    buffers.items[key]=record;changed.append({**record,'before':original.get(p,'')})
            except Exception:
                for action,p,target in reversed(undo):
                    if action=='remove':
                        if p.is_dir():shutil.rmtree(p)
                        elif p.exists():p.unlink()
                    elif action=='rename':p.rename(target)
                    else:shutil.move(str(target),str(p))
                raise
        result={'applied':True,'resources':resources,'buffers':changed};self.emit('zenit.workspace.edit',edit=result);return result
    def call(self,host,method,p):
        ws=host.workspace
        if not ws.trusted:raise PermissionError('Proyecto no autorizado.')
        if method=='workspace.applyEdit':return self.workspace_edit(ws,p['edit'],p.get('documents'))
        if method=='workspace.saveDocument':
            target=file_path(p['uri']);key=self.key(ws,target);text=p.get('text')
            if not isinstance(text,str) or len(text)>2_000_000:return {'saved':False}
            buffers=self.platform.buffers
            with self.lock,buffers.lock:
                old=buffers.items.get(key)
                if old and not old.get('saved') and old['text']!=text:return {'saved':False,'conflict':True}
                owner=ws if target.is_relative_to(ws.root) else self.file_workspace(target)
                from .workspace import ConflictError
                try:saved=owner.save(target.relative_to(owner.root).as_posix(),text,p.get('revision'),newline=p.get('newline','LF'),bom=p.get('bom',False))
                except (OSError,ValueError,ConflictError):return {'saved':False}
                record={'path':key,'text':saved['content'],'saved':True,'revision':saved['revision'],'sequence':(old or {}).get('sequence',0)+1}
                buffers.items[key]=record
            self.emit('zenit.document.saved',buffer=record)
            for other in list(self.platform.extension_runtime.hosts.values()):
                if other is not host:other.event('document.saved',{'uri':str(target),'text':record['text'],'revision':record['revision']})
            return {'saved':True,'buffer':record}
        if method=='window.pick':
            ident=uuid.uuid4().hex;reply=threading.Event();prompt={'reply':reply,'result':None}
            with self.lock:self.prompts[ident]=prompt
            self.emit('zenit.pick',id=ident,items=p['items'],options=p.get('options') or {})
            try:reply.wait(40);return prompt['result']
            finally:
                with self.lock:self.prompts.pop(ident,None)
        if method=='context.set':self.contexts[p['key']]=p.get('value');return None
        if method=='command.execute':
            if p['id'] in ('workbench.action.reloadWindow','workbench.action.terminal.focus'):self.emit('zenit.command',id=p['id'],arguments=p.get('args',[]));return None
            raise ValueError('Comando del IDE no implementado: '+p['id'])
        if method=='terminal.create':
            opts=p['options']
            if opts.get('pty'):session=VirtualTerminal(host,p['id'],opts.get('name','Terminal'))
            else:
                if not self.platform.prefs.get('security.terminals'):raise PermissionError('Terminales desactivadas en Ajustes.')
                profiles=terminal_profiles();command=opts.get('shellPath') or (profiles[0]['argv'][0] if profiles else None)
                if not command:raise ValueError('No se encontró un shell local.')
                args=opts.get('shellArgs',[])
                if isinstance(args,str):
                    import shlex
                    args=shlex.split(args,posix=os.name!='nt')
                cwd=file_path(opts['cwd']) if opts.get('cwd') else ws.root
                env={k:str(v) for k,v in (opts.get('env') or {}).items() if v is not None}
                session=TerminalSession({'id':'extension:'+p['id'],'label':opts.get('name') or 'Terminal','kind':'extension','argv':[command,*args]},cwd,self.platform.app.project,environment=env)
            with self.lock:self.terminals[host,p['id']]=session;self.platform.terminals.sessions[session.id]=session
            pid=session.win.pid if getattr(session,'win',None) else session.process.pid if session.process else None
            def monitor():
                while not session.closed and host.process.poll() is None:time.sleep(.1)
                host.event('terminal.close',{'id':p['id'],'code':session.code})
            threading.Thread(target=monitor,daemon=True).start()
            return {'id':session.id,'pid':pid,'dimensions':{'columns':100,'rows':26}}
        if method.startswith('terminal.'):
            session=self.terminals[host,p['id']];action=method.split('.')[1]
            if action=='write':return session.write(p['text'])
            if action=='append':session._append(p['text']);return True
            if action=='finish':session.code=p.get('code');session.closed=True;return True
            if action=='name':session.profile['label']=p['name'];return True
            if action=='show':self.emit('zenit.terminal.show',terminal=session.id,preserveFocus=p.get('preserveFocus',False));return True
            if action=='hide':self.emit('zenit.terminal.hide',terminal=session.id);return True
            if action=='close':session.close();return True
        if method=='task.execute':
            task=p['task'];execution=task['execution'];opts=execution.get('options') or {};env=opts.get('env') or {};cwd=opts.get('cwd') or str(ws.root)
            if 'process' in execution:command=execution['process'];args=execution.get('args',[])
            else:
                import subprocess,shlex
                line=execution.get('commandLine')
                if line is None:
                    values=[execution['command'],*execution.get('args',[])];values=[x.get('value') if isinstance(x,dict) else x for x in values];line=subprocess.list2cmdline(values) if os.name=='nt' else shlex.join(values)
                command=opts.get('executable') or ('cmd.exe' if os.name=='nt' else '/bin/sh');args=[*opts['shellArgs'],line] if opts.get('shellArgs') else (['/d','/s','/c',line] if os.name=='nt' else ['-c',line])
            info=self.call(host,'terminal.create',{'id':p['id'],'options':{'name':task['name'],'shellPath':command,'shellArgs':args,'cwd':cwd,'env':env}})
            self.tasks[host,p['id']]=self.terminals[host,p['id']]
            self.call(host,'terminal.show',{'id':p['id']})
            host.event('task.processStart',{'id':p['id'],'pid':info['pid']});self.watch_task(host,p['id']);return info
        if method=='task.custom':self.tasks[host,p['id']]=self.terminals[host,p['terminal']];self.watch_task(host,p['id']);return True
        if method=='task.terminate':self.tasks[host,p['id']].close();return True
        if method=='webview.create':
            with self.lock:self.panels[p['id']]={**p,'owner':host,'extension':host.extension_id,'html':'','visible':True,'messages':[],'revision':1,'messageSequence':0}
            return True
        if method=='webview.update':
            with self.lock:
                panel=self.panels[p['id']]
                if panel['owner'] is not host:raise PermissionError('Webview de otra extensión.')
                panel.update({k:v for k,v in p.items() if k in ('html','title','visible','column','disposed','options','state','revealSequence')});panel['revision']+=1
                if panel.get('disposed'):self.dispose_panel(p['id'])
            return True
        if method=='webview.post':
            with self.lock:
                panel=self.panels.get(p['id'])
                if not panel or panel['owner'] is not host:return False
                panel['messageSequence']+=1;panel['messages'].append({'seq':panel['messageSequence'],'message':p['message']});panel['messages']=panel['messages'][-100:]
            return True
        if method=='debug.start':
            key=host,p['id'];debugger=ExtensionDebugger(host,p['id']);self.debuggers[key]=debugger
            if self.platform.debugger.snapshot()['status'] in ('running','paused'):raise ValueError('Detén primero la sesión de depuración actual.')
            self.platform.debugger.current=debugger;self.emit('zenit.debug.show')
            try:return debugger.launch(ws,p['configuration'],p['descriptor'],p.get('breakpoints',[]))
            except Exception:debugger.stop();self.debuggers.pop(key,None);raise
        if method=='debug.request':return self.debuggers[host,p['id']].request(p['command'],p.get('args'))
        if method=='debug.breakpoints':return self.debuggers[host,p['id']].set_breakpoints(p['breakpoints'])
        if method=='debug.message':self.debuggers[host,p['id']].receive(p['message']);return True
        if method=='debug.stop':self.debuggers[host,p['id']].stop();return True
        raise ValueError('Servicio no implementado: '+method)
    def watch_task(self,host,ident):
        terminal=self.tasks[host,ident]
        def monitor():
            while not terminal.closed and host.process.poll() is None:time.sleep(.1)
            host.event('task.end',{'id':ident,'code':terminal.code})
        threading.Thread(target=monitor,daemon=True).start()
    def resource(self,ident,value):
        panel=self.panels[ident];p=file_path(value);opts=panel.get('options') or {};roots=opts.get('localResourceRoots')
        if roots is None:roots=[str(panel['owner'].workspace.root),str(panel['owner'].extension_root)]
        allowed=[file_path(r) for r in roots if r]
        if not any(p.is_relative_to(root) for root in allowed):raise PermissionError('Recurso fuera de localResourceRoots.')
        data=p.read_bytes()
        if len(data)>20_000_000:raise ValueError('Recurso webview demasiado grande.')
        import mimetypes
        return {'data':base64.b64encode(data).decode(),'mime':mimetypes.guess_type(p.name)[0] or 'application/octet-stream'}
    def answer_prompt(self,ident,value):
        with self.lock:
            prompt=self.prompts.get(ident)
            if not prompt:raise ValueError('La selección ha caducado.')
            prompt['result']=value;prompt['reply'].set();return {'ok':True}


class VirtualTerminal:
    def __init__(self,host,ident,name):
        self.host=host;self.ident=ident;self.id=uuid.uuid4().hex;self.profile={'id':'extension:'+ident,'label':name,'kind':'extension'};self.process=None;self.closed=False;self.code=None;self.output='';self.kind='Extension PTY';self.start=0;self.lock=threading.RLock()
    _append=TerminalSession._append
    read=TerminalSession.read
    def write(self,text):
        if self.closed:return False
        self.host.event('terminal.input',{'id':self.ident,'text':text});return True
    def resize(self,cols,rows):self.host.event('terminal.dimensions',{'id':self.ident,'dimensions':{'columns':cols,'rows':rows}})
    def close(self):self.closed=True
