@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  set "LUMEN_PY=py -3"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python no esta instalado o no esta en PATH. Se necesita Python 3.10 o posterior.
    pause
    exit /b 1
  )
  set "LUMEN_PY=python"
)
echo.
echo LUMEN STUDIO - Preparando dependencias visuales...
echo La primera vez se descargan Monaco y Babylon desde npm.
%LUMEN_PY% tools\setup_assets.py
if errorlevel 1 echo Se utilizara el modo base hasta que esten disponibles las dependencias.
%LUMEN_PY% app.py %*
if errorlevel 1 pause
endlocal
