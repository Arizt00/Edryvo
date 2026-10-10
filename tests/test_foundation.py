"""Real CPU execution and dependency activation; no fake SDK success responses."""
import io,json,os,tempfile,unittest,zipfile
from pathlib import Path
from types import SimpleNamespace
from backend.server import Application
from backend.simulation import Simulation,EXAMPLES
from backend.foundation import bundled_tool,tool_environment
from backend.extension_dependencies import dependency_graph
ROOT=Path(__file__).resolve().parents[1]

class FoundationTest(unittest.TestCase):
 def test_five_cpu_architectures_compute_real_registers(self):
  if not bundled_tool('python') or not bundled_tool('clang'):self.skipTest('Requires the prepared SDK')
  registers={'x86':'eax','x86_64':'rax','arm':'r0','arm64':'x0','riscv64':'a0'}
  for arch,source in EXAMPLES.items():
   with self.subTest(architecture=arch):
    result=Simulation(None).run(SimpleNamespace(trusted=True),{'architecture':arch,'source':source,'steps':100})
    self.assertEqual(result['status'],'complete',result);self.assertEqual(result['registers'][registers[arch]],'0xc');self.assertEqual(result['executed'],3)
 def test_step_limit_and_edit_restart(self):
  if not bundled_tool('python'):self.skipTest('Requires the prepared SDK')
  s=Simulation(None);ws=SimpleNamespace(trusted=True)
  first=s.run(ws,{'architecture':'x86_64','source':EXAMPLES['x86_64'],'steps':1})
  self.assertEqual(first['status'],'paused');self.assertEqual(first['registers']['rax'],'0x7')
  edited=s.run(ws,{'architecture':'x86_64','source':EXAMPLES['x86_64'].replace('7','3'),'steps':2})
  self.assertEqual(edited['registers']['rax'],'0x8')
 def test_invalid_syntax_and_untrusted_project(self):
  s=Simulation(None)
  with self.assertRaises(PermissionError):s.run(SimpleNamespace(trusted=False),{})
  if not bundled_tool('python'):self.skipTest('Requires the prepared SDK')
  r=s.run(SimpleNamespace(trusted=True),{'architecture':'x86_64','source':'invented_instruction rax\n','steps':10})
  self.assertEqual(r['status'],'error');self.assertIn('error',r['error'])
 def test_bounded_infinite_loop(self):
  if not bundled_tool('python'):self.skipTest('Requires the prepared SDK')
  r=Simulation(None).run(SimpleNamespace(trusted=True),{'architecture':'x86_64','source':'.text\nloop: jmp loop\n','steps':30})
  self.assertEqual(r['status'],'paused');self.assertEqual(r['executed'],30)
 def test_sdk_environment_does_not_import_user_packages(self):
  env=tool_environment();self.assertEqual(env['PYTHONNOUSERSITE'],'1')
  if bundled_tool('java'):self.assertTrue((Path(env['JAVA_HOME'])/'bin/java.exe').is_file())

class DependencyActivationTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name);self.ws=root/'workspace';self.ws.mkdir();(self.ws/'main.py').write_text('x=1\n')
  self.app=Application(ROOT,self.ws,data_dir=root/'profile');self.app.workspace.trusted=True;self.store=self.app.features.extensions
 def tearDown(self):self.app.features.shutdown();self.app.runner.shutdown();self.tmp.cleanup()
 def install(self,name,code,deps=()):
  b=io.BytesIO()
  with zipfile.ZipFile(b,'w') as z:
   z.writestr('extension/package.json',json.dumps({'publisher':'qa','name':name,'version':'1.0.0','license':'MIT','main':'main.cjs','extensionDependencies':list(deps)}));z.writestr('extension/main.cjs',code)
  self.store.install(self.store.inspect_bytes(b.getvalue())['ticket'],True)
 def test_dependency_function_exports_and_own_context_are_preserved(self):
  self.install('dep',"const v=require('vscode');exports.activate=c=>{v.window.registerTreeDataProvider('qa.dep.view',{getChildren:()=>[12],getTreeItem:n=>({label:'Valor '+n})});v.workspace.registerTextDocumentContentProvider('qa-dep',{provideTextDocumentContent:()=> 'dependencia ñ'});return {sum:(a,b)=>a+b,id:c.extension.id};};")
  self.install('root',"const v=require('vscode');exports.activate=async()=>{const d=v.extensions.getExtension('qa.dep');const a=await d.activate();v.commands.registerCommand('qa.dep.sum',()=>({value:a.sum(7,5),id:a.id,active:d.isActive}));};",['qa.dep'])
  runtime=self.app.features.extension_runtime;state=runtime.start(self.app.workspace,'qa.root',True)
  self.assertEqual(state['hosts'][0]['dependencies'],['qa.dep'])
  result=runtime.request(self.app.workspace,{'id':'qa.root','method':'command','command':'qa.dep.sum'})['result']
  self.assertEqual(result,{'value':12,'id':'qa.dep','active':True})
  tree=runtime.request(self.app.workspace,{'id':'qa.root','method':'tree','view':'qa.dep.view'});self.assertEqual(tree['items'][0]['label'],'Valor 12')
  virtual=runtime.request(self.app.workspace,{'id':'qa.root','method':'virtual','uri':'qa-dep://test'});self.assertEqual(virtual['text'],'dependencia ñ')
 def test_missing_disabled_and_circular_dependencies_do_not_start_host(self):
  self.install('missing','exports.activate=()=>{}',['qa.absent'])
  with self.assertRaisesRegex(ValueError,'Falta'):dependency_graph(self.store,'qa.missing')
  self.install('dep','exports.activate=()=>{}');self.install('root','exports.activate=()=>{}',['qa.dep']);self.store.update_state('qa.dep',False)
  with self.assertRaisesRegex(ValueError,'desactivada'):self.app.features.extension_runtime.start(self.app.workspace,'qa.root',True)
  self.assertFalse(self.store.installed['qa.dep']['enabled']);self.assertFalse(self.app.features.extension_runtime.hosts)
  self.install('a','exports.activate=()=>{}',['qa.b']);self.install('b','exports.activate=()=>{}',['qa.a'])
  with self.assertRaisesRegex(ValueError,'circulares'):dependency_graph(self.store,'qa.a')
 def test_ssh_profile_persists_and_rejects_options(self):
  m=self.app.features.machines
  for field in ({'host':'-oProxyCommand=foo','user':'zenit'},{'host':'127.0.0.1','user':'-root'}):
   with self.assertRaises(ValueError):m.save_ssh({'type':'macos',**field})
  state=m.save_ssh({'type':'macos','host':'192.168.1.20','user':'zenit','port':22})
  self.assertEqual(state['profiles'][0]['mode'],'ssh');self.assertNotIn('password',json.dumps(state))
  from backend.machines import Machines
  restored=Machines(self.app.features);self.assertEqual(restored.profiles,m.profiles)
 def test_restore_pins_dependency_packages_and_requires_review_after_update(self):
  self.install('dep','exports.activate=()=>({version:1})')
  self.install('root','exports.activate=()=>{}',['qa.dep'])
  runtime=self.app.features.extension_runtime;runtime.start(self.app.workspace,'QA.ROOT',True)
  self.assertIn('qa.root',runtime.hosts);runtime.shutdown();runtime.restore(self.app.workspace)
  self.assertIn('qa.root',runtime.hosts);runtime.shutdown()
  self.install('dep','exports.activate=()=>({version:2})')
  state=runtime.restore(self.app.workspace)
  self.assertFalse(runtime.hosts);self.assertIn('cambiaron',state['errors']['qa.root'])
  runtime.start(self.app.workspace,'qa.root',True)
  self.assertNotIn('qa.root',runtime.errors)
 def test_disabling_dependency_stops_parent_group_and_preserves_user_choice(self):
  self.install('dep','exports.activate=()=>({value:12})')
  self.install('root','exports.activate=()=>{}',['qa.dep'])
  runtime=self.app.features.extension_runtime;runtime.start(self.app.workspace,'qa.root',True)
  self.app.features.post('/extensions/toggle',{'id':'qa.dep','enabled':False})
  self.assertFalse(runtime.hosts);self.assertFalse(self.store.installed['qa.dep']['enabled'])
  runtime.restore(self.app.workspace);self.assertFalse(runtime.hosts)
  with self.assertRaisesRegex(ValueError,'desactivada'):runtime.start(self.app.workspace,'qa.root',True)

if __name__=='__main__':unittest.main()
