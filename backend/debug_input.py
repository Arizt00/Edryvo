"""Nonblocking Windows named pipe for LLDB's documented stdio redirection."""
import ctypes
from ctypes import wintypes
import threading
import time
import uuid

class DebugInput:
    def __init__(self):
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True);self.lock=threading.Lock();self.closed=False
        self.kernel.CreateNamedPipeW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p];self.kernel.CreateNamedPipeW.restype=wintypes.HANDLE
        self.kernel.ConnectNamedPipe.argtypes=[wintypes.HANDLE,ctypes.c_void_p];self.kernel.ConnectNamedPipe.restype=wintypes.BOOL
        self.kernel.WriteFile.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD),ctypes.c_void_p];self.kernel.WriteFile.restype=wintypes.BOOL
        self.kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        self.path='\\\\.\\pipe\\lumen-debug-'+uuid.uuid4().hex
        # Outbound (IDE -> debuggee), first instance, byte stream, nonblocking, local only.
        self.handle=self.kernel.CreateNamedPipeW(self.path,2|0x80000,1|8,1,65536,65536,0,None)
        if self.handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
        self.kernel.ConnectNamedPipe(self.handle,None)
    def write(self,text):
        data=text.encode('utf-8');offset=0;deadline=time.monotonic()+3
        with self.lock:
            while offset<len(data):
                if self.closed:raise ValueError('La entrada de depuración está cerrada.')
                written=wintypes.DWORD();chunk=ctypes.create_string_buffer(data[offset:])
                ok=self.kernel.WriteFile(self.handle,chunk,len(data)-offset,ctypes.byref(written),None)
                if ok and written.value:offset+=written.value;continue
                error=ctypes.get_last_error()
                if not ok and error not in (232,535,536):raise ctypes.WinError(error)
                if time.monotonic()>=deadline:raise ValueError('El programa no ha leído la entrada todavía. Espera antes de volver a enviar.')
                time.sleep(.015)
        return {'ok':True,'bytes':offset}
    def close(self):
        with self.lock:
            if not self.closed:self.closed=True;self.kernel.CloseHandle(self.handle)
