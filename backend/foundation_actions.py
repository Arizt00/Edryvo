"""Explicit development actions hosted by the existing task runner and PTY."""
from pathlib import Path
import os
from .foundation import tool_environment
from .runtime_paths import find_tool

def action(features,ws,body):
    if not ws.trusted:raise PermissionError('Autoriza el proyecto antes de ejecutar herramientas.')
    operation=body.get('action')
    if operation=='venv':
        executable=find_tool('python',features.runtimes.config.get('tools'))
        if not executable:
            if getattr(__import__('sys'),'frozen',False):raise ValueError('Prepara un runtime Python independiente para crear entornos del proyecto.')
            executable=__import__('sys').executable
        folder=ws.resolve('.venv',must_exist=False)
        if folder.exists():raise ValueError('Ya existe .venv; se conserva. Usa su terminal o el gestor de paquetes.')
        return features.app.runner.start([[executable,'-m','venv',str(folder)]],ws.root,timeout=120,env=tool_environment())
    if operation=='pip':
        folder=ws.resolve('.venv',must_exist=True);python=folder/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        if not python.is_file():raise ValueError('Crea primero el entorno .venv del proyecto.')
        requirements=ws.resolve('requirements.txt')
        return features.hacker._terminal([str(python),'-m','pip','install','-r',str(requirements)],'Python · dependencias del proyecto',ws.root)
    commands={'docker-info':['docker','version'],'docker-ps':['docker','ps','--all'],
              'docker-compose':['docker','compose','version'],'bash':['bash','--login','-i'],
              'java':['java','--version'],'maven':['mvn','--version'],'gradle':['gradle','--version']}
    if operation not in commands:raise ValueError('Acción de desarrollo desconocida.')
    name,*args=commands[operation];exe=find_tool(name)
    if not exe:raise ValueError('Falta '+name+' en la base de Zénit o en el sistema.')
    argv=[exe,*args]
    if os.name=='nt' and Path(exe).suffix.lower() in ('.cmd','.bat'):
        # Only fixed actions above are accepted; no command string from the UI.
        import subprocess
        argv=[find_tool('cmd.exe'),'/d','/s','/c',subprocess.list2cmdline([exe,*args])]
    return features.hacker._terminal(argv,name+' · Zénit',ws.root)
