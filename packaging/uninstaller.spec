from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
ROOT=Path(SPECPATH).parent
data=[(str(ROOT/'web/uninstall.html'),'web'),(str(ROOT/'web/uninstall.css'),'web'),(str(ROOT/'web/src/uninstall.js'),'web/src'),(str(ROOT/'web/assets/lumen.svg'),'web/assets'),(str(ROOT/'licenses'),'licenses'),(str(ROOT/'LICENSE'),'.'),(str(ROOT/'THIRD_PARTY_NOTICES.md'),'.')]+collect_data_files('webview')
a=Analysis([str(ROOT/'uninstaller.py')],pathex=[str(ROOT)],datas=data,binaries=[],hiddenimports=collect_submodules('webview')+collect_submodules('keyring')+['win32com.client','pythoncom','pywintypes','psutil'],excludes=['playwright','tkinter','PySide6','PyQt5','PyQt6'],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name='Uninstall-Lumen',console=False,upx=False,strip=False,version=str(ROOT/'packaging/version.txt'),icon=str(ROOT/'web/assets/lumen.ico'))
