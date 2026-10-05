#!/usr/bin/env bash
set -uo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' 'Se necesita Python 3.10 o posterior.'
  exit 1
fi
printf '\n%s\n' 'ZENIT IDE · preparando dependencias visuales.'
printf '%s\n' 'La primera vez se descargan Monaco y Babylon desde npm.'
python3 tools/setup_assets.py || printf '%s\n' 'Se iniciará el modo base. Repite setup_assets.py cuando tengas conexión.'
exec python3 app.py "$@"
