"""Interactive local terminals: POSIX PTY or optional Windows ConPTY (pywinpty).

A terminal is not a sandbox. Only explicitly trusted workspaces may start one.
"""
from __future__ import annotations
import codecs
import importlib.util
import os
import platform
import re
import select
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

SECRET_NAMES={'OPENAI_API_KEY','ANTHROPIC_API_KEY','GEMINI_API_KEY','GOOGLE_API_KEY','GITHUB_TOKEN','GH_TOKEN','COPILOT_GITHUB_TOKEN'}


def child_environment():
    env={k:v for k,v in os.environ.items() if k.upper() not in SECRET_NAMES and not k.upper().startswith('LUMEN_SECRET_')}
    env.update({'TERM':'xterm-256color','COLORTERM':'truecolor','LUMEN_TERMINAL':'1','PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'})
    return env


def terminal_profiles():
    result=[]
    def add(ident,label,command,args=(),kind='local'):
        exe=shutil.which(command)
        if exe: result.append({'id':ident,'label':label,'argv':[exe,*args],'kind':kind,'available':True})
    if os.name=='nt':
        add('powershell7','PowerShell 7','pwsh',['-NoLogo'])
        add('powershell','Windows PowerShell','powershell.exe',['-NoLogo'])
        add('cmd','Símbolo del sistema · CMD','cmd.exe')
        wsl=shutil.which('wsl.exe')
        if wsl:
            try:
                raw=subprocess.run([wsl,'--list','--quiet'],capture_output=True,timeout=4,creationflags=subprocess.CREATE_NO_WINDOW).stdout
                text=raw.decode('utf-16-le' if b'\x00' in raw else 'utf-8',errors='replace')
                for distro in text.splitlines():
                    distro=distro.strip().strip('\ufeff')
                    if distro and re.fullmatch(r'[\w. -]{1,100}',distro):
                        result.append({'id':'wsl:'+distro,'label':'WSL · '+distro,'argv':[wsl,'--distribution',distro],'kind':'wsl','available':True})
            except (OSError,subprocess.SubprocessError): pass
        for root in (os.environ.get('ProgramFiles','C:/Program Files'),os.environ.get('LOCALAPPDATA','')):
            bash=Path(root)/'Git/bin/bash.exe'
            if bash.is_file():result.append({'id':'git-bash','label':'Git Bash','argv':[str(bash),'--login','-i'],'kind':'local','available':True});break
    else:
        add('bash','Bash','bash',['--noprofile','--norc','-i'])
        add('zsh','Zsh','zsh',['-i'])
        add('fish','Fish','fish',['-i'])
        add('sh','Shell POSIX','sh',['-i'])
        add('powershell7','PowerShell 7','pwsh',['-NoLogo'])
    return result


class TerminalSession:
    def __init__(self,profile,cwd,project,cols=100,rows=26,environment=None):
        self.id=uuid.uuid4().hex;self.profile=profile;self.cwd=str(cwd);self.lock=threading.RLock()
        self.output='';self.start=0;self.closed=False;self.code=None;self.fd=None;self.process=None;self.win=None;self.created=time.time()
        env=child_environment();env.update(environment or {});self.decoder=codecs.getincrementaldecoder('utf-8')('replace')
        argv=list(profile['argv'])
        if os.name=='nt':
            try: from winpty import PtyProcess
            except ImportError as e: raise ValueError('ConPTY requiere pywinpty. Instala los requisitos de escritorio; no se inicia una falsa terminal.') from e
            # pywinpty quotes the argument list itself. Passing a quoted string
            # first would preserve literal quotes on paths/commands with spaces.
            self.win=PtyProcess.spawn(argv,cwd=str(cwd),env=env,dimensions=(rows,cols))
            self.kind='ConPTY/pywinpty'
        else:
            import pty,fcntl,termios,struct
            master,slave=pty.openpty();self.fd=master
            fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',rows,cols,0,0))
            # The short child establishes its controlling terminal after Popen's
            # setsid, without running Python preexec_fn in a multi-threaded server.
            launch=([sys.executable,'--pty-child'] if getattr(sys,'frozen',False) else [sys.executable,str(project/'app.py'),'--pty-child'])+argv
            try:
                self.process=subprocess.Popen(launch,stdin=slave,stdout=slave,stderr=slave,cwd=cwd,env=env,start_new_session=True,close_fds=True)
            except Exception:
                os.close(master);self.fd=None;raise
            finally:os.close(slave)
            self.kind='POSIX PTY'
        self.thread=threading.Thread(target=self._read,name='lumen-pty-reader',daemon=True);self.thread.start()
    def _append(self,text):
        with self.lock:
            self.output+=text
            if len(self.output)>1_000_000:
                count=len(self.output)-750_000;self.output=self.output[count:];self.start+=count
    def _read(self):
        try:
            if self.win:
                while not self.closed:
                    try: text=self.win.read(4096)
                    except EOFError:break
                    if text:self._append(text)
                    elif not self.win.isalive():break
            else:
                while not self.closed:
                    ready,_,_=select.select([self.fd],[],[],.2)
                    if ready:
                        try:data=os.read(self.fd,16384)
                        except OSError:break
                        if not data:break
                        self._append(self.decoder.decode(data))
                    elif self.process.poll() is not None:break
                self._append(self.decoder.decode(b'',final=True))
        finally:
            with self.lock:
                if self.process and self.process.poll() is not None:self.code=self.process.returncode
                self.closed=True
            if self.fd is not None:
                try:os.close(self.fd)
                except OSError:pass
                self.fd=None
    def read(self,offset=0):
        with self.lock:
            absolute=max(int(offset),self.start)
            return {'id':self.id,'data':self.output[absolute-self.start:],'offset':self.start+len(self.output),
                'truncated':int(offset)<self.start,'closed':self.closed,'code':self.code,'kind':self.kind}
    def write(self,text):
        if not isinstance(text,str) or len(text)>65536:raise ValueError('Entrada de terminal demasiado grande.')
        if self.closed:return False
        try:
            if self.win:self.win.write(text)
            else:
                raw=text.encode('utf-8');offset=0
                while offset<len(raw):offset+=os.write(self.fd,raw[offset:])
        except (EOFError,BrokenPipeError):
            # xterm can reply to a terminal query just after a short script
            # exits. This is a normal closed stream, not an internal error.
            self.closed=True;return False
        return True
    def resize(self,cols,rows):
        cols=max(20,min(int(cols),500));rows=max(5,min(int(rows),200))
        if self.closed:return
        if self.win:
            try:self.win.setwinsize(rows,cols)
            except EOFError:self.closed=True
        else:
            import fcntl,termios,struct
            fcntl.ioctl(self.fd,termios.TIOCSWINSZ,struct.pack('HHHH',rows,cols,0,0))
    def close(self):
        if self.win:
            try:self.win.terminate(force=True)
            except (OSError,EOFError):pass
        elif self.process and self.process.poll() is None:
            try:os.killpg(self.process.pid,signal.SIGTERM)
            except OSError:pass
            try:self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:os.killpg(self.process.pid,signal.SIGKILL)
                except OSError:pass
        self.closed=True
        self.thread.join(timeout=2)


class TerminalManager:
    def __init__(self,prefs,project):self.prefs=prefs;self.project=project;self.sessions={};self.lock=threading.RLock()
    def profiles(self):
        result=terminal_profiles()
        conpty=os.name!='nt' or importlib.util.find_spec('winpty') is not None
        return {'profiles':result,'interactiveAvailable':conpty,'platform':platform.system(),'note':'Los sistemas Linux/WSL/Kali solo se muestran cuando están instalados; CMake es una herramienta de construcción, no una shell.'}
    def create(self,ws,profile_id,consent=False,cols=100,rows=26):
        if not ws.trusted or consent is not True:raise PermissionError('Confirma la confianza y la apertura de la terminal.')
        if not self.prefs.get('security.terminals'):raise PermissionError('Las terminales están desactivadas en Seguridad.')
        with self.lock:
            if sum(not s.closed for s in self.sessions.values())>=6:raise ValueError('Límite de seis terminales activas.')
            for sid in list(self.sessions):
                if self.sessions[sid].closed:del self.sessions[sid]
            profile=next((p for p in terminal_profiles() if p['id']==profile_id),None)
            if not profile:raise ValueError('Ese perfil no está disponible en este sistema.')
            session=TerminalSession(profile,ws.root,self.project,max(20,min(int(cols),500)),max(5,min(int(rows),200)))
            self.sessions[session.id]=session
            self.prefs.audit('terminal.open',profile=profile_id)
            return {'id':session.id,'profile':profile,'kind':session.kind}
    def get(self,sid):
        with self.lock:
            s=self.sessions.get(sid)
            if not s:raise FileNotFoundError('Sesión de terminal no disponible.')
            return s
    def list(self):
        with self.lock:return [{'id':s.id,'label':s.profile['label'],'profile':s.profile,'closed':s.closed,'kind':s.kind} for s in self.sessions.values()]
    def shutdown(self):
        with self.lock:
            for s in self.sessions.values():s.close()
            self.sessions.clear()
