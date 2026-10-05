"""Python buffers and GCC/GDB workflows, using Zénit's real integrated PTY."""
import os
from pathlib import Path
import sys
import tempfile
from .runtime_paths import find_tool
from .terminals import TerminalSession


class Hacker:
    def __init__(self, features):
        self.features=features;self.builds={};self.folders=[]

    def tools(self):
        return {'python':self._python_executable(),**{name:find_tool(name) for name in ('gcc','gdb')}}

    def _python_executable(self):
        executable=sys.executable
        if getattr(sys,'frozen',False):
            # ConPTY hosts the console helper inside Zénit; no external CMD.
            helper=Path(executable).with_name('zenit-python.exe' if os.name=='nt' else 'zenit-python')
            if helper.is_file():return str(helper)
        return executable

    def _terminal(self, argv, label, cwd, environment=None):
        manager=self.features.terminals
        if not self.features.prefs.get('security.terminals'):raise PermissionError('Activa las terminales en Ajustes.')
        with manager.lock:
            if sum(not s.closed for s in manager.sessions.values())>=6:raise ValueError('Cierra una terminal antes de abrir otra.')
            profile={'id':'hacker','label':label,'argv':argv,'kind':'hacker'}
            # GCC/GDB depend on companion DLLs next to their executables on Windows.
            env=dict(environment or {});env['PATH']=str(Path(argv[0]).parent)+os.pathsep+os.environ.get('PATH','')
            s=TerminalSession(profile,cwd,manager.project,100,26,environment=env)
            manager.sessions[s.id]=s
            return {'id':s.id,'profile':profile,'kind':s.kind}

    def start(self, ws, path, content, mode):
        if not ws.trusted:raise PermissionError('Autoriza el proyecto para ejecutar su código.')
        file=ws.resolve(path)
        if not isinstance(content,str) or len(content)>2_000_000:raise ValueError('El búfer admite hasta 2 MB.')
        folder=Path(tempfile.mkdtemp(prefix='lumen-hacker-'));self.folders.append(folder)
        source=folder/file.name;source.write_text(content,encoding='utf-8',newline='')
        if mode=='python':
            if file.suffix.lower() not in ('.py','.pyw'):raise ValueError('Abre un archivo Python para esta acción.')
            frozen=getattr(sys,'frozen',False)
            executable=self._python_executable()
            argv=[executable,*(['--python-child'] if frozen else ['-u']),str(source)]
            return {'terminal':self._terminal(argv,'Python · '+file.name,ws.root,{'PYTHONPATH':str(file.parent),'LUMEN_SCRIPT_IMPORT_ROOT':str(file.parent)})}
        if mode!='gdb' or file.suffix.lower()!='.c':raise ValueError('GCC + GDB requiere un archivo .c.')
        tools=self.tools()
        if not tools['gcc'] or not tools['gdb']:raise FileNotFoundError('Instala GCC y GDB (MinGW/MSYS2 en Windows) y añade su carpeta bin al PATH. Zénit detecta también C:/msys64/ucrt64/bin.')
        target=folder/('program.exe' if os.name=='nt' else 'program')
        argv=[tools['gcc'],'-g3','-O0','-Wall','-Wextra','-fno-omit-frame-pointer','-iquote',str(file.parent),str(source),'-o',str(target)]
        result=self.features.app.runner.start([argv],ws.root,timeout=120)
        self.builds[result['job']]={'target':target,'gdb':tools['gdb'],'workspace':ws.root,'source':source,'name':file.name}
        return {**result,'flags':argv[1:6]}

    def attach(self, ws, key):
        if not ws.trusted:raise PermissionError('Autoriza el proyecto.')
        build=self.builds.get(key);job=self.features.app.runner.jobs.get(key)
        if not build or build['workspace']!=ws.root or not job:raise ValueError('Compilación no encontrada en este proyecto.')
        if not job.done:raise ValueError('La compilación sigue en curso.')
        if job.code!=0 or not build['target'].is_file():raise ValueError('GCC no pudo compilar. Revisa sus errores en la salida de tareas.')
        result=self._terminal([build['gdb'],'--quiet','-ex','set pagination off','-ex','start','--args',str(build['target'])],'GDB · '+build['name'],ws.root)
        del self.builds[key]
        return result

    def shutdown(self):
        import shutil
        for folder in self.folders:
            target=folder.resolve()
            if target.parent==Path(tempfile.gettempdir()).resolve() and target.name.startswith('lumen-hacker-'):shutil.rmtree(target,ignore_errors=True)
        self.folders.clear();self.builds.clear()
