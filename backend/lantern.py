"""Live buffer execution with syntax gating, revision ownership and cooperative checkpoints."""
from __future__ import annotations
import copy
import hashlib
import json
import sys
import struct
import shutil
import tempfile
import os
from .terminals import child_environment
from .lantern_adapters import stage, prepare, runtime_commands, Superseded
from .diagnostics import marker
from pathlib import Path
from .preferences import atomic_json
import threading
import time
from functools import wraps
from .diagnostics import output_diagnostics

def serialized_control(method):
    @wraps(method)
    def call(self,*args,**kwargs):
        with self.control_lock:return method(self,*args,**kwargs)
    return call

class Lantern:
    def __init__(self,runtimes,runner,preview):
        self.runtimes=runtimes;self.runner=runner;self.preview=preview
        self.lock=threading.RLock();self.control_lock=threading.RLock();self.event=threading.Event();self.thread=None;self.job=None
        self.memory_dir=None;self.history=[];self.validation=None;self.generation=0;self.content=None;self.version=None;self.shadow=None;self.live_root=None
        self.workspace=None;self.revision=0;self.pending=0;self.stamp=None
        self.state={'active':False,'status':'idle','path':'','revision':0,'output':'','diagnostics':[],'preview':None}

    def snapshot(self):
        with self.lock:
            state=copy.deepcopy(self.state)
            if self.job and state.get("executedGeneration")==self.generation:
                with self.job.lock:
                    state['output']=self.job.output;state['job']=self.job.id;state['code']=self.job.code if self.job.done else None
                    if self.job.done:
                        state['status']='error' if self.job.code else 'watching'
                        state['diagnostics']=output_diagnostics(self.job.output,state['path'])
            state['lens']=[]
            if state.get('active') and state.get('executedGeneration')==self.generation and self.memory_dir:
                try:
                    lens=self.memory_dir/'lens.json'
                    if lens.stat().st_size<=256000:
                        data=json.loads(lens.read_text(encoding='utf-8'))
                        if data.get('generation')==str(self.generation):state['lens']=data.get('values',[])[:200]
                except (OSError,ValueError,TypeError):pass
            state['history']=copy.deepcopy(self.history[-20:])
            state['memoryMode']='Checkpoint cooperativo'
            state['memoryHelp']='Python: lantern_state · JS/TS: lanternState · C/C++: lantern.h / lantern.hpp · nC: estado JSON con esquema y migración.'
            if self.memory_dir:
                state['checkpoint']=str(self.memory_dir/'state.json')
                try: state['memory']=json.loads((self.memory_dir/'state.json').read_text(encoding='utf-8')) if (self.memory_dir/'state.json').stat().st_size<=1_000_000 else {}
                except (OSError,ValueError): state['memory']={}
                native=self.memory_dir/'state.json.native'
                try:
                    with native.open('rb') as stream: magic,schema,size,checksum=struct.unpack('<QQQQ',stream.read(32))
                    if magic==0x4c554d454e4c4e31 and native.stat().st_size==32+size:
                        state['nativeMemory']={'schema':schema,'bytes':size,'checksum':f'{checksum:016x}','path':str(native)}
                except (OSError,ValueError,struct.error):pass
            return state

    def template(self,lang):
        suffix={'c':'c','cpp':'cpp','nc':'n'}.get(lang)
        if not suffix:raise ValueError('El soporte nativo está disponible para C, C++ y nC.')
        root=Path(__file__).resolve().parents[1]
        return {'name':'lantern-example.'+suffix,'content':(root/f'examples/lantern/counter.{suffix}').read_text(encoding='utf-8'),'guide':(root/'debugger-support/lantern/README.md').read_text(encoding='utf-8')}

    def settle(self,job):
        if not job or job.done:return
        # The program cooperates at its next safe point; it must checkpoint then exit.
        if self.memory_dir:(self.memory_dir/'state.json.reload').write_text('checkpoint-and-exit',encoding='ascii')
        deadline=time.monotonic()+2
        while not job.done and time.monotonic()<deadline:time.sleep(.025)
        if not job.done:job.cancel()
        deadline=time.monotonic()+3
        while not job.done and time.monotonic()<deadline:time.sleep(.025)
        if not job.done:raise ValueError('El proceso anterior no se ha detenido; se ha evitado ejecutar dos revisiones a la vez.')

    @serialized_control
    def start(self,workspace,path,content=None,version=None):
        if not workspace.trusted:raise PermissionError('Autoriza el proyecto antes de iniciar Lantern.')
        workspace.resolve(path,must_exist=content is None)
        if content is not None and (not isinstance(content,str) or len(content.encode("utf-8"))>2*1024*1024):raise ValueError("Buffer no válido o mayor de 2 MiB.")
        self.stop()
        with self.lock:
            key=hashlib.sha256(path.encode()).hexdigest()[:24]
            self.memory_dir=workspace.private_dir('lantern')/key;self.memory_dir.mkdir(parents=True,exist_ok=True)
            try:self.history=json.loads((self.memory_dir/'history.json').read_text(encoding='utf-8'))[-20:]
            except (OSError,ValueError):self.history=[]
            self.revision=max([h.get('revision',0) for h in self.history]+[0])
            self.workspace=workspace;self.event=threading.Event();self.pending=time.monotonic()+.15
            self.content=content;self.version=version;self.generation+=1
            self.state={'active':True,'status':'preparing','path':path,'revision':self.revision,'output':'Preparando Lantern…\n','diagnostics':[],'preview':None,'bufferVersion':version,'bufferMode':content is not None,'generation':self.generation,'lens':[]}
            self.stamp=self.signature()
            self.thread=threading.Thread(target=self.watch,args=(self.event,),daemon=True);self.thread.start()
        return self.snapshot()

    def signature(self):
        try:
            p=self.workspace.resolve(self.state['path']);s=p.stat();return(s.st_mtime_ns,s.st_size)
        except (OSError,ValueError,KeyError,PermissionError):return None

    def buffer(self,workspace,path,content,version=None):
        if not isinstance(content,str) or len(content.encode('utf-8'))>2*1024*1024:raise ValueError('Buffer no válido o mayor de 2 MiB.')
        with self.lock:
            if not self.state['active'] or workspace is not self.workspace or path!=self.state['path']:
                return {'ignored':True}
            if content==self.content and version==self.version:return self.snapshot()
            self.content=content;self.version=version;self.generation+=1;self.pending=time.monotonic()+.65
            self.state.update(status='debouncing',bufferVersion=version,bufferMode=True,generation=self.generation,diagnostics=[],lens=[],preview=None,job=None)
            validation=self.validation
        if validation and not validation.done:validation.cancel()
        return self.snapshot()

    def saved(self,workspace,path):
        with self.lock:
            if self.content is None and self.state['active'] and workspace is self.workspace and path==self.state['path']:
                self.pending=time.monotonic()+.55
                self.stamp=self.signature()

    @serialized_control
    def restart(self):
        with self.lock:
            if not self.state['active']:raise ValueError('Inicia una sesión Lantern primero.')
            self.generation+=1;self.pending=time.monotonic();self.state["generation"]=self.generation
        return self.snapshot()

    def watch(self,event):
        while not event.wait(.08):
            with self.lock:
                if self.content is None:
                    stamp=self.signature()
                    if stamp!=self.stamp:
                        self.stamp=stamp;self.pending=time.monotonic()+.55;self.generation+=1
                if not self.pending or time.monotonic()<self.pending:continue
                self.pending=0;old=self.job;self.job=None;generation=self.generation
                self.state.update(status='preparing',output='Validando el buffer…\n',diagnostics=[],lens=[],error='',job=None)
                workspace=self.workspace;path=self.state['path'];content=self.content
            obsolete=lambda:event.is_set() or generation!=self.generation
            try:
                self.settle(old)
                if old:
                    with self.lock:self.remember(old)
                if obsolete():continue
                if content is None:content=workspace.read(path)['content']
                # Reuse no mutable links. All compiler intermediates live in this copy.
                self.preview.stop();self.cleanup_live()
                self.live_root=Path(tempfile.mkdtemp(prefix='ll-'))
                shadow=stage(workspace,path,content,self.live_root,obsolete)
                plan=prepare(self.runtimes,shadow,path)
                if obsolete():continue
                if plan['checks']:
                    result=self.runner.start(plan['checks'],shadow.root,timeout=90,stop_on_output_limit=False)
                    check=self.runner.jobs[result['job']]
                    with self.lock:self.validation=check
                    while not check.done:
                        if obsolete():
                            check.cancel()
                            deadline=time.monotonic()+3
                            while not check.done and time.monotonic()<deadline:time.sleep(.025)
                            if not check.done:raise ValueError('La validación anterior sigue deteniéndose.')
                            raise Superseded()
                        event.wait(.03)
                    with self.lock:self.validation=None
                    if obsolete():continue
                    if check.code:
                        diagnostics=output_diagnostics(check.output,path)
                        with self.lock:
                            self.state.update(status='waiting' if self.content is not None else 'error',output=check.output,
                                diagnostics=diagnostics,error=diagnostics[0]['message'] if diagnostics else 'La compilación no terminó correctamente. Abre el monitor para ver la salida del compilador.',adapter=plan['adapter'])
                        continue
                with self.lock:
                    if obsolete():continue
                    self.revision+=1;self.shadow=shadow
                    self.state.update(revision=self.revision,status='running',updatedAt=time.time(),executedGeneration=generation,
                        generation=generation,bufferVersion=self.version,adapter=plan['adapter'],lensMode=plan['lensMode'],output='',preview=None)
                    if plan.get('preview'):
                        self.state.update(preview=self.preview.start(shadow,path),status='watching',output='Vista previa del buffer actualizada. El archivo original no se ha guardado.\n')
                    else:
                        checkpoint=self.memory_dir/'state.json';lens=self.memory_dir/'lens.json'
                        (self.memory_dir/'state.json.reload').unlink(missing_ok=True);lens.unlink(missing_ok=True)
                        commands=runtime_commands(plan,checkpoint,lens)
                        runtime_path=os.pathsep.join(dict.fromkeys(str(Path(cmd[0]).parent) for cmd in plan['checks']))
                        result=self.runner.start(commands,shadow.root,timeout=0,env={'PATH':runtime_path+os.pathsep+child_environment().get('PATH',''),'LUMEN_LANTERN_STATE':str(checkpoint),
                            'LUMEN_LANTERN_REVISION':str(self.revision),'LUMEN_LANTERN_LENS':str(lens),'LUMEN_LANTERN_GENERATION':str(generation)})
                        self.job=self.runner.jobs[result['job']]
            except Superseded:continue
            except Exception as exc:
                with self.lock:
                    if not obsolete():
                        diagnostics=[marker(exc.msg,exc.lineno,exc.offset,source='Lantern')] if isinstance(exc,SyntaxError) else []
                        self.state.update(status='waiting' if isinstance(exc,SyntaxError) and self.content is not None else 'error',error=str(exc),output=str(exc)+'\n',diagnostics=diagnostics)

    def cleanup_live(self):
        path=self.live_root
        if path and path.exists() and path.resolve().parent==Path(tempfile.gettempdir()).resolve() and path.name.startswith('ll-'):
            # Only the private directory allocated by this session is removed.
            for attempt in range(8):
                try:shutil.rmtree(path);break
                except OSError:
                    if attempt==7:raise
                    time.sleep(.1)
        self.live_root=None

    def remember(self,job):
        if not self.memory_dir:return
        entry={'revision':self.state['revision'],'path':self.state['path'],'time':time.time(),'code':job.code,'output':job.output[-8000:]}
        self.history=[h for h in self.history if h['revision']!=entry['revision']]+[entry]
        self.history=self.history[-20:];atomic_json(self.memory_dir/'history.json',self.history)

    @serialized_control
    def stop(self):
        with self.lock:
            self.event.set();thread=self.thread;job=self.job;validation=self.validation;self.state['active']=False;self.state['lens']=[]
        if validation and not validation.done:validation.cancel()
        self.settle(job)
        if thread and thread is not threading.current_thread():thread.join(timeout=6)
        with self.lock:
            if thread and thread.is_alive():raise ValueError('Lantern aún está deteniendo su proceso. Inténtalo de nuevo.')
            if job:self.state['output']=job.output;self.remember(job)
            if self.state.get('preview'):self.preview.stop();self.state['preview']=None
            self.cleanup_live()
            self.job=None;self.validation=None;self.thread=None;self.state['status']='stopped';self.pending=0
        return self.snapshot()
