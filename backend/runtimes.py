"""Language-aware build/run plans and explicit local debugger configuration."""
from __future__ import annotations
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import xml.sax.saxutils
from .preferences import atomic_json
from .toolchains import validate_argv
from .runtime_paths import find_tool

SUFFIXES={'python':('.py','.pyw'),'javascript':('.js','.mjs','.cjs'),'typescript':('.ts',),
 'asm':('.s','.asm'),'bash':('.sh','.bash'),'c':('.c',),'cpp':('.cpp','.cc','.cxx'),'rust':('.rs',),'go':('.go',),'java':('.java',),
 'csharp':('.cs',),'html':('.html','.htm','.htmll'),'css':('.css',),'nc':('.n','.nc','.nm','.ncp','.nb','.nbb')}
TOOLS={'asm':('gcc','clang'),'bash':('bash',),'python':(),'javascript':('node',),'typescript':('node',),'c':('gcc','clang'),'cpp':('g++','clang++'),
 'rust':('rustc',),'go':('go',),'java':('javac','java'),'csharp':('dotnet',),'html':(),'css':(),'nc':('ncc',)}
LABELS={'asm':'ASM · ensamblador','bash':'Bash','python':'Python','javascript':'JavaScript','typescript':'TypeScript','c':'C','cpp':'C++','rust':'Rust','go':'Go','java':'Java','csharp':'C#','html':'HTML','css':'CSS','nc':'nC'}

def language(path):
    return next((name for name,suffixes in SUFFIXES.items() if Path(path).suffix.lower() in suffixes),None)

class Runtimes:
    def __init__(self,prefs):
        self.path=prefs.directory/'languages.json';self.config={'languages':{},'tools':{}}
        defaults=Path(__file__).resolve().parents[1]/'config/runtime-defaults.json'
        if defaults.is_file():
            try:self.config=self.validate(json.loads(defaults.read_text(encoding='utf-8')))
            except (ValueError,TypeError,OSError):pass
        local=defaults.with_name('runtime-local.json')
        if local.is_file() and not getattr(sys,'frozen',False):
            try:self.config=self.validate(json.loads(local.read_text(encoding='utf-8')))
            except (ValueError,TypeError,OSError):pass
        if self.path.is_file():
            try:self.config=self.validate(json.loads(self.path.read_text(encoding='utf-8')))
            except (ValueError,TypeError,OSError):pass
    def validate(self,data):
        if not isinstance(data,dict) or not isinstance(data.get('languages'),dict):raise ValueError('Usa un objeto languages.')
        out={'languages':{},'tools':{}}
        for name,path in data.get('tools',{}).items():
            if name not in ('python','bash','ncc','node','nasm','clang','clang++','gcc','g++','rustc','go','javac','java','dotnet','lldb-dap','lldb-vscode','dlv','netcoredbg'):raise ValueError('Herramienta desconocida: '+str(name))
            if not isinstance(path,str) or not path or len(path)>4096 or '\x00' in path:raise ValueError('Ruta no válida.')
            out['tools'][name]=path
        for name,profile in data['languages'].items():
            if name not in SUFFIXES or not isinstance(profile,dict):raise ValueError('Lenguaje o perfil no válido.')
            item={}
            if 'standard' in profile:
                from .foundation import C_STANDARDS, CPP_STANDARDS
                choices=C_STANDARDS if name=='c' else CPP_STANDARDS if name=='cpp' else ()
                if profile['standard'] not in choices:raise ValueError('Estándar no válido para '+name)
                item['standard']=profile['standard']
            for key in ('run','build','check'):
                if key in profile:item[key]=validate_argv(profile[key])
            if 'debug' in profile:
                debug=profile['debug']
                if not isinstance(debug,dict):raise ValueError('Configuración debug no válida.')
                adapter=validate_argv(debug.get('adapter'));launch=debug.get('launch',{})
                if not isinstance(launch,dict) or len(json.dumps(launch))>32000:raise ValueError('Argumentos DAP no válidos.')
                transport=debug.get('transport','stdio')
                if transport not in ('stdio','tcp'):raise ValueError('DAP usa stdio o tcp local.')
                item['debug']={'adapter':adapter,'launch':copy.deepcopy(launch),'transport':transport}
            out['languages'][name]=item
        return out
    def save(self,data):
        result=self.validate(data);atomic_json(self.path,result);self.config=result;return copy.deepcopy(result)
    def expand(self,value,ws,file,target,port=0):
        substitutions={'${workspaceFolder}':str(ws.root),'${file}':str(file),'${fileDirname}':str(file.parent),
            '${fileBasenameNoExtension}':file.stem,'${target}':str(target),'${port}':str(port)}
        if isinstance(value,str):
            for key,item in substitutions.items():value=value.replace(key,item)
            return value
        if isinstance(value,list):return [self.expand(x,ws,file,target,port) for x in value]
        if isinstance(value,dict):return {k:self.expand(v,ws,file,target,port) for k,v in value.items()}
        return value
    def executable(self,*names):
        for name in names:
            if found:=find_tool(name,self.config.get('tools')):return found
        raise ValueError('Falta '+ ' / '.join(names)+'. Instala su SDK o configura la ruta en Lenguajes y depuradores.')
    def plan(self,ws,path,check=False,debug=False):
        if not ws.trusted:raise PermissionError('Autoriza el proyecto antes de ejecutar código.')
        file=ws.resolve(path);lang=language(path)
        if lang not in SUFFIXES:raise ValueError('Configura una tarea para este tipo de archivo.')
        folder=ws.private_dir('run')/(file.stem+'-'+hashlib.sha256(path.encode()).hexdigest()[:8]);folder.mkdir(exist_ok=True)
        target=folder/(file.stem+('.exe' if os.name=='nt' else ''))
        custom=self.config['languages'].get(lang,{})
        if custom.get('run') or custom.get('build'):
            commands=[]
            if check and custom.get('check'):commands=[custom['check']]
            else:
                if custom.get('build'):commands.append(custom['build'])
                if not check and not debug:commands.append(custom.get('run',[str(target)]))
            return {'language':lang,'commands':self.expand(commands,ws,file,target),'target':target,'file':file,'cwd':ws.root}
        commands=[]
        if lang=='python':
            if check:compile(file.read_bytes(),str(file),'exec')
            elif not debug:
                from .foundation import python_command
                commands=[[*python_command(),str(file)]]
        elif lang=='bash':
            commands=[[self.executable('bash'),*(['-n'] if check else []),str(file)]]
        elif lang in ('javascript','typescript'):
            node=self.executable('node');commands=[] if debug else [[node,*(['--check'] if check else []),str(file)]]
        elif lang in ('html','css'):
            if check and lang=='html':
                from html.parser import HTMLParser
                HTMLParser().feed(file.read_text(encoding='utf-8-sig'))
            return {'language':lang,'commands':[],'target':file,'file':file,'cwd':ws.root,'preview':not check}
        elif lang=='asm':
            compiler=self.executable('gcc','clang')
            if file.suffix.lower()=='.asm':
                nasm=self.executable('nasm');obj=folder/(file.stem+'.obj')
                commands=[[nasm,'-f','win64' if os.name=='nt' else 'elf64',str(file),'-o',str(obj)],[compiler,str(obj),'-o',str(target)]]
            else:commands=[[compiler,*(['-g'] if debug else []),str(file),'-o',str(target)]]
            if not check and not debug:commands.append([str(target)])
        elif lang in ('c','cpp'):
            compiler=self.executable(*TOOLS[lang]);standard='-std='+custom.get('standard','c++17' if lang=='cpp' else 'c11')
            commands=[[compiler,standard,'-Wall','-Wextra','-I',str(Path(__file__).resolve().parents[1]/'debugger-support/lantern'),*(['-g','-O0'] if debug else []),*(['-fsyntax-only'] if check else []),str(file),*([] if check else ['-o',str(target)])]]
            if not check and not debug:commands.append([str(target)])
        elif lang=='rust':
            compiler=self.executable('rustc');commands=[[compiler,'--edition=2021',*(['-g','-C','opt-level=0'] if debug else []),*(['--emit=metadata'] if check else []),str(file),'-o',str(target)]]
            if not check and not debug:commands.append([str(target)])
        elif lang=='go':
            go=self.executable('go');commands=[[go,'build',*(['-gcflags=all=-N -l'] if debug else []),'-o',str(target),str(file)]]
            if not check and not debug:commands.append([str(target)])
        elif lang=='java':
            javac=self.executable('javac');java=self.executable('java');commands=[[javac,'-J-Dfile.encoding=UTF-8','-J-Dstdout.encoding=UTF-8','-J-Dstderr.encoding=UTF-8','-g','-encoding','UTF-8','-d',str(folder),str(file)]]
            package=re.search(r'^\s*package\s+([\w.]+)\s*;',file.read_text(encoding='utf-8-sig'),re.M);main=(package.group(1)+'.' if package else '')+file.stem
            target=folder
            if not check and not debug:commands.append([java,'-Dfile.encoding=UTF-8','-Dstdin.encoding=UTF-8','-Dstdout.encoding=UTF-8','-Dstderr.encoding=UTF-8','-cp',str(folder),main])
        elif lang=='csharp':
            if re.search(r'\b(using\s+UnityEngine|MonoBehaviour)\b',file.read_text(encoding='utf-8-sig')):raise ValueError('Este componente pertenece a Unity. Abre el proyecto en Unity o configura una tarea y su adaptador DAP de Unity.')
            dotnet=self.executable('dotnet');projects=[]
            for parent in [file.parent,*file.parents]:
                if not parent.is_relative_to(ws.root):break
                projects=list(parent.glob('*.csproj'))
                if projects:break
            if len(projects)>1:raise ValueError('Hay varios proyectos .NET. Configura el proyecto de inicio en Lenguajes y depuradores.')
            if projects:project=projects[0]
            else:
                import subprocess
                result=subprocess.run([dotnet,'--version'],capture_output=True,text=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                match=re.match(r'(\d+)\.',result.stdout.strip())
                if not match:raise ValueError('El SDK .NET no está preparado: '+result.stderr[:500])
                project=folder/'LumenScript.csproj';escaped=xml.sax.saxutils.escape(str(file),{'"':'&quot;'})
                project.write_text(f'<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net{match.group(1)}.0</TargetFramework><EnableDefaultCompileItems>false</EnableDefaultCompileItems><ImplicitUsings>enable</ImplicitUsings><DebugType>portable</DebugType></PropertyGroup><ItemGroup><Compile Include="{escaped}" /></ItemGroup></Project>',encoding='utf-8')
            out=folder/'bin';target=out/(project.stem+'.dll')
            commands=[[dotnet,'build',str(project),'-c','Debug','-o',str(out),'--nologo']]
            if not check and not debug:commands.append([dotnet,str(target)])
        elif lang=='nc':
            ncc=self.executable('ncc')
            if check:commands=[[ncc,'check',str(file)]]
            elif debug and file.suffix.lower() in ('.n','.nc'):
                commands=[[ncc,'compiler','build-native',str(file),'--profile','debug','--out-dir',str(folder),'--out',str(target),'--no-run','--strict']]
            elif not debug:commands=[[ncc,'run',str(file)]]
        return {'language':lang,'commands':commands,'target':target,'file':file,'cwd':ws.root}
    def status(self):
        result=[]
        for name in SUFFIXES:
            custom=self.config['languages'].get(name,{})
            available=not TOOLS[name] or any(find_tool(x,self.config.get('tools')) for x in TOOLS[name]) or bool(custom.get('run') or custom.get('build'))
            adapter='Integrado' if name in ('python','javascript','typescript') else 'Navegador' if name in ('html','css') else 'DAP configurado' if custom.get('debug') else 'Delve' if name=='go' else 'NetCoreDbg' if name=='csharp' else 'LLDB DAP' if name in ('c','cpp','rust') else 'JDI integrado' if name=='java' else 'ncc / LLDB DAP' if name=='nc' else 'Configurar DAP'
            result.append({'id':name,'name':LABELS[name],'extensions':SUFFIXES[name],'available':available,'tools':TOOLS[name],'debugger':adapter})
        return {'languages':result,'config':copy.deepcopy(self.config)}
