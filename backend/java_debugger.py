"""JDK 17+ JDI worker, using the same event contract as the Python debugger."""
from pathlib import Path
import os
import re
import subprocess
import threading
from .debugger import PythonDebugger
from .terminals import child_environment

class JavaDebugger(PythonDebugger):
    def output(self,text):
        with self.lock:self.state['output']=(self.state['output']+text)[-100000:]
    def update(self,**changes):
        with self.lock:self.state.update(changes)
    def start_java(self,ws,path,points,java,classes):
        file=ws.resolve(path);package=re.search(r'^\s*package\s+([\w.]+)\s*;',file.read_text(encoding='utf-8-sig'),re.M)
        main=(package.group(1)+'.' if package else '')+file.stem
        worker=Path(__file__).with_name('LumenJavaDebugger.java')
        self.update(status='running',path=path,engine='JDK JDI')
        self.process=subprocess.Popen([java,'--add-modules=jdk.jdi','-Dfile.encoding=UTF-8','-Dstdout.encoding=UTF-8','-Dstderr.encoding=UTF-8',str(worker),str(classes),main,path,','.join(map(str,points))],cwd=ws.root,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace',bufsize=1,env=child_environment(),creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        threading.Thread(target=self._read,args=(self.process,),daemon=True).start();threading.Thread(target=self._errors,args=(self.process,),daemon=True).start()
        return self.snapshot()
    def stop(self):
        process=self.process
        if process and process.poll() is None:
            try:process.stdin.write('stop\n');process.stdin.flush();process.wait(timeout=3)
            except (OSError,subprocess.TimeoutExpired):pass
        super().stop()
        self.update(status='stopped')
