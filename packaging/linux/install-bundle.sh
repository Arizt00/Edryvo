#!/bin/sh
# Per-user installation of the native portable package. No sudo or source build.
set -eu
base=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
target="$HOME/.local/opt/lumen-studio/0.5.2-R9"
[ -x "$base/LumenStudio/lumen" ] || { echo 'Falta el ejecutable nativo de Linux.' >&2; exit 1; }
[ ! -e "$target" ] || { echo 'Esta versión ya está instalada. Los datos se conservan.' >&2; exit 1; }
mkdir -p "$HOME/.local/opt/lumen-studio" "$HOME/.local/bin" "$HOME/.local/share/applications"
cp -R "$base/LumenStudio" "$target"
ln -sfn "$target/lumen" "$HOME/.local/bin/lumen"
cat > "$HOME/.local/share/applications/lumen-studio.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Edryvo
Comment=Editor, Lantern Live y Forge
Exec="$target/lumen"
Icon=$target/_internal/web/assets/lumen.svg
Terminal=false
Categories=Development;IDE;
EOF
printf 'Edryvo instalado en %s. Ábrelo desde el menú de aplicaciones o ~/.local/bin/lumen\n' "$target"
printf 'No requiere Python global. Los compiladores y SDK de tus proyectos se preparan aparte.\n'
