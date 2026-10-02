"""Validated per-user preferences. No credentials are written to this JSON store."""
from __future__ import annotations
import copy
import json
import os
import platform
import re
import tempfile
import threading
from pathlib import Path


def user_data_dir() -> Path:
    override = os.environ.get('LUMEN_DATA_DIR')
    if override:
        return Path(override).expanduser().resolve()
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) / 'LumenStudio'
    if platform.system() == 'Darwin':
        return Path.home() / 'Library/Application Support/LumenStudio'
    return Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'lumen-studio'


def atomic_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, allow_nan=False)
            f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)


# category, default, label ES, label EN, type/choices/min/max, optional requirement
SCHEMA = {
 'general.locale': ('general','es','Idioma de la interfaz','Interface language',['es','en']),
 'general.showWelcome': ('general',True,'Mostrar inicio al abrir Lumen','Show welcome when Lumen starts','bool'),
 'general.restoreLayout': ('general',True,'Recordar la distribución de paneles','Remember panel layout','bool'),
 'appearance.theme': ('appearance','day','Tema','Color theme',['day','dark','forest']),
 'appearance.density': ('appearance','comfortable','Densidad','Density',['comfortable','compact']),
 'appearance.motion': ('appearance',True,'Animaciones','Animations','bool'),
 'appearance.motionDuration': ('appearance',220,'Transición de paneles (ms)','Panel transition (ms)',[80,400]),
 'appearance.decorations': ('appearance',True,'Paisaje y esfera','Landscape and pearl','bool'),
 'appearance.lanternMonitor': ('appearance',True,'Monitor Lantern en Proyecto','Lantern project monitor','bool'),
 'appearance.errorColor': ('appearance','red','Color de los errores de código','Code error color',['red','rose','amber','mint']),
 'editor.autoLanguageServer': ('editor',True,'Conectar servidor del lenguaje en proyectos de confianza','Connect language server in trusted projects','bool'),
 'editor.completion': ('editor',True,'Autocompletado de código','Code completion','bool'),
 'editor.prediction': ('editor',True,'Predicción local en línea','Local inline prediction','bool'),
 'editor.diagnostics': ('editor',True,'Subrayar diagnósticos','Underline diagnostics','bool'),
 'lantern.lens': ('editor',True,'Lantern Lens: valores junto al código','Lantern Lens: inline values','bool'),
 'lantern.autoSave': ('editor',False,'Compatibilidad: autoguardado Lantern antiguo (sin efecto)','Legacy Lantern autosave (unused)','bool'),
 'editor.fontSize': ('editor',14,'Tamaño de letra','Font size',[11,28]),
 'editor.fontFamily': ('editor','Consolas, "Cascadia Code", "Liberation Mono", monospace','Fuente del editor','Editor font','font'),
 'editor.lineHeight': ('editor',1.45,'Interlineado','Line height',[1.15,2.0]),
 'editor.tabSize': ('editor',4,'Espacios por tabulación','Tab size',[2,4,8]),
 'editor.insertSpaces': ('editor',True,'Insertar espacios','Insert spaces','bool'),
 'editor.minimap': ('editor',True,'Minimapa','Minimap','bool'),
 'editor.lineNumbers': ('editor',True,'Números de línea','Line numbers','bool'),
 'editor.wordWrap': ('editor',False,'Ajuste de línea · Monaco','Word wrap · Monaco','bool','monaco'),
 'editor.fontLigatures': ('editor',False,'Ligaduras tipográficas · Monaco','Font ligatures · Monaco','bool','monaco'),
 'editor.bracketColors': ('editor',True,'Colores de parejas de corchetes · Monaco','Bracket pair colors · Monaco','bool','monaco'),
 'editor.renderWhitespace': ('editor','selection','Espacios visibles · Monaco','Render whitespace · Monaco',['none','selection','all'],'monaco'),
 'editor.cursorBlinking': ('editor','smooth','Cursor · Monaco','Cursor · Monaco',['blink','smooth','solid'],'monaco'),
 'editor.smoothScrolling': ('editor',True,'Desplazamiento suave · Monaco','Smooth scrolling · Monaco','bool','monaco'),
 'files.autoSave': ('files',False,'Autoguardado del archivo activo','Active file autosave','bool'),
 'files.saveNotifications': ('files',False,'Notificación al guardar manualmente','Notify on manual save','bool'),
 'files.autoSaveDelay': ('files',1800,'Espera de autoguardado (ms)','Autosave delay (ms)',[600,600000]),
 'files.trimTrailingWhitespace': ('files',False,'Quitar espacios finales al guardar','Trim trailing whitespace on save','bool'),
 'files.insertFinalNewline': ('files',False,'Insertar salto final al guardar','Insert final newline on save','bool'),
 'terminal.fontSize': ('terminal',13,'Tamaño de letra de terminal','Terminal font size',[10,24]),
 'terminal.cursorBlink': ('terminal',True,'Cursor intermitente','Blinking cursor','bool'),
 'terminal.scrollback': ('terminal',5000,'Líneas de historial · xterm','Scrollback lines · xterm',[500,30000]),
 'terminal.defaultProfile': ('terminal','','Perfil predeterminado (ID detectado)','Default profile (detected ID)','string'),
 'terminal.confirmClose': ('terminal',True,'Confirmar al cerrar una terminal activa','Confirm closing a running terminal','bool'),
 'extensions.network': ('extensions',True,'Permitir búsqueda en Open VSX','Allow Open VSX search','bool'),
 'extensions.loadContributions': ('extensions',True,'Cargar aportaciones compatibles','Load compatible contributions','bool'),
 'extensions.checkUpdatesOnOpen': ('extensions',False,'Consultar actualizaciones al abrir Extensiones','Check updates when Extensions opens','bool'),
 'security.cloudAI': ('security',False,'Permitir envíos a proveedores de IA en la nube','Allow requests to cloud AI providers','bool'),
 'security.terminals': ('security',True,'Permitir terminales tras confirmar confianza','Allow terminals after workspace trust','bool'),
 'security.audit': ('security',True,'Registro local de operaciones sensibles','Local sensitive-operation audit','bool'),
 'ai.provider': ('ai','codex','Proveedor predeterminado','Default provider',['codex','claude-code','gemini-cli','copilot','openai','anthropic','gemini','ollama','emma']),
 'ai.melodyProvider': ('ai','codex','Último proveedor de Melody','Last Melody provider',['codex','claude-code','gemini-cli','copilot','openai','anthropic','gemini','ollama']),
 'ai.melodyModel': ('ai','','Último modelo de Melody','Last Melody model','string'),
 'ai.model': ('ai','','Identificador exacto del modelo','Exact model identifier','string'),
 'ai.context': ('ai','selection','Contexto propuesto','Proposed context',['none','selection','file']),
 'ai.maxOutputTokens': ('ai',4096,'Límite de salida en tokens','Output token limit',[256,32768]),
 'ai.timeout': ('ai',120,'Tiempo máximo de respuesta (s)','Response timeout (s)',[15,300]),
 'ai.emmaDirectory': ('ai','','Carpeta de Emma · motor local','Emma folder · local engine','string'),
 'ai.ollamaBase': ('ai','http://127.0.0.1:11434','Servidor Ollama local','Local Ollama server','localurl'),
 'hardware.enabled': ('hardware',False,'Métricas locales de CPU y memoria','Local CPU and memory metrics','bool'),
 'hardware.interval': ('hardware',2500,'Intervalo de muestreo (ms)','Sampling interval (ms)',[1000,10000]),
 'hardware.gpu': ('hardware',False,'Consultar GPU NVIDIA mediante nvidia-smi','Query NVIDIA GPU using nvidia-smi','bool'),
}


def validate(key, value):
    if key not in SCHEMA: raise ValueError('Ajuste desconocido: ' + str(key))
    rule = SCHEMA[key][4]
    if rule == 'bool':
        if type(value) is not bool: raise ValueError('Se requiere un booleano: ' + key)
    elif isinstance(rule, list):
        if len(rule) == 2 and all(type(x) in (int,float) for x in rule):
            if type(value) not in (int,float) or not rule[0] <= value <= rule[1]: raise ValueError('Valor fuera de rango: ' + key)
        elif value not in rule: raise ValueError('Opción no permitida: ' + key)
    elif rule in ('string','font','localurl'):
        if not isinstance(value,str) or len(value)>400 or any(ord(c)<32 for c in value): raise ValueError('Texto no válido: ' + key)
        if rule == 'font' and (not value or not re.fullmatch(r'[\w\s,"\-]+',value)): raise ValueError('Familia tipográfica no válida.')
        if rule == 'localurl':
            from .ai import LocalAssistant
            value = LocalAssistant.validate_url(value)
    return value


class Preferences:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory is not None else user_data_dir()
        self.directory.mkdir(parents=True, exist_ok=True)
        try: os.chmod(self.directory,0o700)
        except OSError: pass
        self.path=self.directory/'settings.json'; self.lock=threading.RLock()
        self.values={k:copy.deepcopy(v[1]) for k,v in SCHEMA.items()}
        if self.path.is_file():
            try:
                data=json.loads(self.path.read_text(encoding='utf-8'))
                for k,v in data.get('settings',{}).items():
                    try: self.values[k]=validate(k,v)
                    except (ValueError,TypeError): pass
            except (OSError,ValueError,AttributeError): pass
    def get(self,key):
        with self.lock: return self.values[key]
    def export(self):
        with self.lock: return {'version':1,'settings':copy.deepcopy(self.values)}
    def describe(self):
        return {**self.export(),'schema':[{'key':k,'category':v[0],'default':v[1],'label':{'es':v[2],'en':v[3]},'rule':v[4],'requires':v[5] if len(v)>5 else None} for k,v in SCHEMA.items() if k!='lantern.autoSave']}
    def update(self,changes,reset=False):
        if not isinstance(changes,dict) or len(changes)>100: raise ValueError('Objeto de ajustes no válido.')
        validated={k:validate(k,v) for k,v in changes.items()}
        with self.lock:
            candidate={k:copy.deepcopy(v[1]) for k,v in SCHEMA.items()} if reset else dict(self.values)
            candidate.update(validated)
            atomic_json(self.path,{'version':1,'settings':candidate})
            self.values=candidate
        return self.export()
    def audit(self,operation,**fields):
        if not self.get('security.audit'): return
        import time
        # No file contents, API keys, prompts or command text in this log.
        safe={k:str(v)[:180] for k,v in fields.items() if k in ('provider','extension','profile','action','status','id')}
        with self.lock:
            path=self.directory/'audit.jsonl'
            if path.exists() and path.stat().st_size>1_000_000: os.replace(path,self.directory/'audit.previous.jsonl')
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
            with os.fdopen(fd,'a',encoding='utf-8') as f:
                f.write(json.dumps({'time':time.time(),'operation':operation,**safe})+'\n')
