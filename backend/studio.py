"""Local profile and workbench state, independent of the WebView's random port."""
from __future__ import annotations
import base64
import copy
import getpass
import json
import threading
from .preferences import atomic_json


class StudioState:
    def __init__(self, directory):
        self.path = directory / 'studio.json'
        self.lock = threading.RLock()
        self.data = {'displayName': getpass.getuser(), 'avatar': '', 'onboarded': False,
                     'layout': None, 'recent': [], 'workspaceStyle': 'general'}
        try:
            self.update(json.loads(self.path.read_text(encoding='utf-8')), save=False)
        except (OSError, ValueError, TypeError):
            pass

    def export(self):
        with self.lock:
            return copy.deepcopy(self.data)

    def update(self, changes, save=True):
        if not isinstance(changes, dict) or set(changes) - set(self.data):
            raise ValueError('Datos de perfil no válidos.')
        with self.lock:
            draft = copy.deepcopy(self.data)
            for key, value in changes.items():
                if key == 'displayName':
                    if not isinstance(value, str) or not value.strip() or len(value) > 40 or any(ord(c) < 32 for c in value):
                        raise ValueError('El nombre debe tener entre 1 y 40 caracteres.')
                    value = value.strip()
                elif key == 'avatar':
                    if not isinstance(value, str) or len(value) > 1_000_000:
                        raise ValueError('La imagen de perfil es demasiado grande.')
                    if value:
                        prefix, separator, payload = value.partition(',')
                        if not separator or prefix not in ('data:image/png;base64', 'data:image/jpeg;base64', 'data:image/webp;base64'):
                            raise ValueError('Usa una imagen PNG, JPEG o WebP.')
                        try:
                            raw = base64.b64decode(payload, validate=True)
                        except ValueError as exc:
                            raise ValueError('Imagen no válida.') from exc
                        if not (raw.startswith(b'\x89PNG\r\n\x1a\n') or raw.startswith(b'\xff\xd8\xff') or (raw.startswith(b'RIFF') and raw[8:12] == b'WEBP')):
                            raise ValueError('El contenido no corresponde a una imagen.')
                elif key == 'onboarded':
                    if type(value) is not bool:
                        raise ValueError('Estado de bienvenida no válido.')
                elif key == 'workspaceStyle':
                    if value not in ('general', 'web', 'data', 'design', 'assembly'):
                        raise ValueError('Estilo de espacio desconocido.')
                elif key == 'layout':
                    if value is not None and (not isinstance(value, dict) or len(json.dumps(value)) > 6000):
                        raise ValueError('Distribución no válida.')
                elif key == 'recent':
                    if not isinstance(value, list) or len(value) > 30:
                        raise ValueError('Historial no válido.')
                    for item in value:
                        if not isinstance(item, dict) or set(item) != {'path', 'workspace', 'openedAt'} or any(not isinstance(v, str) or len(v) > 2048 for v in item.values()):
                            raise ValueError('Entrada de historial no válida.')
                draft[key] = value
            if save:
                atomic_json(self.path, draft)
            self.data = draft
            return self.export()
