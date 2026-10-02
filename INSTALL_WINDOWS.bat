@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Se necesita Python 3.10 o posterior. El instalador no requiere administrador.
  pause
  exit /b 1
)
py -3 tools\install_user.py --launch %*
if errorlevel 1 pause
