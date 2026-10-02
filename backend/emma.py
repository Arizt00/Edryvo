"""Bridge to the user-selected Emma source installation, with an isolated local session."""
from pathlib import Path
import json
import os
import queue
import subprocess
import threading
import time
from .runtime_paths import find_tool

def command(directory):
    root = Path(directory).expanduser().resolve()
    if not (root / 'electron/inference-runtime.mjs').is_file():
        raise ValueError('Selecciona la carpeta de Emma que contiene electron/inference-runtime.mjs en Ajustes → Inteligencia artificial.')
    node = find_tool('node')
    if not node: raise ValueError('Emma necesita Node.js. Instálalo en Lenguajes y herramientas.')
    return [str(node), str(Path(__file__).with_name('emma_bridge.mjs')), str(root)]

def models(directory):
    result = subprocess.run([*command(directory), '--models'], capture_output=True, text=True, encoding='utf-8', errors='replace',
                            timeout=12, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    for line in result.stdout.splitlines():
        item = json.loads(line)
        if item.get('type') == 'ready': return {'models':[item['model']], 'verified':True, 'note':'Motor y modelo locales de Emma detectados. No se ha cargado el modelo ni enviado una conversación.'}
        if item.get('type') == 'error': raise ValueError(item['message'])
    raise ValueError('El motor local de Emma no respondió. Revisa la carpeta y Node.js.')

def stream(directory, job, messages, system, max_tokens, timeout):
    process = subprocess.Popen(command(directory), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, encoding='utf-8', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    events=queue.Queue()
    def read():
        try:
            for line in process.stdout:
                if len(line) > 1_000_000: break
                try: events.put(json.loads(line))
                except ValueError: pass
        finally: events.put({'type':'exit'})
    threading.Thread(target=read, daemon=True).start()
    deadline=time.monotonic()+timeout
    try:
        while not job.cancelled.is_set():
            if time.monotonic()>=deadline: raise ValueError('Emma tardó demasiado en responder. Prueba menos contexto o amplía el tiempo de respuesta en Ajustes.')
            try: item=events.get(timeout=.15)
            except queue.Empty: continue
            kind=item.get('type')
            if kind=='ready':
                process.stdin.write(json.dumps({'messages':[{'role':'system','content':system},*messages], 'maxTokens':max_tokens})+'\n');process.stdin.flush()
            elif kind=='status': job.message=item.get('message','')
            elif kind=='delta': job.message='';job.append(item.get('text',''))
            elif kind=='done': job.usage=item.get('metrics',{});return
            elif kind=='error': raise ValueError(item.get('message','Emma no pudo responder.'))
            elif kind=='exit': raise ValueError('El motor de Emma se detuvo antes de completar la respuesta.')
    finally:
        if process.poll() is None:
            try: process.stdin.write('{"cancel":true}\n');process.stdin.flush();process.wait(timeout=3)
            except (OSError,subprocess.TimeoutExpired):
                if os.name=='nt': subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=8,creationflags=subprocess.CREATE_NO_WINDOW)
                else: process.kill()
        process.stdin.close();process.stdout.close()
