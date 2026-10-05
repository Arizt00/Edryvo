# Build only on the target operating system. No cross-compilation or signing.
from pathlib import Path
import importlib.util
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
ROOT=Path(SPECPATH).parent
hidden=['lumen','backend.server','backend.platform_services','backend.preferences','backend.extensions','backend.terminals','backend.hardware','backend.toolchains','backend.lsp','backend.providers','backend.studio','backend.debugger','backend.debug_worker','psutil','keyring.backends']
if sys.platform=='win32':hidden+=['winpty']
if sys.platform.startswith('linux'):hidden+=['qtpy','PySide6.QtWebEngineWidgets','PySide6.QtWebEngineCore','PySide6.QtWebChannel']
for package in ('webview','keyring','copilot'):
    if importlib.util.find_spec(package):hidden+=collect_submodules(package)
data=[(str(ROOT/'web'),'web'),(str(ROOT/'licenses'),'licenses'),(str(ROOT/'README.md'),'.'),(str(ROOT/'LICENSE'),'.'),(str(ROOT/'THIRD_PARTY_NOTICES.md'),'.'),(str(ROOT/'LEEME_PRIMERO.txt'),'.'),(str(ROOT/'config/runtime-defaults.json'),'config'),(str(ROOT/'debugger-support'),'debugger-support'),(str(ROOT/'examples/lantern/counter.c'),'examples/lantern'),(str(ROOT/'examples/lantern/counter.cpp'),'examples/lantern'),(str(ROOT/'examples/lantern/counter.n'),'examples/lantern'),(str(ROOT/'backend/LumenJavaDebugger.java'),'backend'),(str(ROOT/'backend/emma_bridge.mjs'),'backend'),(str(ROOT/'backend/lantern_memory.cjs'),'backend'),(str(ROOT/'backend/extension_host.cjs'),'backend'),(str(ROOT/'backend/extension_api.cjs'),'backend')]
# Package documentation deliberately: historical QA can contain local user paths.
data.append((str(ROOT/'backend/extension_views.cjs'),'backend'))
data.append((str(ROOT/'backend/extension_services.cjs'),'backend'))
for name in ('PREVIEW_053_R1.md','PREVIEW_R9.md','PREVIEW_R8.md','PREVIEW_R7.md','PREVIEW_R6.md','PREVIEW_R5.md','LENGUAJES.md','EXTENSIONES.md','SEGURIDAD.md'):
    data.append((str(ROOT/'docs'/name),'docs'))
# Only the shipped examples belong in the bundle, never compiler/profile caches.
for file in (ROOT/'workspace').rglob('*'):
    relative=file.relative_to(ROOT)
    if file.is_file() and not any(part in ('.ncc','.lumen','__pycache__','.git') for part in relative.parts):
        data.append((str(file),str(relative.parent)))
for package in ('webview','winpty'):
    if importlib.util.find_spec(package):data+=collect_data_files(package)
binaries=[]
for name in ('lumen_core.dll','liblumen_core.dylib','liblumen_core.so'):
    for directory in ('native/build/lib','native/build/lib/Release'):
        path=ROOT/directory/name
        if path.exists():binaries.append((str(path),directory))
excludes=['playwright','tkinter','PyQt5','PyQt6','PySide2']
if not sys.platform.startswith('linux'):excludes+=['PySide6','qtpy']
a=Analysis([str(ROOT/'app.py')],pathex=[str(ROOT)],binaries=binaries,datas=data,hiddenimports=hidden,hookspath=[],excludes=excludes,noarchive=False)
pyz=PYZ(a.pure)
icon=ROOT/('packaging/macos/lumen.icns' if sys.platform=='darwin' else 'web/assets/lumen.ico')
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='lumen',debug=False,bootloader_ignore_signals=False,strip=False,version=str(ROOT/'packaging/version.txt') if sys.platform=='win32' else None,upx=False,console=False if sys.platform in ('win32','darwin') else True,disable_windowed_traceback=False,icon=str(icon) if icon.exists() else None)
# The GUI executable cannot supply console handles to a ConPTY Python task.
# Reuse its analyzed modules/runtime in a console helper hosted by the IDE PTY.
python_exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='lumen-python',debug=False,bootloader_ignore_signals=False,strip=False,version=str(ROOT/'packaging/version.txt') if sys.platform=='win32' else None,upx=False,console=True)
collection=COLLECT(exe,python_exe,a.binaries,a.datas,strip=False,upx=False,name='LumenStudio')
if sys.platform=='darwin':
    app=BUNDLE(collection,name='Edryvo.app',icon=str(icon) if icon.exists() else None,bundle_identifier='studio.lumen.ide',info_plist={'CFBundleShortVersionString':'0.5.3','CFBundleVersion':'0.5.3.1','NSHighResolutionCapable':True,'LSMinimumSystemVersion':'14.0','NSHumanReadableCopyright':'Edryvo. Licencia propietaria de preview.'})
