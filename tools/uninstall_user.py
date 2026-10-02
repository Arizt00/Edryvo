#!/usr/bin/env python3
"""Remove only this installer-owned version. Never remove user workspaces/keys."""
import argparse
import json
import shutil
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description='Desinstala la aplicación; conserva preferencias, claves y proyectos.')
    p.add_argument('--yes',action='store_true');a=p.parse_args()
    root=Path(__file__).resolve().parents[1];marker=root/'.lumen-source-install.json'
    if not marker.is_file():p.error('Esta carpeta no tiene un manifiesto de instalación. No se eliminará.')
    plan=json.loads(marker.read_text())
    if Path(plan.get('application','')).resolve()!=root:p.error('La ruta no coincide con el manifiesto.')
    if not a.yes and input(f'Eliminar solo {root}? Escribe ELIMINAR: ')!='ELIMINAR':return
    for value in plan.get('launchers',[]):
        path=Path(value)
        if path.is_file() and str(root) in path.read_text(encoding='utf-8',errors='replace'):path.unlink()
    # Run this script with an external Python interpreter on Windows, so the
    # installer virtual environment is not kept locked by its own interpreter.
    shutil.rmtree(root)
    print('Aplicación eliminada. Preferencias y proyectos conservados. Los accesos del menú pueden retirarse manualmente.')
if __name__=='__main__':main()
