"""Use a shipped language-server binary through Lumen's real LSP client.

This does not claim the extension's VS Code UI/commands are supported.
"""
import os
import threading
from pathlib import Path
from .lsp import LanguageSession


class NativeLanguageHost:
    def __init__(self,workspace,profile,language,engine):
        self.language=language;self.session=LanguageSession(profile,workspace)
        self.process=self.session.process;self.root=workspace.root;self.documents={};self.lock=threading.Lock();self.diagnostics={};self.sequence=0
        caps=self.session.capabilities
        self.methods={'completion':('completionProvider','textDocument/completion'),'hover':('hoverProvider','textDocument/hover'),'definition':('definitionProvider','textDocument/definition'),'references':('referencesProvider','textDocument/references'),'symbols':('documentSymbolProvider','textDocument/documentSymbol'),'inlay':('inlayHintProvider','textDocument/inlayHint'),'format':('documentFormattingProvider','textDocument/formatting'),'semantic':('semanticTokensProvider','textDocument/semanticTokens/full')}
        providers=[{'kind':kind,'language':language,'triggers':caps.get(key,{}).get('triggerCharacters',[]) if isinstance(caps.get(key),dict) else []} for kind,(key,_) in self.methods.items() if key in caps and caps[key] is not False]
        for provider in providers:
            if provider['kind']=='semantic':provider['legend']=caps['semanticTokensProvider']['legend']
        self.capabilities={'commands':[],'providers':providers+[{'kind':'diagnostics','language':language}],'tokens':[],'engine':engine}

    @property
    def logs(self):return self.session.stderr

    def request(self,message):
        with self.lock:
            document=message.get('document',{});path=document.get('path')
            if not path:return {'items':[]}
            uri=(self.root/path).resolve().as_uri();text=document.get('text','');previous=self.documents.get(uri)
            version=1 if previous is None else previous[1]+(previous[0]!=text)
            if previous is None:self.session.notify('textDocument/didOpen',{'textDocument':{'uri':uri,'languageId':document.get('language',self.language),'version':version,'text':text}})
            elif previous[0]!=text:self.session.notify('textDocument/didChange',{'textDocument':{'uri':uri,'version':version},'contentChanges':[{'text':text}]})
            self.documents[uri]=(text,version)
            method=message['method']
            if method=='willSave':return {'edits':[]}
            if method=='didSave':self.session.notify('textDocument/didSave',{'textDocument':{'uri':uri},'text':text});return {'ok':True}
            if method!='provide':raise ValueError('Este adaptador proporciona servicios del lenguaje. Los comandos de la interfaz VS Code no están disponibles.')
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
            if kind=='format':params['options']={'tabSize':4,'insertSpaces':True}
            value=self.session.request(self.methods[kind][1],params)
            items=value if isinstance(value,list) else value.get('items',[value]) if isinstance(value,dict) else []
            if kind=='completion':
                for item in items:
                    item['kind']=max(0,item.get('kind',1)-1);item['insertTextRules']=4 if item.get('insertTextFormat')==2 else 0
            if kind=='symbols':
                def normalize(symbol):
                    symbol['kind']=max(0,symbol.get('kind',1)-1)
                    for child in symbol.get('children',[]):normalize(child)
                for item in items:normalize(item)
            return {'items':items}

    def close(self):self.session.close()


class PyreflyHost(NativeLanguageHost):
    def __init__(self,root,workspace):
        binary=root/'bin'/('pyrefly.exe' if os.name=='nt' else 'pyrefly')
        if not binary.is_file():raise ValueError('Pyrefly instalado no corresponde a este sistema. Reinstala el paquete para descargar la plataforma correcta.')
        if os.name=='nt':
            with binary.open('rb') as stream:
                if stream.read(2)!=b'MZ':raise ValueError('Pyrefly no contiene un ejecutable Windows. Reinstala el paquete.')
        config={'pyrefly':{'typeCheckingMode':'default','diagnosticMode':'openFilesOnly'}}
        super().__init__(workspace,{'argv':[str(binary),'lsp'],'languages':['python'],'initializationOptions':config,'settings':{'python':config}},'python','Pyrefly · LSP nativo')


class JavaLanguageHost(NativeLanguageHost):
    def __init__(self,root,workspace,storage):
        import hashlib,shutil,sys
        from .runtime_paths import find_tool
        launches=sorted((root/'server/plugins').glob('org.eclipse.equinox.launcher_*.jar'))
        java=next(iter(root.glob('jre/*/bin/java.exe' if os.name=='nt' else 'jre/*/bin/java')),None) or find_tool('java')
        if not launches or not java:raise ValueError('La extensión Java necesita su servidor JDT LS y un JDK 21 o posterior. Reinstala el paquete de tu plataforma.')
        name='config_win' if os.name=='nt' else 'config_mac' if sys.platform=='darwin' else 'config_linux'
        config=storage/name
        if not config.exists():shutil.copytree(root/'server'/name,config)
        data=storage/'workspaces'/hashlib.sha256(str(workspace.root).encode()).hexdigest()[:20]
        argv=[str(java),'-Declipse.application=org.eclipse.jdt.ls.core.id1','-Dosgi.bundles.defaultStartLevel=4','-Declipse.product=org.eclipse.jdt.ls.core.product','-Dlog.level=WARNING','-Xmx1G','--add-modules=ALL-SYSTEM','--add-opens','java.base/java.util=ALL-UNNAMED','--add-opens','java.base/java.lang=ALL-UNNAMED','-jar',str(launches[-1]),'-configuration',str(config),'-data',str(data)]
        opts={'settings':{'java':{'import':{'gradle':{'enabled':True},'maven':{'enabled':True}},'autobuild':{'enabled':True},'completion':{'enabled':True}}},'extendedClientCapabilities':{'classFileContentsSupport':False}}
        super().__init__(workspace,{'argv':argv,'initializationOptions':opts,'initializationTimeout':60,'languages':['java']},'java','Java · Eclipse JDT LS nativo')
