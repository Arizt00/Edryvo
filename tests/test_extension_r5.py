"""Exercise VS Code compatibility contracts in the actual isolated Node process."""
import io,json,sys,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.server import Application

class ExtensionAPI(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();base=Path(self.tmp.name);ws=base/'project';ws.mkdir();(ws/'main.js').write_text('let answer = 42;\n')
        self.app=Application(ROOT,ws,data_dir=base/'profile');self.app.workspace.trusted=True
        raw=io.BytesIO()
        code="""
        const v=require('vscode');exports.activate=ctx=>{
          let events=0;ctx.subscriptions.push(v.workspace.onDidChangeConfiguration(e=>{if(e.affectsConfiguration('r5'))events++}));
          v.commands.registerCommand('r5.config',async value=>{await v.workspace.getConfiguration('r5').update('answer',value);return {events,value:v.workspace.getConfiguration('r5').get('answer'),id:v.extensions.getExtension('lumen.api-r5').id};});
          v.commands.registerCommand('r5.persist',()=>v.workspace.getConfiguration('r5').get('answer'));
          v.languages.registerDocumentSemanticTokensProvider('javascript',{provideDocumentSemanticTokens(doc,token){if(!token||typeof token.isCancellationRequested!=='boolean')throw Error('Missing cancellation token');return new v.SemanticTokens(new Uint32Array([0,4,6,0,0]));}},new v.SemanticTokensLegend(['variable'],[]));
          v.languages.registerDefinitionProvider('javascript',{provideDefinition(doc,pos){return new v.Location(doc.uri,new v.Range(0,4,0,10));}});
          v.languages.registerInlayHintsProvider('javascript',{provideInlayHints(doc,range,token){if(!(range instanceof v.Range))throw Error('Missing range');return [new v.InlayHint(new v.Position(0,10),': number',1)];}});
        };
        """
        with zipfile.ZipFile(raw,'w') as z:
            z.writestr('extension/package.json',json.dumps({'publisher':'lumen','name':'api-r5','version':'1','main':'main.cjs','description':'%description%'}));z.writestr('extension/package.nls.json',json.dumps({'description':'Localized language tools'}));z.writestr('extension/main.cjs',code)
        self.store=self.app.features.extensions;r=self.store.inspect_bytes(raw.getvalue());self.store.install(r['ticket'],True)
        self.runtime=self.app.features.extension_runtime;self.runtime.start(self.app.workspace,'lumen.api-r5',True)
    def tearDown(self):self.app.features.shutdown();self.app.runner.shutdown();self.tmp.cleanup()
    def call(self,**params):return self.runtime.request(self.app.workspace,{'id':'lumen.api-r5','document':{'path':'main.js','text':'let answer = 42;\n','language':'javascript'},**params})
    def test_real_configuration_events_extension_registry_and_argument_forwarding(self):
        r=self.call(method='command',command='r5.config',arguments=[42])['result'];self.assertEqual(r,{'events':1,'value':42,'id':'lumen.api-r5'})
        self.runtime.stop('lumen.api-r5');self.runtime.start(self.app.workspace,'lumen.api-r5',True)
        self.assertEqual(self.call(method='command',command='r5.persist')['result'],42)
    def test_provider_contracts_and_typed_token_serialization(self):
        self.assertEqual(self.call(method='provide',kind='semantic')['items'][0]['data'],[0,4,6,0,0])
        loc=self.call(method='provide',kind='definition',position={'line':0,'character':7})['items'][0]
        self.assertTrue(loc['uri']['fsPath'].endswith('main.js'))
        hints=self.call(method='provide',kind='inlay',range={'start':{'line':0,'character':0},'end':{'line':1,'character':0}})['items'];self.assertEqual(hints[0]['label'],': number')
    def test_manifest_localization_is_reflected_in_installed_catalog(self):
        self.assertEqual(self.store.list()[0]['description'],'Localized language tools')
if __name__=='__main__':unittest.main()
