from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
ROOT=Path(SPECPATH).parent
data=[(str(ROOT/'dist/Uninstall-Zenit.exe'),'.'),(str(ROOT/'web'),'web'),(str(ROOT/'dist/Zenit'),'payload')]+collect_data_files('webview')
a=Analysis([str(ROOT/'installer.py')],pathex=[str(ROOT)],datas=data,binaries=[],hiddenimports=collect_submodules('webview'),excludes=['playwright','tkinter','PySide6','PyQt5','PyQt6'],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name='Zenit-0.5.3-R4-Windows-Setup',console=False,upx=False,strip=False,version=str(ROOT/'packaging/version.txt'),icon=str(ROOT/'web/assets/lumen.ico') if (ROOT/'web/assets/lumen.ico').exists() else None)
