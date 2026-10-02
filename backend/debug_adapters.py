"""Real DAP and Node inspector clients. Adapters run only in a trusted workspace."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import queue
import re
import socket
import subprocess
import threading
import time
from .terminals import child_environment

class ProtocolDebugger:
    def __init__(self):
        self.state={'status':'idle','output':'','variables':[],'stack':[]};self.lock=threading.RLock();self.write_lock=threading.Lock()
        self.pending={};self.seq=0;self.process=None;self.closed=False;self.connection=None;self.thread_id=1;self.initialized=threading.Event()
        self.debuggee=None;self.input_pipe=None
    def snapshot(self):
        with self.lock:return copy.deepcopy(self.state)
    def update(self,**changes):
        with self.lock:self.state.update(changes)
    def output(self,text):
        with self.lock:self.state['output']=(self.state['output']+text)[-100000:]
    def request(self,method,args=None,wait=True,timeout=15):
        with self.lock:
            self.seq+=1;seq=self.seq;channel=queue.Queue();self.pending[seq]=channel
        self.send({'seq':seq,'type':'request','command':method,'arguments':args or {}})
        if not wait:return (seq,channel)
        return self.answer((seq,channel),timeout)
    def answer(self,ticket,timeout=15):
        seq,channel=ticket
        try:
            response=channel.get(timeout=timeout)
            if not response.get('success',False):raise ValueError(response.get('message') or response.get('body',{}).get('error',{}).get('format') or 'El adaptador rechazó la operación.')
            return response.get('body',{})
        except queue.Empty:raise ValueError('El depurador no respondió a tiempo.')
        finally:
            with self.lock:self.pending.pop(seq,None)
    def send(self,message):
        raw=json.dumps(message).encode()
        with self.write_lock:
            if self.closed:raise ValueError('Depurador cerrado.')
            stream=self.connection or self.process.stdin
            if self.connection:self.connection.sendall(f'Content-Length: {len(raw)}\r\n\r\n'.encode()+raw)
            else:stream.write(f'Content-Length: {len(raw)}\r\n\r\n'.encode()+raw);stream.flush()
    def read(self,stream):
        try:
            while not self.closed:
                headers={};count=0
                while True:
                    line=stream.readline(4096)
                    if not line:return
                    count+=len(line)
                    if count>8192:raise ValueError('Cabecera DAP excesiva.')
                    if line in (b'\r\n',b'\n'):break
                    key,_,value=line.partition(b':');headers[key.lower().strip()]=value.strip()
                length=int(headers.get(b'content-length',0))
                if not 0<length<=4_000_000:raise ValueError('Mensaje DAP no válido.')
                message=json.loads(stream.read(length))
                if message.get('type')=='response':
                    if target:=self.pending.get(message.get('request_seq')):target.put(message)
                elif message.get('type')=='event':self.event(message.get('event'),message.get('body',{}))
                elif message.get('type')=='request':threading.Thread(target=self.reverse_request,args=(message,),daemon=True).start()
        except (OSError,ValueError,TypeError) as exc:
            if not self.closed:self.update(status='error',error=str(exc))
        finally:
            stream.close()
            for channel in list(self.pending.values()):channel.put({'success':False,'message':'La conexión de depuración terminó.'})
            if not self.closed and self.state['status'] not in ('error','finished','stopped'):self.update(status='error',error='El adaptador terminó antes de completar la sesión.',variables=[],stack=[])
    def drain(self,stream):
        with stream:
            for line in stream:self.output(line.decode('utf-8','replace'))
    def reverse_request(self,message):
        reply={'seq':0,'type':'response','request_seq':message['seq'],'command':message['command'],'success':False}
        try:
            if message['command']!='runInTerminal':raise ValueError('Petición inversa DAP no compatible.')
            args=message.get('arguments',{});argv=args.get('args')
            if args.get('argsCanBeInterpretedByShell') or not isinstance(argv,list) or not argv or any(not isinstance(x,str) or '\x00' in x for x in argv):raise ValueError('El adaptador debe proporcionar argumentos sin shell.')
            if self.closed:raise ValueError('Sesión cerrada.')
            env=child_environment()
            for key,value in args.get('env',{}).items():
                if value is None:env.pop(key,None)
                elif isinstance(value,str):env[key]=value
            self.debuggee=subprocess.Popen(argv,cwd=args.get('cwd') or self.root,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            def output():
                import codecs
                decoder=codecs.getincrementaldecoder('utf-8')('replace')
                with self.debuggee.stdout as stream:
                    while chunk:=stream.read1(4096):self.output(decoder.decode(chunk))
            threading.Thread(target=output,daemon=True).start()
            reply.update(success=True,body={'processId':self.debuggee.pid})
        except Exception as exc:reply['message']=str(exc)
        try:self.send(reply)
        except (OSError,ValueError):pass
    def input(self,text):
        if self.input_pipe:return self.input_pipe.write(text)
        if not self.debuggee or self.debuggee.poll() is not None:raise ValueError('Este adaptador no abrió entrada integrada.')
        self.debuggee.stdin.write(text.encode('utf-8'));self.debuggee.stdin.flush();return {'ok':True}
    def stderr(self):
        with self.process.stderr as stream:
            for line in stream:self.output(line.decode('utf-8','replace'))
    def start(self,ws,path,points,argv,launch,transport='stdio',port=0):
        self.update(status='running',path=path,engine='DAP');self.root=ws.root
        self.lldb='lldb' in Path(argv[0]).stem.lower()
        env=child_environment()
        if os.name=='nt':env['PATH']=env.get('PATH','')+os.pathsep+'C:/msys64/ucrt64/bin'+os.pathsep+'C:/msys64/mingw64/bin'
        support=Path(__file__).resolve().parents[1]/'debugger-support/python311'
        if 'lldb' in Path(argv[0]).stem.lower() and support.is_dir():env['PATH']=str(support)+os.pathsep+env.get('PATH','');env['PYTHONHOME']=str(support);env['PYTHONPATH']=os.pathsep.join([str(support/'python311.zip'),str(support),str(Path(argv[0]).parent.parent/'lib/site-packages')])
        self.process=subprocess.Popen(argv,cwd=ws.root,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        threading.Thread(target=self.stderr,daemon=True).start()
        if transport=='tcp':
            deadline=time.monotonic()+10
            while True:
                try:self.connection=socket.create_connection(('127.0.0.1',port),timeout=1);self.connection.settimeout(None);break
                except OSError:
                    if time.monotonic()>deadline or self.process.poll() is not None:raise ValueError('El adaptador DAP no abrió su puerto local.')
                    time.sleep(.05)
            stream=self.connection.makefile('rb')
            threading.Thread(target=self.drain,args=(self.process.stdout,),daemon=True).start()
        else:stream=self.process.stdout
        threading.Thread(target=self.read,args=(stream,),daemon=True).start()
        capabilities=self.request('initialize',{'clientID':'lumen','clientName':'Lumen Studio','adapterID':'lumen','pathFormat':'path','linesStartAt1':True,'columnsStartAt1':True,'supportsVariableType':True,'supportsRunInTerminalRequest':True})
        launch=dict(launch);entry=launch.pop('_lumenEntry',False);self.entry_function=launch.pop('_lumenEntryFunction',None)
        version=re.search(r'lldb version (\d+)',capabilities.get('$__lldb_version',''))
        if os.name=='nt' and self.lldb and version and int(version[1])>=22 and launch.get('console')=='internalConsole' and 'stdio' not in launch:
            from .debug_input import DebugInput
            self.input_pipe=DebugInput();launch['stdio']=[self.input_pipe.path,None,None]
        ticket=self.request('launch',launch,wait=False)
        if not self.initialized.wait(15):raise ValueError('El adaptador no anunció que está preparado. '+self.snapshot()['output'][-600:])
        self.breakpoint_source=str(ws.resolve(path));self.user_points=points;self.temporary_entry=entry and 1 not in points
        bps=self.request('setBreakpoints',{'source':{'path':self.breakpoint_source},'breakpoints':[{'line':line} for line in sorted(set(points+([1] if entry else [])))]}).get('breakpoints',[])
        for bp in bps:
            if not bp.get('verified'):self.output('Punto pendiente: '+str(bp.get('line',''))+' '+bp.get('message','')+'\n')
        if self.entry_function:self.request('setFunctionBreakpoints',{'breakpoints':[{'name':self.entry_function}]})
        if capabilities.get('supportsConfigurationDoneRequest'):self.request('configurationDone')
        self.answer(ticket,30);return self.snapshot()
    def event(self,name,body):
        if name=='initialized':self.initialized.set()
        elif name=='output':self.output(body.get('output',''))
        elif name in ('terminated','exited'):self.update(status='finished',variables=[],stack=[])
        elif name=='continued':self.update(status='running',variables=[],stack=[])
        elif name=='stopped':
            self.thread_id=body.get('threadId',1);threading.Thread(target=self.inspect,daemon=True).start()
    def inspect(self):
        try:
            stack=self.request('stackTrace',{'threadId':self.thread_id,'startFrame':0,'levels':25}).get('stackFrames',[]);variables=[]
            if stack:
                scopes=self.request('scopes',{'frameId':stack[0]['id']}).get('scopes',[])
                for scope in scopes:
                    if scope.get('expensive'):continue
                    for item in self.request('variables',{'variablesReference':scope['variablesReference']}).get('variables',[])[:100]:variables.append({'name':item['name'],'value':item.get('value','')[:400],'type':item.get('type','')})
                    if variables:break
            self.update(status='paused',line=stack[0].get('line',0) if stack else 0,path=stack[0].get('source',{}).get('path',self.state.get('path','')) if stack else self.state.get('path',''),
                stack=[{'name':f.get('name',''),'path':f.get('source',{}).get('path',''),'line':f.get('line',0)} for f in stack],variables=variables)
        except ValueError as exc:self.update(status='error',error=str(exc))
    def command(self,command):
        if command=='stop':self.stop();return self.snapshot()
        methods={'continue':'continue','next':'next','step':'stepIn','out':'stepOut','pause':'pause'}
        if command not in methods:raise ValueError('Comando de depuración no válido.')
        if getattr(self,'entry_function',None):self.request('setFunctionBreakpoints',{'breakpoints':[]});self.entry_function=None
        if getattr(self,'temporary_entry',False):
            self.request('setBreakpoints',{'source':{'path':self.breakpoint_source},'breakpoints':[{'line':line} for line in self.user_points]});self.temporary_entry=False
        self.update(status='running');self.request(methods[command],{'threadId':self.thread_id});return self.snapshot()
    def stop(self):
        if self.input_pipe:self.input_pipe.close();self.input_pipe=None
        if self.closed:return
        if self.process and self.process.poll() is None:
            try:self.request('disconnect',{'terminateDebuggee':True},timeout=2)
            except (ValueError,OSError):pass
        self.closed=True
        if self.debuggee and self.debuggee.poll() is None:
            if os.name=='nt':subprocess.run(['taskkill','/PID',str(self.debuggee.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=5)
            else:self.debuggee.kill()
        if self.connection:
            try:self.connection.shutdown(socket.SHUT_RDWR);self.connection.close()
            except OSError:pass
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                try:self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
            if self.process.stdin:
                try:self.process.stdin.close()
                except OSError:pass
        self.update(status='stopped',variables=[],stack=[])

class NodeDebugger(ProtocolDebugger):
    def start_node(self,ws,path,points,node):
        import websocket
        self.scripts={};self.file=ws.resolve(path);self.update(status='running',path=path,engine='Node Inspector');self.inspector_url=None
        self.process=subprocess.Popen([node,'--inspect-brk=127.0.0.1:0',str(self.file)],cwd=ws.root,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=child_environment(),creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        def stderr():
            with self.process.stderr as stream:
                for raw in stream:
                    line=raw.decode('utf-8','replace');match=re.search(r'ws://127\.0\.0\.1:\d+/[\w-]+',line)
                    if match:self.inspector_url=match.group(0);self.initialized.set()
                    elif 'Waiting for the debugger to disconnect' in line:self.update(status='finished',variables=[],stack=[]);self.connection.close()
                    elif not line.startswith(('Debugger attached','For help, see:')):self.output(line)
        threading.Thread(target=stderr,daemon=True).start()
        threading.Thread(target=self.drain,args=(self.process.stdout,),daemon=True).start()
        if not self.initialized.wait(10):raise ValueError('Node no inició el inspector. '+self.state['output'])
        self.connection=websocket.create_connection(self.inspector_url,timeout=10,suppress_origin=True);self.connection.settimeout(None)
        threading.Thread(target=self.read_ws,daemon=True).start()
        self.cdp('Runtime.enable');self.cdp('Debugger.enable')
        for line in points:self.cdp('Debugger.setBreakpointByUrl',{'url':self.file.as_uri(),'lineNumber':line-1})
        self.cdp('Runtime.runIfWaitingForDebugger');return self.snapshot()
    def cdp(self,method,params=None):
        with self.lock:self.seq+=1;seq=self.seq;channel=queue.Queue();self.pending[seq]=channel
        with self.write_lock:self.connection.send(json.dumps({'id':seq,'method':method,'params':params or {}}))
        try:
            response=channel.get(timeout=12)
            if 'error' in response:raise ValueError(response['error'].get('message','Error del inspector'))
            return response.get('result',{})
        except queue.Empty:raise ValueError('El inspector de Node no respondió.')
        finally:self.pending.pop(seq,None)
    def read_ws(self):
        try:
            while not self.closed:
                raw=self.connection.recv()
                if not raw:break
                msg=json.loads(raw)
                if 'id' in msg:
                    if channel:=self.pending.get(msg['id']):channel.put(msg)
                elif msg.get('method')=='Debugger.scriptParsed':self.scripts[msg['params']['scriptId']]=msg['params'].get('url','')
                elif msg.get('method')=='Debugger.paused':threading.Thread(target=self.inspect_node,args=(msg['params'],),daemon=True).start()
                elif msg.get('method')=='Debugger.resumed':self.update(status='running')
        except Exception as exc:
            if not self.closed and self.state['status']!='finished':self.update(status='error',error=str(exc))
    def inspect_node(self,body):
        try:
            frames=body.get('callFrames',[]);variables=[]
            if frames:
                for scope in frames[0].get('scopeChain',[]):
                    if scope['type'] not in ('local','block','script'):continue
                    values=self.cdp('Runtime.getProperties',{'objectId':scope['object']['objectId'],'ownProperties':True})
                    for item in values.get('result',[])[:100]:
                        value=item.get('value',{});variables.append({'name':item.get('name',''),'type':value.get('type',''),'value':str(value.get('value',value.get('description','')) )[:400]})
            self.update(status='paused',line=frames[0]['location']['lineNumber']+1 if frames else 0,variables=variables,
                stack=[{'name':f.get('functionName') or '<module>','path':f.get('url') or self.scripts.get(f['location']['scriptId'],'<runtime>'),'line':f['location']['lineNumber']+1} for f in frames[:25]])
        except ValueError as exc:self.update(status='error',error=str(exc))
    def command(self,command):
        if command=='stop':self.stop();return self.snapshot()
        method={'continue':'Debugger.resume','next':'Debugger.stepOver','step':'Debugger.stepInto','out':'Debugger.stepOut','pause':'Debugger.pause'}.get(command)
        if not method:raise ValueError('Comando no válido.')
        self.cdp(method);return self.snapshot()
    def stop(self):
        self.closed=True
        if self.connection:self.connection.close()
        if self.process:
            if self.process.poll() is None:self.process.terminate();self.process.wait(timeout=4)
            for stream in (self.process.stdout,self.process.stderr):
                if stream and not stream.closed:stream.close()
        self.update(status='stopped',variables=[],stack=[])
