#!/bin/sh
# Installer for a PyInstaller Linux bundle, not for the source checkout.
set -eu
base=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
target="$HOME/.local/opt/lumen-studio-0.5.2"
[ -x "$base/LumenStudio/lumen" ] || { echo 'Falta el ejecutable nativo de Linux.' >&2; exit 1; }
[ ! -e "$target" ] || { echo 'Ya existe esta versión; no se sobrescribe.' >&2; exit 1; }
mkdir -p "$HOME/.local/opt" "$HOME/.local/bin"
cp -R "$base/LumenStudio" "$target"
ln -s "$target/lumen" "$HOME/.local/bin/lumen-0.5.2"
printf 'Lumen instalado en %s. Ejecuta ~/.local/bin/lumen-0.5.2\n' "$target"
printf 'Para desinstalar, elimina únicamente esa carpeta y ese enlace. Los datos personales se conservan.\n'
