"""Real save RPC and safe package icon handling for Zénit R2."""
import base64,hashlib,io,json,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from backend.server import Application
from backend.extensions import image_data,package_icon
ROOT=Path(__file__).resolve().parents[1]
PLUGIN=r'''
const v=require('vscode');let saves=0;
exports.activate=()=>{
 v.workspace.onDidSaveTextDocument(()=>saves++);
 v.workspace.onWillSaveTextDocument(e=>{if(e.document.getText().includes('FORMAT'))e.waitUntil(Promise.resolve([v.TextEdit.replace(new v.Range(0,0,0,6),'format')]));});
 v.commands.registerCommand('qa.save',async()=>({saved:await v.window.activeTextEditor.document.save(),events:saves}));
 v.commands.registerCommand('qa.all',async()=>({saved:await v.workspace.saveAll(),events:saves}));
};
'''

class ExtensionSaveTest(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();base=Path(self.temp.name);self.ws=base/'project';self.ws.mkdir();self.file=self.ws/'main.py';self.file.write_bytes(b'\xef\xbb\xbfDISK\r\n')
  self.app=Application(ROOT,self.ws,data_dir=base/'profile');self.app.workspace.trusted=True;self.runtime=self.app.features.extension_runtime
  raw=io.BytesIO()
  with zipfile.ZipFile(raw,'w') as z:
   z.writestr('extension/package.json',json.dumps({'publisher':'qa','name':'zenit-save','version':'1.0.0','main':'main.cjs'}));z.writestr('extension/main.cjs',PLUGIN)
  store=self.app.features.extensions;store.install(store.inspect_bytes(raw.getvalue())['ticket'],True);self.runtime.start(self.app.workspace,'qa.zenit-save',True)
 def tearDown(self):self.app.features.shutdown();self.app.runner.shutdown();self.temp.cleanup()
 def call(self,text,command='qa.save'):
  return self.runtime.request(self.app.workspace,{'id':'qa.zenit-save','method':'command','command':command,'document':{'path':'main.py','text':text,'dirty':True,'language':'python'}})['result']
 def test_document_save_runs_wait_until_preserves_encoding_and_emits_real_event(self):
  self.app.features.buffers.update(self.app.workspace,{'path':'main.py','text':'FORMAT ñ\n','sequence':0,'revision':hashlib.sha256(self.file.read_bytes()).hexdigest()})
  result=self.call('FORMAT ñ\n');self.assertEqual(result,{'saved':True,'events':1});self.assertEqual(self.file.read_bytes(),'\ufeffformat ñ\r\n'.encode('utf-8'))
  self.assertTrue(self.app.features.buffers.snapshot()['buffers'][0]['saved'])
 def test_disk_conflict_is_false_and_preserves_external_file_and_unsaved_buffer(self):
  self.call('first\n');self.file.write_text('external\n',encoding='utf-8');result=self.call('second\n')
  self.assertFalse(result['saved']);self.assertEqual(self.file.read_text(),'external\n');self.assertEqual(result['events'],1)
 def test_shared_buffer_conflict_is_false(self):
  self.app.features.buffers.update(self.app.workspace,{'path':'main.py','text':'OTHER WINDOW','sequence':0})
  result=self.call('local\n');self.assertFalse(result['saved']);self.assertEqual(self.file.read_bytes(),b'\xef\xbb\xbfDISK\r\n');self.assertEqual(result['events'],0)
 def test_save_all_returns_real_success(self):
  self.assertEqual(self.call('all ñ\n','qa.all'),{'saved':True,'events':1});self.assertIn('all ñ',self.file.read_text(encoding='utf-8-sig'))
 def test_extension_can_save_again_after_a_manual_editor_save(self):
  self.assertTrue(self.call('first\n')['saved']);self.file.write_bytes('manual ñ\r\n'.encode('utf-8-sig'))
  saved=self.app.features.buffers.snapshot()['buffers'][0]
  self.app.features.buffers.update(self.app.workspace,{'path':'main.py','text':'manual ñ\n','saved':True,'sequence':saved['sequence'],'revision':hashlib.sha256(self.file.read_bytes()).hexdigest()})
  self.runtime.request(self.app.workspace,{'id':'qa.zenit-save','method':'didSave','document':{'path':'main.py','text':'manual ñ\n','dirty':False,'language':'python'}})
  self.assertTrue(self.call('extension after manual\n')['saved']);self.assertIn('extension after manual',self.file.read_text(encoding='utf-8-sig'))

class IconTest(unittest.TestCase):
 def test_local_icon_is_package_scoped_and_has_a_safe_data_uri(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'icon.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0h2v2"/></svg>')
   self.assertTrue(package_icon(root,{'icon':'icon.svg'}).startswith('data:image/svg+xml;base64,'));self.assertIsNone(package_icon(root,{'icon':'../icon.svg'}))
 def test_script_and_external_resources_are_rejected(self):
  for svg in [b'<svg><script>alert(1)</script></svg>',b'<svg><image href="https://example.org"/></svg>',b'<svg onload="alert(1)"></svg>']:
   with self.assertRaises(ValueError):image_data(svg)
  with self.assertRaises(ValueError):image_data(b'x'*512_001)

if __name__=='__main__':unittest.main()
