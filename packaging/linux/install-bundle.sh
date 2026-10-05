#!/bin/sh
# Per-user installation of the native portable package. No sudo or source build.
set -eu
base=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
target="$HOME/.local/opt/zenit/0.5.3-R2"
[ -x "$base/Zenit/zenit" ] || { echo 'Falta el ejecutable nativo de Linux.' >&2; exit 1; }
[ ! -e "$target" ] || { echo 'Esta versión ya está instalada. Los datos se conservan.' >&2; exit 1; }
mkdir -p "$HOME/.local/opt/zenit" "$HOME/.local/bin" "$HOME/.local/share/applications"
cp -R "$base/Zenit" "$target"
ln -sfn "$target/zenit" "$HOME/.local/bin/zenit"
cat > "$HOME/.local/share/applications/zenit.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Zénit
Comment=Editor, Lantern Live y Forge
Exec="$target/zenit"
Icon=$target/_internal/web/assets/lumen.svg
Terminal=false
Categories=Development;IDE;
EOF
printf 'Zénit instalado en %s. Ábrelo desde el menú de aplicaciones o ~/.local/bin/zenit\n' "$target"
printf 'No requiere Python global. Los compiladores y SDK de tus proyectos se preparan aparte.\n'
