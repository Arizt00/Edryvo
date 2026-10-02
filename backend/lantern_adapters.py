"""Live adapters stage a buffer and validate it before any user code is executed."""
from __future__ import annotations
import ast
import os
from pathlib import Path
import shutil
import sys
from .workspace import Workspace, MAX_FILE
from .runtimes import language

SKIP = {'.git', '.lumen', '.ncc', 'node_modules', '__pycache__', '.venv', 'venv', 'Library', 'Temp', 'obj', 'bin', 'target', 'dist', 'build'}

class Superseded(Exception): pass

def stage(workspace, path, content, directory, obsolete):
    """A bounded private project copy, never links to mutable original sources."""
    workspace.resolve(path, must_exist=False)
    if not isinstance(content, str) or len(content.encode('utf-8')) > MAX_FILE:
        raise ValueError('El buffer de Lantern admite hasta 2 MiB.')
    directory.mkdir(parents=True, exist_ok=True)
    count = total = 0
    for folder, dirs, files in os.walk(workspace.root, followlinks=False):
        if obsolete(): raise Superseded()
        dirs[:] = [d for d in dirs if d not in SKIP]
        for name in dirs + files:
            item = Path(folder) / name
            if item.is_symlink() or (hasattr(item, 'is_junction') and item.is_junction()):
                raise ValueError('Lantern no copia enlaces del proyecto: ' + str(item.relative_to(workspace.root)))
        for name in files:
            if obsolete(): raise Superseded()
            source = Path(folder) / name
            relative = source.relative_to(workspace.root)
            # Exclude secrets, VCS internals and bytecode from the execution copy.
            if name.startswith('.env') or source.suffix == '.pyc': continue
            if relative.as_posix() == path.replace('\\', '/'): continue
            count += 1; total += source.stat().st_size
            if count > 15000 or total > 256 * 1024 * 1024:
                raise ValueError('El contexto Live supera 15 000 archivos o 256 MiB. Abre la carpeta del programa o configura una tarea específica.')
            output = directory / relative; output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, output)
    shadow = Workspace(directory, workspace.native); shadow.trusted = True
    file = shadow.resolve(path, must_exist=False); file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(content, encoding='utf-8', newline='')
    return shadow

def prepare(runtimes, workspace, path):
    """Return separate validation and execution commands. A compiler runs only once."""
    lang = language(path)
    if not lang: raise ValueError('No hay adaptador Lantern para este archivo.')
    profile = runtimes.config['languages'].get(lang, {})
    if profile.get('run') or profile.get('build'):
        if not (profile.get('check') or profile.get('build')):
            raise ValueError('El adaptador personalizado necesita check o build para validar el buffer antes de ejecutarlo.')
        plan = runtimes.plan(workspace, path)
        checks = runtimes.plan(workspace, path, check=True)['commands']
        commands = plan['commands'][-1:]
    elif lang == 'python':
        ast.parse(workspace.resolve(path).read_text(encoding='utf-8'), filename=path)
        plan = runtimes.plan(workspace, path); checks = []; commands = plan['commands']
    elif lang in ('javascript', 'typescript'):
        plan = runtimes.plan(workspace, path)
        checks = runtimes.plan(workspace, path, check=True)['commands']; commands = plan['commands']
    elif lang in ('html', 'css'):
        plan = runtimes.plan(workspace, path); checks = []; commands = []
    elif lang == 'nc':
        if Path(path).suffix.lower() in ('.n', '.nc'):
            plan = runtimes.plan(workspace, path, debug=True); checks = plan['commands']; commands = [[str(plan['target'])]]
        else:
            plan = runtimes.plan(workspace, path); checks = runtimes.plan(workspace, path, check=True)['commands']; commands = plan['commands']
    else:
        plan = runtimes.plan(workspace, path)
        checks = plan['commands'][:-1]; commands = plan['commands'][-1:]
        if not checks: raise ValueError('El adaptador no proporciona una fase de compilación.')
    return {**plan, 'checks': checks, 'commands': commands, 'custom': bool(profile.get('run') or profile.get('build')),
            'lensMode': 'automatic' if lang == 'python' else 'cooperative',
            'adapter': lang, 'preview': plan.get('preview', False)}

def runtime_commands(plan, checkpoint, lens):
    commands = plan['commands']
    if plan.get('custom'): return commands
    if plan['language'] == 'python':
        commands = [[sys.executable, '--lantern-child', str(plan['file']), str(checkpoint)]] if getattr(sys, 'frozen', False) else [[sys.executable, '-u', str(Path(__file__).with_name('lantern_memory.py')), str(plan['file']), str(checkpoint)]]
    elif plan['language'] in ('javascript', 'typescript') and commands and Path(commands[0][0]).stem.lower() == 'node':
        commands = [[commands[0][0], '--require', str(Path(__file__).with_name('lantern_memory.cjs')), *commands[0][1:]]]
    return commands
