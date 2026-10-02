"""Detect SDKs without changing the user's PATH or invoking rustup installers."""
import os
from pathlib import Path
import shutil

def find_tool(name, configured=None):
    explicit=(configured or {}).get(name)
    if explicit:
        path=Path(explicit).expanduser()
        return str(path) if path.is_file() else shutil.which(explicit)
    if name=='rustc' and os.name=='nt':
        base=Path(os.environ.get('RUSTUP_HOME',Path.home()/'.rustup'))/'toolchains'
        for channel in ('stable-x86_64-pc-windows-msvc','stable-x86_64-pc-windows-gnu'):
            file=base/channel/'bin/rustc.exe'
            if file.is_file():return str(file)
    if found:=shutil.which(name):return found
    if name=='dlv':
        file=Path(__file__).resolve().parents[1]/'debugger-support/delve/dlv.exe'
        if file.is_file():return str(file)
    if name=='netcoredbg':
        for file in (Path(__file__).resolve().parents[1]/'debugger-support/netcoredbg').glob('**/netcoredbg.exe'):
            return str(file)
    if os.name!='nt':return None
    suffix=name if name.endswith('.exe') else name+'.exe'
    roots=[Path(os.environ.get('ProgramFiles','C:/Program Files'))/'LLVM/bin',Path('C:/msys64/ucrt64/bin'),Path('C:/msys64/mingw64/bin'),Path('C:/Program Files/Go/bin'),Path.home()/'go/bin',Path.home()/'.cargo/bin',Path('C:/Program Files/dotnet')]
    for root in roots:
        file=root/suffix
        if file.is_file():return str(file)
    return None
