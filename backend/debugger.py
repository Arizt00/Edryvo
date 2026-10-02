"""A real, explicitly trusted Python debugger. No simulated DAP or Unity sessions."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from .terminals import child_environment


class PythonDebugger:
    def __init__(self):
        self.lock = threading.RLock()
        self.process = None
        self.state = {'status': 'idle', 'output': '', 'variables': [], 'stack': []}

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.state)

    def start(self, workspace, path, breakpoints):
        if not workspace.trusted:
            raise PermissionError('Autoriza el proyecto antes de depurar código.')
        record = workspace.read(path)
        if not path.lower().endswith(('.py','.pyw')):
            raise ValueError('El depurador integrado admite archivos Python.')
        if not isinstance(breakpoints, list) or len(breakpoints) > 200 or any(type(x) is not int or x < 1 for x in breakpoints):
            raise ValueError('Puntos de interrupción no válidos.')
        compile(record['content'], path, 'exec')
        with self.lock:
            if self.process and self.process.poll() is None:
                raise ValueError('Ya hay una sesión de depuración activa.')
            file = (workspace.root / path).resolve()
            worker = [sys.executable, '--debug-child'] if getattr(sys, 'frozen', False) else [sys.executable, str(Path(__file__).with_name('debug_worker.py'))]
            self.state = {'status': 'running', 'path': path, 'output': '', 'variables': [], 'stack': []}
            process = subprocess.Popen(worker + [str(file), json.dumps(breakpoints)], cwd=workspace.root,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                encoding='utf-8', errors='replace', bufsize=1, env=child_environment(),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            self.process = process
        threading.Thread(target=self._read, args=(process,), daemon=True).start()
        threading.Thread(target=self._errors, args=(process,), daemon=True).start()
        return self.snapshot()

    def _errors(self, process):
        for line in process.stderr:
            with self.lock:
                if process is self.process:
                    self.state['output'] = (self.state['output'] + line)[-100000:]
        process.stderr.close()

    def _read(self, process):
        for line in process.stdout:
            try:
                event = json.loads(line)
                with self.lock:
                    if process is self.process:
                        if event.get('event') == 'output':
                            self.state['output'] = (self.state['output'] + event['text'])[-100000:]
                        else:
                            self.state.update({k: v for k, v in event.items() if k != 'event'})
            except (ValueError, TypeError):
                pass
        code = process.wait()
        process.stdout.close()
        process.stdin.close()
        with self.lock:
            if process is self.process and self.state['status'] not in ('error', 'stopped'):
                self.state['status'] = 'finished' if code == 0 else 'error'
                self.state['variables'] = []; self.state['stack'] = []

    def command(self, command):
        if command not in ('continue', 'next', 'step', 'out', 'pause', 'stop'):
            raise ValueError('Comando de depuración desconocido.')
        with self.lock:
            if command == 'stop':
                self.stop()
                return self.snapshot()
            if not self.process or self.process.poll() is not None or self.state['status'] != ('running' if command=='pause' else 'paused'):
                raise ValueError('La sesión no está en pausa.')
            self.process.stdin.write(command + '\n'); self.process.stdin.flush()
            self.state['status'] = 'running'
            return self.snapshot()

    def input(self,text):
        if not isinstance(text,str) or len(text)>65536:raise ValueError('Entrada no válida.')
        with self.lock:
            if not self.process or self.process.poll() is not None:raise ValueError('No hay programa activo.')
            self.process.stdin.write(json.dumps({'input':text})+'\n');self.process.stdin.flush()
        return {'ok':True}

    def stop(self):
        with self.lock:
            process = self.process
            if process and process.poll() is None:
                self.state['status'] = 'stopped'
                process.terminate()
                try: process.wait(timeout=3)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=3)
            self.state['variables'] = []; self.state['stack'] = []
