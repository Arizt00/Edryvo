"""Real extension RPC, PTYs, tasks, resource edits, webviews and debugger transport."""
import io,json,os,sys,tempfile,time,unittest,zipfile
from pathlib import Path
from backend.server import Application
from backend.extension_services import text_edit
ROOT=Path(__file__).resolve().parents[1]
PLUGIN=r"""
const v=require('vscode');const closed=[];
exports.activate=()=>{
 v.commands.registerCommand('qa.shell',()=>v.env.shell);
 v.window.onDidCloseTerminal(t=>closed.push({name:t.name,code:t.exitStatus?.code}));
 v.commands.registerCommand('qa.terminal',async()=>{const t=v.window.createTerminal({name:'Extensión ñ',shellPath:process.execPath,shellArgs:['-e','console.log("terminal ñ");setTimeout(()=>{},300)']});await t.processId;t.show();return {id:t._id,pid:await t.processId};});
 v.commands.registerCommand('qa.closed',()=>closed);
 v.commands.registerCommand('qa.task',async()=>{let resolve;const result=new Promise(r=>resolve=r);const d=v.tasks.onDidEndTaskProcess(e=>{d.dispose();resolve(e.exitCode);});const task=new v.Task({type:'qa'},v.TaskScope.Workspace,'Proceso real','QA',new v.ProcessExecution(process.execPath,['-e','console.log("tarea ñ")']));await v.tasks.executeTask(task);return await result;});
 v.tasks.registerTaskProvider('qa',{provideTasks:()=>[new v.Task({type:'qa'},v.TaskScope.Workspace,'Listado','QA',new v.ProcessExecution(process.execPath,['-e','console.log("listado")']))]});
 v.commands.registerCommand('qa.fetch',async()=>(await v.tasks.fetchTasks({type:'qa'})).map(x=>x.name));
 v.commands.registerCommand('qa.workspaceTasks',async()=>(await v.tasks.fetchTasks({type:'process'})).map(x=>({name:x.name,process:x.execution.process,args:x.execution.args})));
 v.commands.registerCommand('qa.pickTask',async()=>{const result=await v.commands.executeCommand('workbench.action.tasks.runTask');return !!result;});
 v.commands.registerCommand('qa.editorEdit',async()=>{const editor=v.window.activeTextEditor;const result=await editor.edit(b=>b.insert(new v.Position(0,0),'# edit ñ\n'));const document=await v.workspace.openTextDocument(editor.document.uri);return {result,text:document.getText()};});
 v.commands.registerCommand('qa.edit',async()=>{const edit=new v.WorkspaceEdit(),root=v.workspace.workspaceFolders[0].uri;edit.createFile(v.Uri.joinPath(root,'created.py'));edit.insert(v.Uri.joinPath(root,'created.py'),new v.Position(0,0),'print("nuevo ñ")\n');edit.renameFile(v.Uri.joinPath(root,'main.py'),v.Uri.joinPath(root,'renamed.py'));edit.deleteFile(v.Uri.joinPath(root,'delete.py'));return v.workspace.applyEdit(edit);});
 v.commands.registerCommand('qa.webview',()=>{const p=v.window.createWebviewPanel('qa','Panel real ñ',v.ViewColumn.One,{enableScripts:true,localResourceRoots:[v.workspace.workspaceFolders[0].uri]});p.webview.onDidReceiveMessage(async m=>{await p.webview.postMessage({answer:m.value+1});});p.webview.html='<button id="send" onclick="api.postMessage({value:41})">Enviar ñ</button><output id="answer"></output><script>const api=acquireVsCodeApi();window.addEventListener("message",e=>document.querySelector("output").textContent=e.data.answer);</script>';return p._id;});
 v.debug.registerDebugAdapterDescriptorFactory('qa-debugpy',{createDebugAdapterDescriptor:()=>new v.DebugAdapterExecutable(process.env.QA_PYTHON,['-m','debugpy.adapter'])});
 v.commands.registerCommand('qa.debug',async()=>v.debug.startDebugging(undefined,{type:'qa-debugpy',name:'Python real',request:'launch',program:v.Uri.joinPath(v.workspace.workspaceFolders[0].uri,'debug.py').fsPath,console:'internalConsole',stopOnEntry:true}));
};
"""

class ExtensionServicesTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name);self.ws=root/'workspace';self.ws.mkdir();self.outside=root/'outside.py';self.outside.write_text('outside\n')
  for name,text in {'main.py':'x=1\n','delete.py':'delete\n','debug.py':'value=41\nprint(value+1)\n'}.items():(self.ws/name).write_text(text,encoding='utf-8')
  self.app=Application(ROOT,self.ws,data_dir=root/'profile');self.app.workspace.trusted=True;self.runtime=self.app.features.extension_runtime;raw=io.BytesIO()
  with zipfile.ZipFile(raw,'w') as z:
   z.writestr('extension/package.json',json.dumps({'publisher':'qa','name':'services-053','version':'1.0.0','main':'main.cjs'}));z.writestr('extension/main.cjs',PLUGIN)
  store=self.app.features.extensions;store.install(store.inspect_bytes(raw.getvalue())['ticket'],True)
  self.previous=os.environ.get('QA_PYTHON');os.environ['QA_PYTHON']=sys.executable
  self.runtime.start(self.app.workspace,'qa.services-053',True)
 def tearDown(self):
  self.app.features.shutdown();self.app.runner.shutdown();self.tmp.cleanup()
  if self.previous is None:os.environ.pop('QA_PYTHON',None)
  else:os.environ['QA_PYTHON']=self.previous
 def call(self,name):return self.runtime.request(self.app.workspace,{'id':'qa.services-053','method':'command','command':name})['result']
 def wait(self,fn):
  end=time.monotonic()+12
  while time.monotonic()<end:
   result=fn()
   if result:return result
   time.sleep(.1)
  self.fail('No llegó el resultado real del servicio.')
 def test_terminal_close_is_emitted_by_real_process(self):
  info=self.call('qa.terminal');self.assertGreater(info['pid'],0)
  result=self.wait(lambda:self.call('qa.closed'));self.assertEqual(result[0]['name'],'Extensión ñ')
  terminal=next(iter(self.app.features.terminals.sessions.values()));self.assertIn('terminal ñ',terminal.read()['data'])
 def test_shell_is_the_executable_used_by_default_extension_terminal(self):
   from backend.terminals import terminal_profiles
   profiles=terminal_profiles();self.assertTrue(profiles)
   shell=self.call('qa.shell');self.assertEqual(shell,profiles[0]['argv'][0]);self.assertTrue(Path(shell).is_file())
 def test_real_process_task_exits_and_provider_fetches(self):
  self.assertEqual(self.call('qa.fetch'),['Listado']);self.assertEqual(self.call('qa.task'),0)
  self.assertTrue(any('tarea ñ' in t.read()['data'] for t in self.app.features.terminals.sessions.values()))
 def test_workspace_task_jsonc_comments_after_trailing_commas_preserve_strings(self):
  (self.ws/'.vscode').mkdir();(self.ws/'.vscode/tasks.json').write_text(r'''{
   // User task
   "tasks": [{"label":"Comentada ñ","type":"process","command":"node","args":["https://example.test/a/*b*/", "x,}", /* last argument */ ], /* last property */ }, // last task
   ], /* last root property */
  }''',encoding='utf-8')
  tasks=self.call('qa.workspaceTasks');self.assertEqual(tasks,[{'name':'Comentada ñ','process':'node','args':['https://example.test/a/*b*/','x,}']}])
 def test_editor_edit_uses_dirty_document_and_keeps_disk_unchanged(self):
  self.app.features.buffers.update(self.app.workspace,{'path':'main.py','text':'x=2\n','saved':False})
  result=self.runtime.request(self.app.workspace,{'id':'qa.services-053','method':'command','command':'qa.editorEdit','document':{'path':'main.py','text':'x=2\n','language':'python'}})['result']
  self.assertEqual(result,{'result':True,'text':'# edit ñ\nx=2\n'});self.assertEqual((self.ws/'main.py').read_text(),'x=1\n');self.assertEqual(self.app.features.buffers.items['main.py']['text'],'# edit ñ\nx=2\n')
 def test_workspace_edit_creates_renames_deletes_and_keeps_text_unsaved(self):
  self.assertTrue(self.call('qa.edit'));self.assertFalse((self.ws/'main.py').exists());self.assertTrue((self.ws/'renamed.py').exists());self.assertFalse((self.ws/'delete.py').exists())
  self.assertEqual((self.ws/'created.py').read_text(),'');buffer=self.app.features.buffers.items['created.py'];self.assertEqual(buffer['text'],'print("nuevo ñ")\n');self.assertFalse(buffer['saved'])
 def test_external_file_edits_and_rollback_on_invalid_later_operation(self):
  services=self.app.features.extension_services
  def edit(uri,new):return {'kind':'text','uri':str(uri),'edits':[{'range':{'start':{'line':0,'character':0},'end':{'line':0,'character':0}},'newText':new}]}
  result=services.workspace_edit(self.app.workspace,{'operations':[edit(self.outside,'# ñ\n')]});self.assertTrue(result['applied']);self.assertEqual(self.outside.read_text(),'outside\n');self.assertIn(str(self.outside),self.app.features.buffers.items)
  with self.assertRaises(ValueError):services.workspace_edit(self.app.workspace,{'operations':[{'kind':'rename','oldUri':str(self.ws/'main.py'),'newUri':str(self.ws/'renamed.py')},{'kind':'text','uri':str(self.ws/'renamed.py'),'edits':[{'range':{'start':{'line':99,'character':0},'end':{'line':99,'character':0}},'newText':'x'}]}]})
  self.assertTrue((self.ws/'main.py').is_file());self.assertFalse((self.ws/'renamed.py').exists())
 def test_directory_rename_preserves_dirty_descendant_buffers(self):
  folder=self.ws/'source';folder.mkdir();(folder/'main.py').write_text('disk\n');self.app.features.buffers.update(self.app.workspace,{'path':'source/main.py','text':'dirty ñ\n','saved':False})
  self.app.features.extension_services.workspace_edit(self.app.workspace,{'operations':[{'kind':'rename','oldUri':str(folder),'newUri':str(self.ws/'target')}]})
  self.assertNotIn('source/main.py',self.app.features.buffers.items);buffer=self.app.features.buffers.items['target/main.py'];self.assertEqual(buffer['text'],'dirty ñ\n');self.assertFalse(buffer['saved']);self.assertEqual((self.ws/'target/main.py').read_text(),'disk\n')
 def test_external_save_preserves_bom_newlines_and_rejects_disk_conflict(self):
  from backend.workspace import ConflictError
  self.outside.write_bytes(b'\xef\xbb\xbfprint("\xc3\xb1")\r\n');features=self.app.features
  item=features.get('/extensions/file',{'path':[str(self.outside)]});self.assertTrue(item['external']);self.assertTrue(item['bom']);self.assertEqual(item['newline'],'CRLF')
  saved=features.post('/extensions/save',{'path':str(self.outside),'content':item['content']+'# á\n','revision':item['revision'],'newline':item['newline'],'bom':item['bom']})
  expected=b'\xef\xbb\xbfprint("\xc3\xb1")\r\n# \xc3\xa1\r\n';self.assertEqual(self.outside.read_bytes(),expected);self.assertTrue(saved['saved'])
  self.outside.write_bytes(b'external change\n')
  with self.assertRaises(ConflictError):features.post('/extensions/save',{'path':str(self.outside),'content':'overwrite','revision':saved['revision']})
  self.assertEqual(self.outside.read_bytes(),b'external change\n')
 def test_manifest_localizes_nested_contributions_with_language_fallback(self):
  from backend.extensions import localized_manifest
  folder=Path(self.tmp.name)/'localized';folder.mkdir()
  manifest={'name':'localized','contributes':{'commands':[{'command':'qa.test','title':'%title%','category':'%category%'}],'configuration':{'properties':{'qa.url':{'default':'https://example.test/%path%','description':'%description%'}}}}}
  (folder/'package.json').write_text(json.dumps(manifest));(folder/'package.nls.json').write_text(json.dumps({'title':'Execute','category':'Tools','description':'Description'}));(folder/'package.nls.es.json').write_text(json.dumps({'title':'Ejecutar ñ','description':'Descripción'}))
  result=localized_manifest(folder,'es-ES');self.assertEqual(result['contributes']['commands'][0],{'command':'qa.test','title':'Ejecutar ñ','category':'Tools'});self.assertEqual(result['contributes']['configuration']['properties']['qa.url']['description'],'Descripción');self.assertEqual(result['contributes']['configuration']['properties']['qa.url']['default'],'https://example.test/%path%')
 def test_utf16_positions_and_overlap_detection(self):
  self.assertEqual(text_edit('😀ñ\r\nx',[{'range':{'start':{'line':0,'character':2},'end':{'line':0,'character':3}},'newText':'á'}]),'😀á\r\nx')
  with self.assertRaises(ValueError):text_edit('😀ñ',[{'range':{'start':{'line':0,'character':1},'end':{'line':0,'character':2}},'newText':'x'}])
 def test_webview_messages_and_local_resource_roots(self):
  ident=self.call('qa.webview');runtime=self.app.features.extension_runtime;runtime.request(self.app.workspace,{'id':'qa.services-053','method':'webviewMessage','panel':ident,'message':{'value':41}})
  self.wait(lambda:self.app.features.extension_services.panels[ident]['messages']);panel=self.app.features.extension_services.snapshot()['panels'][0];self.assertEqual(panel['messages'][0]['message'],{'answer':42})
  self.assertTrue(self.app.features.extension_services.resource(ident,str(self.ws/'main.py'))['data'])
  with self.assertRaises(PermissionError):self.app.features.extension_services.resource(ident,str(self.outside))
 def test_extension_debugger_launches_real_debugpy_and_stops(self):
  import importlib.util
  if not importlib.util.find_spec('debugpy'):self.skipTest('debugpy no instalado en este Python de pruebas')
  self.assertTrue(self.call('qa.debug'));self.wait(lambda:self.app.features.debugger.snapshot()['status']=='paused');self.app.features.debugger.command('continue');self.wait(lambda:'42' in self.app.features.debugger.snapshot()['output']);self.app.features.debugger.stop()

if __name__=='__main__':unittest.main()
