"""HTTP fallback and real isolated extension editing contracts."""
import io,json,tempfile,unittest,urllib.error,zipfile
from pathlib import Path
from unittest.mock import patch,MagicMock
from backend.extensions import download,registry_metadata
from backend.server import Application
ROOT=Path(__file__).resolve().parents[1]

class RegistryFallback(unittest.TestCase):
 def test_real_download_keeps_404_for_universal_resolution(self):
  response=MagicMock();response.__enter__.return_value=response;response.headers={};response.geturl.return_value='https://open-vsx.org/api/sample/name/universal/latest';response.read.return_value=b'{"targetPlatform":"universal"}'
  opener=MagicMock();opener.open.side_effect=[urllib.error.HTTPError('https://open-vsx.org/a',404,'Not Found',{},None),response]
  with patch('backend.extensions.urllib.request.build_opener',return_value=opener),patch('backend.extensions.target_platform',return_value='win32-x64'):
   self.assertEqual(registry_metadata(['sample','name'],'latest')['targetPlatform'],'universal')
  self.assertEqual(len(opener.open.call_args_list),2)
 def test_transient_retry_is_bounded_and_recovers(self):
  response=MagicMock();response.__enter__.return_value=response;response.headers={};response.geturl.return_value='https://open-vsx.org/api/test';response.read.return_value=b'{}'
  opener=MagicMock();opener.open.side_effect=[urllib.error.HTTPError('https://open-vsx.org/a',503,'Busy',{},None),response]
  with patch('backend.extensions.urllib.request.build_opener',return_value=opener),patch('backend.extensions.time.sleep'):
   self.assertEqual(download('https://open-vsx.org/api/test'),b'{}')
  opener.open.side_effect=TimeoutError('offline')
  with patch('backend.extensions.urllib.request.build_opener',return_value=opener),patch('backend.extensions.time.sleep'):
   with self.assertRaisesRegex(ValueError,'tres intentos'):download('https://open-vsx.org/api/test')
  self.assertEqual(opener.open.call_count,5)
 def test_permanent_http_error_does_not_retry_or_claim_offline(self):
  opener=MagicMock();opener.open.side_effect=urllib.error.HTTPError('https://open-vsx.org/a',403,'Forbidden',{},None)
  with patch('backend.extensions.urllib.request.build_opener',return_value=opener):
   with self.assertRaisesRegex(ValueError,'HTTP 403'):download('https://open-vsx.org/api/test')
  self.assertEqual(opener.open.call_count,1)

PLUGIN="""
const v=require('vscode');exports.activate=()=>{
 const telemetry=v.env.createTelemetryLogger({sendEventData(){throw Error('Telemetry must stay disabled');},sendErrorData(){throw Error('Telemetry must stay disabled');}});telemetry.logUsage('test');telemetry.logError(Error('test'));
 v.commands.registerCommand('qa.telemetry',()=>({usage:telemetry.isUsageEnabled,errors:telemetry.isErrorsEnabled}));
 v.commands.registerCommand('qa.relativePattern',async()=>{const files=await v.workspace.findFiles(new v.RelativePattern(v.workspace.workspaceFolders[0],'**/*.py'));return files.map(uri=>v.workspace.asRelativePath(uri));});
 const decorations=new v.EventEmitter();let decorated=true;
 const registration=v.window.registerFileDecorationProvider({onDidChangeFileDecorations:decorations.event,provideFileDecoration(uri){return decorated&&uri.fsPath.endsWith('main.py')?new v.FileDecoration('M','Cambios de la extensión',new v.ThemeColor('gitDecoration.modifiedResourceForeground')):undefined;}});
 v.commands.registerCommand('qa.decorations.clear',()=>{decorated=false;decorations.fire();});
 v.commands.registerCommand('qa.decorations.dispose',()=>registration.dispose());
 v.languages.registerCodeActionsProvider('python',{
  provideCodeActions(doc,r,context){if(!(r instanceof v.Range))throw Error('Missing range');const a=new v.CodeAction('Corregir con extensión',v.CodeActionKind.QuickFix.append('lumen'));a.isPreferred=true;return [a];},
  resolveCodeAction(a){const edit=new v.WorkspaceEdit();edit.insert(v.window.activeTextEditor.document.uri,new v.Position(0,0),'# corrección ñ\\n');edit.insert(v.Uri.joinPath(v.workspace.workspaceFolders[0].uri,'other.py'),new v.Position(0,0),'# segundo archivo\\n');a.edit=edit;return a;}
 });
 v.languages.registerOnTypeFormattingEditProvider('python',{provideOnTypeFormattingEdits(doc,p,ch,opts){if(ch!==';'||opts.tabSize!==2)throw Error('Incorrect formatting arguments');return [v.TextEdit.replace(new v.Range(0,0,0,1),'X')];}},';');
 v.languages.registerDocumentRangeFormattingEditProvider('python',{provideDocumentRangeFormattingEdits(doc,r,o){return [v.TextEdit.replace(r,doc.getText(r).toUpperCase())];}});
 v.languages.registerDocumentHighlightProvider('python',{provideDocumentHighlights(doc,p){return [new v.DocumentHighlight(new v.Range(0,0,0,1),v.DocumentHighlightKind.Read)];}});
 v.languages.registerSelectionRangeProvider('python',{provideSelectionRanges(doc,ps){return ps.map(p=>new v.SelectionRange(new v.Range(0,0,0,1),new v.SelectionRange(new v.Range(0,0,1,0))));}});
 v.languages.registerColorProvider('python',{provideDocumentColors(){return [new v.ColorInformation(new v.Range(0,0,0,1),new v.Color(1,0,0,1))];},provideColorPresentations(color,context){const p=new v.ColorPresentation('rojo');p.textEdit=v.TextEdit.replace(context.range,'#ff0000');return [p];}});
};
"""
class ExtensionEditing(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name);ws=root/'workspace';ws.mkdir();(ws/'main.py').write_text('x=1\n');(ws/'other.py').write_text('y=2\n')
  self.app=Application(ROOT,ws,data_dir=root/'profile');self.app.workspace.trusted=True;raw=io.BytesIO()
  with zipfile.ZipFile(raw,'w') as z:
   z.writestr('extension/package.json',json.dumps({'publisher':'lumen','name':'r9-editing','version':'1.0.0','main':'main.cjs'}));z.writestr('extension/main.cjs',PLUGIN)
  store=self.app.features.extensions;store.install(store.inspect_bytes(raw.getvalue())['ticket'],True);self.runtime=self.app.features.extension_runtime;self.runtime.start(self.app.workspace,'lumen.r9-editing',True)
 def tearDown(self):self.app.features.shutdown();self.app.runner.shutdown();self.tmp.cleanup()
 def call(self,**params):return self.runtime.request(self.app.workspace,{'id':'lumen.r9-editing','document':{'path':'main.py','text':'x=1\n','language':'python'},**params})
 def test_actions_resolve_real_workspace_edit_and_reject_stale_buffer(self):
  action=self.call(method='provide',kind='actions',range={'start':{'line':0,'character':0},'end':{'line':0,'character':1}})['items'][0]
  self.assertEqual(action['kind'],'quickfix.lumen');self.assertNotIn('edit',action)
  result=self.call(method='resolveAction',action=action['_lumenAction'])['action'];self.assertEqual(len(result['edit']['changes']),2)
  with self.assertRaisesRegex(ValueError,'archivo cambió'):self.call(method='resolveAction',action=action['_lumenAction'],document={'path':'main.py','text':'new','language':'python'})
  self.assertEqual((self.app.workspace.root/'main.py').read_text(),'x=1\n')
 def test_formatter_receives_typed_character_range_and_editor_options(self):
  edits=self.call(method='provide',kind='onTypeFormat',position={'line':0,'character':1},character=';',options={'tabSize':2,'insertSpaces':True})['items'];self.assertEqual(edits[0]['newText'],'X')
  edits=self.call(method='provide',kind='rangeFormat',range={'start':{'line':0,'character':0},'end':{'line':0,'character':1}})['items'];self.assertEqual(edits[0]['newText'],'X')
 def test_colors_selection_and_highlights_are_serialized(self):
  self.assertEqual(self.call(method='provide',kind='highlights',position={'line':0,'character':0})['items'][0]['kind'],1)
  self.assertEqual(len(self.call(method='provide',kind='selection',positions=[{'line':0,'character':0}])['items']),1)
  self.assertEqual(self.call(method='provide',kind='colors')['items'][0]['color']['red'],1)
  presentation=self.call(method='provide',kind='colorPresentation',color={'red':1,'green':0,'blue':0,'alpha':1},range={'start':{'line':0,'character':0},'end':{'line':0,'character':1}})['items'][0];self.assertEqual(presentation['textEdit']['newText'],'#ff0000')
 def test_file_decorations_refresh_and_validate_project_paths(self):
  result=self.call(method='decorations',paths=['main.py','other.py']);self.assertEqual(result['items'][0]['decoration']['badge'],'M')
  self.assertTrue(self.call(method='decorations',paths=['main.py','other.py'],revision=result['revision'])['unchanged'])
  self.call(method='command',command='qa.decorations.clear');updated=self.call(method='decorations',paths=['main.py'],revision=result['revision']);self.assertEqual(updated['items'],[])
  self.call(method='command',command='qa.decorations.dispose');self.assertGreater(self.call(method='decorations',paths=['main.py'])['revision'],updated['revision'])
  with self.assertRaises((ValueError,PermissionError)):self.call(method='decorations',paths=['../outside.py'])
 def test_extension_telemetry_remains_disabled(self):
  self.assertEqual(self.call(method='command',command='qa.telemetry')['result'],{'usage':False,'errors':False})
 def test_relative_pattern_accepts_a_workspace_folder(self):
  self.assertEqual(set(self.call(method='command',command='qa.relativePattern')['result']),{'main.py','other.py'})
if __name__=='__main__':unittest.main()
