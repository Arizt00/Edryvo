"""One debugger lifecycle across Python, Node and configured DAP adapters."""
from __future__ import annotations
import copy
import os
import re
import shutil
import socket
import threading
import time
from .debugger import PythonDebugger
from .debug_adapters import NodeDebugger,ProtocolDebugger
from .runtimes import language

class DebugManager:
    def __init__(self,runtimes,runner):
        self.runtimes=runtimes;self.runner=runner;self.current=PythonDebugger();self.build=None;self.cancelled=False
        self.starting=None;self.generation=0;self.lock=threading.RLock()
    @property
    def process(self):return self.current.process
    def snapshot(self):
        state=copy.deepcopy(self.starting) if self.starting else self.current.snapshot()
        state['preparing']=bool(self.starting and self.starting.get('status')=='running')
        state['inputSupported']=(isinstance(self.current,(PythonDebugger,NodeDebugger)) or getattr(self.current,'debuggee',None) is not None or getattr(self.current,'input_pipe',None) is not None) and not state['preparing']
        state['stepOutSupported']=not state['preparing'] and type(self.current).__name__!='JavaDebugger'
        return state
    def input(self,text):
        if not isinstance(text,str) or len(text)>65536:raise ValueError('Entrada no válida.')
        if isinstance(self.current,PythonDebugger):return self.current.input(text)
        if isinstance(self.current,NodeDebugger) and self.current.process and self.current.process.poll() is None:
            self.current.process.stdin.write(text.encode('utf-8'));self.current.process.stdin.flush();return {'ok':True}
        if getattr(self.current,'debuggee',None) is not None or getattr(self.current,'input_pipe',None) is not None:return self.current.input(text)
        raise ValueError('Este adaptador no expone entrada estándar. Usa Ejecutar o Lantern para entrada interactiva.')
    def start(self,ws,path,points):
        if not ws.trusted:raise PermissionError('Autoriza el proyecto antes de depurar.')
        ws.read(path)
        if not isinstance(points,list) or len(points)>200 or any(type(n) is not int or n<1 for n in points):raise ValueError('Puntos de interrupción no válidos.')
        with self.lock:
            if self.snapshot()['status'] in ('running','paused'):raise ValueError('Detén la sesión de depuración actual.')
            self.current.stop()
            lang=language(path)
            if lang=='python':self.current=PythonDebugger();return self.current.start(ws,path,points)
            self.generation+=1;generation=self.generation;self.cancelled=False
            self.build=None
            self.starting={'status':'running','path':path,'variables':[],'stack':[],'output':'Preparando '+str(lang)+'…\n'}
        threading.Thread(target=self.prepare,args=(ws,path,points,generation),daemon=True).start();return self.snapshot()
    def prepare(self,ws,path,points,generation):
        try:
            plan=self.runtimes.plan(ws,path,debug=True);lang=plan['language'];file=plan['file'];target=plan['target']
            custom=self.runtimes.config['languages'].get(lang,{}).get('debug');port=0
            if lang not in ('javascript','typescript','java') or custom:
                if custom:adapter=custom['adapter'];launch=custom['launch'];transport=custom.get('transport','stdio')
                elif lang in ('c','cpp','rust','asm') or lang=='nc' and file.suffix.lower() in ('.n','.nc'):
                    adapter=[self.runtimes.executable('lldb-dap','lldb-vscode')];transport='stdio';launch={'program':str(target),'cwd':str(ws.root),'stopOnEntry':False,'console':'internalConsole','_lumenEntry':True}
                elif lang=='csharp':
                    adapter=[self.runtimes.executable('netcoredbg'),'--interpreter=vscode'];transport='stdio';launch={'program':str(target),'cwd':str(ws.root),'stopAtEntry':True,'console':'integratedTerminal'}
                elif lang=='go':
                    adapter=[self.runtimes.executable('dlv'),'dap','--listen=127.0.0.1:${port}'];transport='tcp';launch={'program':str(target),'mode':'exec','cwd':str(ws.root),'stopOnEntry':False,'_lumenEntryFunction':'main.main'}
                elif lang=='nc':
                    adapter=[self.runtimes.executable('ncc'),'debug-adapter'];transport='stdio';launch={'program':str(file),'cwd':str(ws.root),'stopOnEntry':True,'lane':{'.nm':'machine','.nb':'basal','.ncp':'primitive','.nbb':'primitive'}.get(file.suffix.lower(),'source')}
                else:raise ValueError('Configura el adaptador DAP de '+str(lang)+' en Lenguajes y depuradores. HTML/CSS se inspeccionan en Vista previa.')
                if transport=='tcp':
                    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
                adapter=self.runtimes.expand(adapter,ws,file,target,port);launch=self.runtimes.expand(launch,ws,file,target,port)
            if plan['commands']:
                job_id=self.runner.start(plan['commands'],ws.root)['job'];self.build=self.runner.jobs[job_id]
                while not self.build.done:
                    if generation!=self.generation:self.build.cancel();return
                    if self.starting:self.starting['output']=self.build.output
                    time.sleep(.05)
                if self.build.code:raise ValueError('La compilación no terminó correctamente.\n'+self.build.output[-7000:])
            if generation!=self.generation:return
            if lang=='nc' and not custom and file.suffix.lower() in ('.n','.nc'):
                # Read the compiler's emitted debug metadata, never guess nC syntax.
                for ir in list((target.parent/'lowering').glob('*.ll'))[:20]:
                    metadata=ir.read_text(encoding='utf-8',errors='replace')
                    match=re.search(r'DISubprogram\(name: "[^"]*\.main", linkageName: "([^"]+)"',metadata)
                    if match:
                        launch.pop('_lumenEntry',None);launch['_lumenEntryFunction']=match.group(1);break
            from .java_debugger import JavaDebugger
            self.current=JavaDebugger() if lang=='java' and not custom else NodeDebugger() if lang in ('javascript','typescript') else ProtocolDebugger()
            if self.build:self.current.output(self.build.output)
            self.starting=None
            if isinstance(self.current,NodeDebugger):self.current.start_node(ws,path,points,self.runtimes.executable('node'))
            elif isinstance(self.current,JavaDebugger):self.current.start_java(ws,path,points,self.runtimes.executable('java'),target)
            else:self.current.start(ws,path,points,adapter,launch,transport,port)
        except Exception as exc:
            if generation==self.generation:
                if self.starting:self.starting.update(status='error',error=str(exc))
                else:
                    self.current.stop();self.current.update(status='error',error=str(exc))
    def command(self,command):
        if command=='stop':self.stop();return self.snapshot()
        if self.starting:raise ValueError('Espera a que el depurador esté preparado.')
        return self.current.command(command)
    def stop(self):
        self.generation+=1
        if self.build and not self.build.done:self.build.cancel()
        self.current.stop();self.starting=None
