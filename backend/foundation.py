"""Bundled SDK discovery. Project interpreters stay separate from the IDE runtime."""
import json
import os
from pathlib import Path
import sys

C_STANDARDS = ('c89', 'c90', 'c99', 'c11', 'c17', 'c23', 'gnu89', 'gnu99', 'gnu11', 'gnu17', 'gnu23')
CPP_STANDARDS = ('c++98', 'c++03', 'c++11', 'c++14', 'c++17', 'c++20', 'c++23', 'c++26')
ARCHITECTURES = ('x86', 'x86_64', 'arm', 'arm64', 'riscv64')

def roots():
    candidates = []
    if os.environ.get('ZENIT_SDK_ROOT'):
        candidates.append(Path(os.environ['ZENIT_SDK_ROOT']))
    if getattr(sys, 'frozen', False):
        candidates.extend((Path(sys.executable).parent / 'sdk/foundation', Path(getattr(sys, '_MEIPASS', '.')) / 'sdk/foundation'))
        candidates.append(Path(sys.executable).parent.parent / 'sdk/foundation')
    candidates.append(Path(__file__).resolve().parents[1] / 'sdk/foundation')
    return candidates

def inventory():
    for root in roots():
        try:
            data = json.loads((root / 'tool-index.json').read_text(encoding='utf-8'))
            if data.get('schema') == 1:
                return root.resolve(), data
        except (OSError, ValueError):
            pass
    return None, {'schema': 1, 'tools': {}, 'components': []}

def bundled_tool(name):
    root, data = inventory()
    relative = data.get('tools', {}).get(name)
    if root is None or not isinstance(relative, str):
        return None
    candidate = (root / relative).resolve()
    if candidate.is_relative_to(root) and candidate.is_file():
        return str(candidate)
    return None

def python_command():
    executable = bundled_tool('python')
    if executable:
        return [executable, '-u']
    return [sys.executable, '--python-child'] if getattr(sys, 'frozen', False) else [sys.executable, '-u']

def tool_environment():
    root, data = inventory()
    bins = []
    for relative in data.get('tools', {}).values():
        if root and isinstance(relative, str):
            directory = (root / relative).resolve().parent
            if directory.is_relative_to(root) and directory.is_dir() and str(directory) not in bins:
                bins.append(str(directory))
    environment = {'PATH': os.pathsep.join([*bins, os.environ.get('PATH', '')]), 'PYTHONNOUSERSITE': '1'}
    java = bundled_tool('java')
    if java:
        environment['JAVA_HOME'] = str(Path(java).parents[1])
    return environment

def status():
    from .runtime_paths import find_tool
    root, data = inventory()
    names = ('python', 'gcc', 'g++', 'clang', 'java', 'javac', 'bash', 'ncc', 'node', 'docker', 'qemu-system-x86_64', 'mvn', 'gradle')
    return {'bundle': bool(root), 'directory': str(root) if root else None,
            'components': data.get('components', []),
            'tools': [{'id': name, 'path': find_tool(name), 'bundled': bool(bundled_tool(name))} for name in names],
            'architectures': list(ARCHITECTURES), 'standards': {'c': list(C_STANDARDS), 'cpp': list(CPP_STANDARDS)},
            'dependencyPolicy': 'Bibliotecas estándar incluidas; paquetes de proyecto en venv, Maven/Gradle o el gestor de su lenguaje.'}
