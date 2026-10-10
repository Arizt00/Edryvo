"""Detected tools, explicit argv tasks and reviewable package-manager plans."""
from __future__ import annotations
import json
import os
import platform
import re
import secrets
import shlex
import shutil
import subprocess
import threading
import time
from pathlib import Path
from .preferences import atomic_json
from .terminals import child_environment

TOOLS=[('python','Python',('python3','python')),('node','JavaScript / Node.js',('node',)),
 ('gcc','C / GCC',('gcc',)),('g++','C++ / GCC',('g++',)),('clang','C / Clang',('clang',)),('clang++','C++ / Clang',('clang++',)),
 ('rustc','Rust',('rustc',)),('cargo','Cargo',('cargo',)),('go','Go',('go',)),('javac','Java compiler',('javac',)),('java','Java runtime',('java',)),
 ('dotnet','C# / F# / .NET',('dotnet',)),('cmake','CMake',('cmake',)),('ninja','Ninja',('ninja',)),('make','Make',('make',)),
 ('nasm','ASM / NASM',('nasm',)),('as','GNU Assembler',('as',)),('ruby','Ruby',('ruby',)),('php','PHP',('php',)),
 ('perl','Perl',('perl',)),('lua','Lua',('lua','lua5.4')),('swift','Swift',('swift',)),('zig','Zig',('zig',)),
 ('julia','Julia',('julia',)),('R','R',('R',)),('fpc','Pascal',('fpc',)),('ncc','nC / NCC',('ncc',)),
 ('git','Git',('git',)),('clangd','C / C++ Language Server',('clangd',)),('pylsp','Python Language Server',('pylsp',)),
 ('bash','Bash',('bash',)),('docker','Docker CLI',('docker',)),('qemu','QEMU · máquinas virtuales',('qemu-system-x86_64',)),('maven','Maven',('mvn',)),('gradle','Gradle',('gradle',)),
 ('rust-analyzer','Rust Language Server',('rust-analyzer',)),('gopls','Go Language Server',('gopls',))]
PACKAGES={
 'cmake':{'winget':'Kitware.CMake','brew':'cmake','apt':'cmake','dnf':'cmake','pacman':'cmake'},
 'llvm':{'winget':'LLVM.LLVM','brew':'llvm','apt':'clang','dnf':'clang','pacman':'clang'},
 'gcc':{'brew':'gcc','apt':'build-essential','dnf':'gcc-c++','pacman':'base-devel'},
 'ninja':{'winget':'Ninja-build.Ninja','brew':'ninja','apt':'ninja-build','dnf':'ninja-build','pacman':'ninja'},
 'git':{'winget':'Git.Git','brew':'git','apt':'git','dnf':'git','pacman':'git'},
 'node':{'winget':'OpenJS.NodeJS.LTS','brew':'node','apt':'nodejs','dnf':'nodejs','pacman':'nodejs'},
 'python':{'brew':'python','apt':'python3','dnf':'python3','pacman':'python'},
 'go':{'winget':'GoLang.Go','brew':'go','apt':'golang','dnf':'golang','pacman':'go'},
 'rust':{'winget':'Rustlang.Rustup','brew':'rustup','apt':'rustc','dnf':'rust','pacman':'rust'},
 'nasm':{'brew':'nasm','apt':'nasm','dnf':'nasm','pacman':'nasm'},
}


def validate_argv(argv):
    if not isinstance(argv,list) or not 1<=len(argv)<=80 or any(not isinstance(s,str) or '\0' in s or len(s)>4000 for s in argv) or not argv[0].strip():
        raise ValueError('Usa una lista JSON de argumentos, con el ejecutable como primer elemento.')
    return list(argv)


def resolve_argv(argv,ws,active=''):
    argv=validate_argv(argv)
    current=ws.resolve(active) if active else None
    mapping={'${workspaceFolder}':str(ws.root),'${file}':str(current or ''),'${fileDirname}':str(current.parent if current else ws.root),
             '${fileBasename}':current.name if current else '', '${fileBasenameNoExtension}':current.stem if current else ''}
    resolved=[]
    for value in argv:
        for key,replacement in mapping.items():value=value.replace(key,replacement)
        resolved.append(value)
    return resolved


class Toolchains:
    def __init__(self,prefs,runner):
        self.prefs=prefs;self.runner=runner;self.path=prefs.directory/'development.json';self.lock=threading.RLock();self.cache=None;self.cache_time=0
        self.config={'tasks':[], 'servers':[], 'associations':{}}
        if self.path.is_file():
            try:self.config=self.validate(json.loads(self.path.read_text(encoding='utf-8')))
            except (ValueError,OSError,TypeError):pass
    def validate(self,data):
        if not isinstance(data,dict):raise ValueError('Configuración de desarrollo no válida.')
        out={'tasks':[],'servers':[],'associations':{}}
        for kind in ('tasks','servers'):
            items=data.get(kind,[])
            if not isinstance(items,list) or len(items)>80:raise ValueError('Demasiadas tareas o servidores.')
            seen=set()
            for obj in items:
                if not isinstance(obj,dict):raise ValueError('Entrada no válida.')
                ident=obj.get('id','')
                if not isinstance(ident,str) or not re.fullmatch(r'[\w.-]{1,80}',ident) or ident in seen:raise ValueError('ID no válido o duplicado.')
                seen.add(ident)
                item={'id':ident,'label':str(obj.get('label',ident))[:150],'argv':validate_argv(obj.get('argv'))}
                if kind=='servers':
                    langs=obj.get('languages',[])
                    if not isinstance(langs,list) or not langs or len(langs)>80 or any(not isinstance(s,str) or not re.fullmatch(r'[\w+.-]{1,80}',s) for s in langs):raise ValueError('Lenguajes de LSP no válidos.')
                    item['languages']=langs
                out[kind].append(item)
        assoc=data.get('associations',{})
        if not isinstance(assoc,dict) or len(assoc)>300:raise ValueError('Asociaciones no válidas.')
        for suffix,language in assoc.items():
            if not re.fullmatch(r'\.[\w.+-]{1,30}',suffix) or not isinstance(language,str) or not re.fullmatch(r'[\w+.-]{1,80}',language):raise ValueError('Asociación no válida.')
            out['associations'][suffix]=language
        return out
    def save(self,data):
        candidate=self.validate(data)
        with self.lock:atomic_json(self.path,candidate);self.config=candidate;self.cache=None
        self.prefs.audit('development.configure')
        return candidate
    def discover_servers(self):
        from .runtime_paths import find_tool
        candidates=[('clangd',['c','cpp'],['--background-index']),('pylsp',['python'],[]),('pyright-langserver',['python'],['--stdio']),('rust-analyzer',['rust'],[]),('gopls',['go'],[]),('jdtls',['java'],[]),('csharp-ls',['csharp'],[]),('ncc-lsp',['nc'],[]),('asm-lsp',['asm'],[])]
        covered={lang for profile in self.config['servers'] for lang in profile['languages']}
        for name,languages,args in candidates:
            if all(lang in covered for lang in languages):continue
            executable=find_tool(name)
            if not executable:continue
            if Path(executable).suffix.lower() in ('.cmd','.bat'):continue
            self.config['servers'].append({'id':'detected-'+name,'label':name+' · detectado','argv':[executable,*args],'languages':languages})
            covered.update(languages)
        return self.config

    def detect(self,refresh=False):
        with self.lock:
            if self.cache and not refresh and time.monotonic()-self.cache_time<30:return self.cache
            self.discover_servers()
            result=[]
            for ident,label,names in TOOLS:
                from .runtime_paths import find_tool
                executable=next((str(Path(p).resolve()) for n in names if (p:=find_tool(n))),None)
                # Discovery does not execute an arbitrary compiler just to render a card.
                result.append({'id':ident,'label':label,'path':executable,'available':bool(executable)})
            managers=[m for m in ('winget','brew','apt','dnf','pacman') if shutil.which(m)]
            self.cache={'tools':result,'managers':managers,'packages':PACKAGES,'platform':platform.system(),'config':self.config};self.cache_time=time.monotonic()
            return self.cache
    def run(self,ws,task_id,active='',consent=False):
        if not ws.trusted or consent is not True:raise PermissionError('Autoriza la ejecución de esta tarea en un proyecto de confianza.')
        task=next((x for x in self.config['tasks'] if x['id']==task_id),None)
        if not task:raise FileNotFoundError('Tarea no configurada.')
        argv=resolve_argv(task['argv'],ws,active)
        self.prefs.audit('task.run',id=task_id)
        return self.runner.start([argv],ws.root)
    def plan(self,package,manager):
        if manager not in PACKAGES.get(package,{}):raise ValueError('Combinación de paquete y gestor no disponible.')
        if not shutil.which(manager):raise ValueError('Ese gestor no está instalado en este sistema.')
        name=PACKAGES[package][manager]
        argv={'winget':['winget','install','--id',name,'--exact','--source','winget'],
              'brew':['brew','install',name], 'apt':['sudo','apt','install',name],
              'dnf':['sudo','dnf','install',name], 'pacman':['sudo','pacman','-S',name]}[manager]
        # This is a reviewed plan, not background elevation. The user runs it in
        # an interactive terminal so package/licence/admin prompts remain visible.
        cmd=subprocess.list2cmdline(argv) if os.name=='nt' else shlex.join(argv)
        return {'argv':argv,'command':cmd,'package':package,'manager':manager,'requiresReview':True,
                'note':'La instalación depende del catálogo del gestor y puede pedir permisos. Revisa el comando; Zénit no eleva permisos en segundo plano.'}
