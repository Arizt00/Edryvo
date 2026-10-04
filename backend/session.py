"""Durable workspace selection; independent of ports and browser storage."""
from pathlib import Path
import json
from .preferences import atomic_json, user_data_dir


def last_workspace(directory=None):
    try:
        data = json.loads(((directory or user_data_dir()) / 'session.json').read_text(encoding='utf-8'))
        path = Path(data['workspace']).expanduser().resolve()
        return path if path.is_dir() else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def remember_workspace(workspace, directory=None):
    atomic_json((directory or user_data_dir()) / 'session.json', {'workspace': str(Path(workspace).resolve())})
