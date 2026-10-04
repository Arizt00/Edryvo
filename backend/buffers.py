"""Unsaved buffers shared by native windows, with optimistic conflict detection."""
import threading


class Buffers:
    def __init__(self):self.lock=threading.RLock();self.items={}
    def snapshot(self):
        with self.lock:return {'buffers':[dict(x) for x in self.items.values()]}
    def update(self, ws, body):
        path=body.get('path');ws.resolve(path,must_exist=False)
        text=body.get('text');expected=body.get('sequence',0)
        if not isinstance(text,str) or len(text)>2_000_000:raise ValueError('El búfer compartido admite hasta 2 MB.')
        if type(expected) is not int:raise ValueError('Revisión inválida.')
        revision=body.get('revision')
        if revision is not None and (not isinstance(revision,str) or len(revision)>100):raise ValueError('Revisión de archivo inválida.')
        with self.lock:
            old=self.items.get(path)
            if old and expected!=old['sequence']:return {'conflict':True,'buffer':dict(old)}
            if not old and len(self.items)>=200:raise ValueError('Límite de 200 búferes compartidos.')
            result={'path':path,'text':text,'sequence':(old['sequence'] if old else 0)+1,'saved':body.get('saved') is True,'revision':revision}
            self.items[path]=result
            return {'buffer':dict(result),'conflict':False}
    def clear(self):
        with self.lock:self.items.clear()
