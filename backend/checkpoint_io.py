"""Bounded checkpoint reads that allow the program to replace its file atomically."""
import os


def read_checkpoint(path,limit):
    if os.name!='nt':
        with path.open('rb') as stream:data=stream.read(limit+1)
    else:
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        kernel.CreateFileW.restype=wintypes.HANDLE
        kernel.ReadFile.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD),ctypes.c_void_p]
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        # FILE_SHARE_DELETE lets a cooperating program rename its complete
        # checkpoint while the monitor reads the previous file version.
        handle=kernel.CreateFileW(str(path),0x80000000,7,None,3,0x80,None)
        if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
        try:
            buffer=ctypes.create_string_buffer(limit+1);count=wintypes.DWORD()
            if not kernel.ReadFile(handle,buffer,limit+1,ctypes.byref(count),None):raise ctypes.WinError(ctypes.get_last_error())
            data=buffer.raw[:count.value]
        finally:kernel.CloseHandle(handle)
    if len(data)>limit:raise ValueError('El checkpoint supera el límite de lectura.')
    return data
