"""Use a shipped language-server binary through Lumen's real LSP client.

This does not claim the extension's VS Code UI/commands are supported.
"""
import os
import threading
from pathlib import Path
from .lsp import LanguageSession


class PyreflyHost:
    def __init__(self,root,workspace):
        binary=root/'bin'/('pyrefly.exe' if os.name=='nt' else 'pyrefly')
        if not binary.is_file():raise ValueError('Pyrefly instalado no corresponde a este sistema. Usa Reinstalar paquete para descargar la plataforma correcta.')
        if os.name=='nt':
            with binary.open('rb') as stream:
                if stream.read(2)!=b'MZ':raise ValueError('Pyrefly no contiene un ejecutable Windows. Reinstala el paquete desde Extensiones.')
        config={'pyrefly':{'typeCheckingMode':'default','diagnosticMode':'openFilesOnly'}}
        self.session=LanguageSession({'argv':[str(binary),'lsp'],'languages':['python'],'initializationOptions':config,'settings':{'python':config}},workspace)
        self.process=self.session.process;self.root=workspace.root;self.documents={};self.lock=threading.Lock();self.diagnostics={};self.sequence=0
        caps=self.session.capabilities
        self.methods={'completion':('completionProvider','textDocument/completion'),'hover':('hoverProvider','textDocument/hover'),'definition':('definitionProvider','textDocument/definition'),'references':('referencesProvider','textDocument/references'),'symbols':('documentSymbolProvider','textDocument/documentSymbol'),'inlay':('inlayHintProvider','textDocument/inlayHint')}
        providers=[{'kind':kind,'language':'python','triggers':caps.get(key,{}).get('triggerCharacters',[]) if isinstance(caps.get(key),dict) else []} for kind,(key,_) in self.methods.items() if key in caps and caps[key] is not False]
        self.capabilities={'commands':[],'providers':providers+[{'kind':'diagnostics','language':'python'}],'tokens':[],'engine':'Pyrefly · LSP nativo'}

    @property
    def logs(self):return self.session.stderr

    def request(self,message):
        with self.lock:
            document=message.get('document',{});path=document.get('path')
            if not path:return {'items':[]}
            uri=(self.root/path).resolve().as_uri();text=document.get('text','');previous=self.documents.get(uri)
            version=1 if previous is None else previous[1]+(previous[0]!=text)
            if previous is None:self.session.notify('textDocument/didOpen',{'textDocument':{'uri':uri,'languageId':document.get('language','python'),'version':version,'text':text}})
            elif previous[0]!=text:self.session.notify('textDocument/didChange',{'textDocument':{'uri':uri,'version':version},'contentChanges':[{'text':text}]})
            self.documents[uri]=(text,version)
            method=message['method']
            if method=='willSave':return {'edits':[]}
            if method=='didSave':self.session.notify('textDocument/didSave',{'textDocument':{'uri':uri},'text':text});return {'ok':True}
            if method!='provide':raise ValueError('Este adaptador proporciona servicios de Python. Los comandos de la interfaz VS Code no están disponibles.')
            kind=message.get('kind')
            if kind=='diagnostics':
                events=self.session.poll(self.sequence);self.sequence=events['sequence']
                for event in events['events']:
                    if event['method']=='textDocument/publishDiagnostics':self.diagnostics[event['params']['uri']]=event['params']
                report=self.diagnostics.get(uri,{})
                if report.get('version') is not None and report['version']!=version:return {'items':[]}
                return {'items':[{'line':d['range']['start']['line']+1,'column':d['range']['start']['character']+1,'endLine':d['range']['end']['line']+1,'endColumn':d['range']['end']['character']+1,'message':d['message'],'severity':{1:'error',2:'warning',3:'info',4:'hint'}.get(d.get('severity',1),'error')} for d in report.get('diagnostics',[])]}
            if kind not in self.methods:return {'items':[]}
            params={'textDocument':{'uri':uri},**{k:message[k] for k in ('position','range') if k in message}}
            if kind=='references':params['context']={'includeDeclaration':True}
            value=self.session.request(self.methods[kind][1],params)
            items=value if isinstance(value,list) else value.get('items',[value]) if isinstance(value,dict) else []
            if kind=='completion':
                for item in items:
                    item['kind']=max(0,item.get('kind',1)-1);item['insertTextRules']=4 if item.get('insertTextFormat')==2 else 0
            return {'items':items}

    def close(self):self.session.close()
