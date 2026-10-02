"""Disk-streamed SDK downloads, with validated range resumption and no auto-execution."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import threading
import time
import urllib.request
import urllib.parse
import uuid
from .preferences import atomic_json

MAX_DOWNLOAD = 500_000_000_000
CHUNK = 1024 * 1024


def validate_url(url):
    p = urllib.parse.urlsplit(url)
    if p.scheme != 'https' and not (p.scheme == 'http' and p.hostname in ('127.0.0.1', 'localhost', '::1')):
        raise ValueError('Usa una URL HTTPS del distribuidor del compilador.')
    if not p.hostname or p.username or p.password: raise ValueError('URL no válida.')
    return url


class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, url):
        validate_url(url)
        return super().redirect_request(req, fp, code, msg, headers, url)


class Downloads:
    def __init__(self, directory):
        self.root = Path(directory) / 'downloads'; self.root.mkdir(parents=True, exist_ok=True)
        self.index = self.root / 'index.json'; self.lock = threading.RLock(); self.events = {}; self.threads = {}
        try: self.items = json.loads(self.index.read_text(encoding='utf-8'))
        except (OSError, ValueError): self.items = {}
        for item in self.items.values():
            if item['status'] in ('downloading', 'verifying'): item['status'] = 'paused'

    def save(self): atomic_json(self.index, self.items)

    def snapshot(self):
        with self.lock:
            return {'items': copy.deepcopy(list(self.items.values())), 'limit': MAX_DOWNLOAD, 'directory': str(self.root), 'free': shutil.disk_usage(self.root).free}

    def start(self, url, name, sha256=''):
        validate_url(url)
        if not isinstance(name, str) or not re.fullmatch(r'[\w .()+-]{1,160}', name) or name.endswith(('.', ' ')) or Path(name).stem.upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(10)],*[f'LPT{i}' for i in range(10)]}: raise ValueError('Nombre de archivo no válido.')
        if sha256 and not re.fullmatch('[a-fA-F0-9]{64}', sha256): raise ValueError('SHA-256 no válido.')
        with self.lock:
            if len(self.items) >= 100: raise ValueError('El historial admite hasta 100 descargas.')
            if any(x['name'].casefold() == name.casefold() for x in self.items.values()) or (self.root/name).exists(): raise ValueError('Ya existe una descarga con ese nombre.')
            key = uuid.uuid4().hex
            self.items[key] = {'id':key, 'url':url, 'name':name, 'sha256':sha256.lower(), 'bytes':0, 'total':None, 'status':'paused', 'error':'', 'validator':'', 'speed':0}
            self.save()
        return self.resume(key)

    def resume(self, key):
        with self.lock:
            item = self.items[key]
            if self.threads.get(key) and self.threads[key].is_alive(): raise ValueError('Espera a que termine la operación actual.')
            if item['status'] == 'complete': return self.snapshot()
            if sum(t.is_alive() for t in self.threads.values()) >= 2: raise ValueError('Hay dos descargas activas.')
            event = threading.Event(); self.events[key] = event
            item.update(status='downloading', error=''); self.save()
            thread = threading.Thread(target=self.run, args=(key,event), daemon=True); self.threads[key]=thread; thread.start()
        return self.snapshot()

    def pause(self, key):
        with self.lock:
            if key not in self.items: raise ValueError('Descarga desconocida.')
            if key in self.events: self.events[key].set()
        return self.snapshot()

    def run(self, key, event):
        item = self.items[key]; partial = self.root / (key+'.part')
        try:
            offset = partial.stat().st_size if partial.exists() else 0
            if not (item.get('bodyComplete') and item.get('bytes')==offset and partial.exists()):
                headers = {'User-Agent':'LumenStudio/0.5.2', 'Accept-Encoding':'identity'}
                if offset and item['validator']: headers.update({'Range':f'bytes={offset}-','If-Range':item['validator']})
                response = urllib.request.build_opener(Redirect()).open(urllib.request.Request(item['url'], headers=headers), timeout=30)
                with response:
                    resumed = response.status == 206
                    if resumed:
                        match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',response.headers.get('Content-Range',''))
                        if not match or int(match[1]) != offset: raise ValueError('El servidor devolvió un rango incorrecto.')
                        total = int(match[3])
                    else:
                        offset = 0; total = int(response.headers['Content-Length']) if response.headers.get('Content-Length') else None
                    if total is not None and total > MAX_DOWNLOAD: raise ValueError('El archivo supera los 500 GB.')
                    if total and total-offset > shutil.disk_usage(self.root).free-16*CHUNK: raise ValueError('Espacio insuficiente para completar la descarga.')
                    validator = response.headers.get('ETag','')
                    if not validator or validator.startswith('W/'): validator=response.headers.get('Last-Modified','')
                    with self.lock: item.update(bytes=offset,total=total,validator=validator); self.save()
                    started=time.monotonic(); initial=offset; last=started
                    with partial.open('ab' if resumed else 'wb') as output:
                        while not event.is_set():
                            chunk=response.read(CHUNK)
                            if not chunk: break
                            if offset+len(chunk)>MAX_DOWNLOAD: raise ValueError('El archivo supera los 500 GB.')
                            if shutil.disk_usage(self.root).free < len(chunk)+16*CHUNK: raise ValueError('Espacio insuficiente; puedes reanudar después de liberar disco.')
                            output.write(chunk); offset+=len(chunk)
                            with self.lock: item.update(bytes=offset,speed=(offset-initial)/max(.01,time.monotonic()-started))
                            if time.monotonic()-last>1:
                                output.flush()
                                with self.lock:self.save()
                                last=time.monotonic()
                if total is not None and offset==total:item['bodyComplete']=True
                if event.is_set():
                    with self.lock:item['status']='paused'
                    return
                if total is not None and offset != total: raise ValueError('Transferencia incompleta. Puedes reanudarla.')
                item['bodyComplete']=True
                with self.lock:self.save()
            if item['sha256']:
                with self.lock:item['status']='verifying'
                digest=hashlib.sha256()
                with partial.open('rb') as stream:
                    while chunk:=stream.read(CHUNK):
                        if event.is_set():
                            with self.lock:item['status']='paused'
                            return
                        digest.update(chunk)
                if digest.hexdigest()!=item['sha256']:
                    item.update(bodyComplete=False,validator='')
                    raise ValueError('SHA-256 incorrecto. Al reanudar se descargará de nuevo. El archivo no se ha publicado.')
            target=self.root/item['name']
            if target.exists(): raise ValueError('El destino ya existe.')
            partial.rename(target)
            with self.lock:item.update(status='complete',path=str(target),speed=0)
        except Exception as exc:
            with self.lock:item.update(status='paused' if event.is_set() else 'error',error=str(exc),speed=0)
        finally:
            with self.lock:self.save()

    def shutdown(self):
        for event in self.events.values():event.set()
