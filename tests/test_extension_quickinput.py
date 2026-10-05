"""Real Node extension events, identities, validation and cancellation through Python."""
import concurrent.futures,io,json,tempfile,time,unittest,zipfile
from pathlib import Path
from backend.server import Application
ROOT=Path(__file__).resolve().parents[1]
PLUGIN=r'''
const v=require('vscode');
exports.activate=()=>{
 v.commands.registerCommand('qa.pick',()=>new Promise(resolve=>{
  const pick=v.window.createQuickPick(),back=v.QuickInputButtons.Back,refresh={iconPath:new v.ThemeIcon('refresh'),tooltip:'Actualizar opción'};
  const first={label:'Primera opción ñ',description:'Python',detail:'Opción inicial',tag:41,buttons:[refresh]};let active=0,selection=0,backPressed=0,itemPressed=0;
  pick.title='Asistente de extensión';pick.step=1;pick.totalSteps=2;pick.buttons=[back];pick.items=[{label:'Herramientas',kind:v.QuickPickItemKind.Separator},first];
  pick.onDidChangeActive(()=>active++);pick.onDidChangeSelection(()=>selection++);
  pick.onDidTriggerButton(b=>{if(b===back){backPressed++;pick.title='Paso anterior';}});
  pick.onDidTriggerItemButton(e=>{if(e.item===first&&e.button===refresh){itemPressed++;first.label='Actualizada ñ';pick.items=[first];}});
  pick.onDidChangeValue(value=>{if(value==='nuevo')pick.items=[{label:'nuevo ñ',tag:42}];});
  pick.onDidAccept(()=>{const result={tag:pick.selectedItems[0]?.tag,active,selection,backPressed,itemPressed};resolve(result);pick.dispose();});pick.onDidHide(()=>{resolve(null);pick.dispose();});pick.show();
 }));
 v.commands.registerCommand('qa.input',()=>v.window.showInputBox({title:'Nombre del proyecto',placeHolder:'Nombre',value:'',prompt:'Escribe un nombre con al menos tres letras',validateInput:async value=>{await new Promise(r=>setTimeout(r,value==='lento'?140:15));return value.length<3?'Escribe al menos tres letras':undefined;}}));
 v.commands.registerCommand('qa.multi',()=>v.window.showQuickPick([{label:'Python',picked:true},{label:'Rust'},{label:'Grupo',kind:v.QuickPickItemKind.Separator}],{title:'Lenguajes',canPickMany:true,matchOnDescription:true}));
 v.commands.registerCommand('qa.cancel',()=>{const token=new v.CancellationTokenSource();setTimeout(()=>token.cancel(),80);return v.window.showInputBox({title:'Cancelación'},token.token);});
 v.commands.registerCommand('qa.idle',()=>{const input=v.window.createInputBox();input.title='Hasta cerrar el motor';input.show();return input._id;});
 v.commands.registerCommand('qa.programmatic',()=>new Promise(resolve=>{const input=v.window.createInputBox(),changes=[];input.onDidChangeValue(value=>changes.push(value));input.value='creación';input.value='creación';input.onDidAccept(()=>{resolve(changes);input.dispose();});input.show();}));
 v.commands.registerCommand('qa.reshow',()=>new Promise(resolve=>{const input=v.window.createInputBox();let shown=0;input.title='Primer paso';input.onDidHide(()=>{if(!shown++){input.title='Segundo paso';input.show();}else{resolve(null);input.dispose();}});input.show();}));
};
'''
def install_plugin(app):
 raw=io.BytesIO()
 with zipfile.ZipFile(raw,'w') as z:
  z.writestr('extension/package.json',json.dumps({'publisher':'qa','name':'quickinput','version':'1.0.0','main':'main.cjs'}));z.writestr('extension/main.cjs',PLUGIN)
 store=app.features.extensions;store.install(store.inspect_bytes(raw.getvalue())['ticket'],True);app.features.extension_runtime.start(app.workspace,'qa.quickinput',True)

class QuickInputTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name);self.ws=root/'ws';self.ws.mkdir();self.app=Application(ROOT,self.ws,data_dir=root/'profile');self.app.workspace.trusted=True;install_plugin(self.app);self.pool=concurrent.futures.ThreadPoolExecutor();self.sequence=0
 def tearDown(self):self.app.features.shutdown();self.app.runner.shutdown();self.pool.shutdown();self.tmp.cleanup()
 def call(self,name):return self.app.features.extension_runtime.request(self.app.workspace,{'id':'qa.quickinput','method':'command','command':name}).get('result')
 def wait(self,predicate=lambda x:x.get('visible')):
  end=time.monotonic()+8
  while time.monotonic()<end:
   for item in self.app.features.extension_services.snapshot()['quickinputs']:
    if predicate(item):return item
   time.sleep(.02)
  self.fail('QuickInput no respondió.')
 def send(self,control,type,**values):
  self.sequence+=1;return self.app.features.extension_services.quickinput_event({'id':control['id'],'type':type,'sequence':self.sequence,**values})
 def test_dynamic_items_preserve_identities_and_navigation_events(self):
  future=self.pool.submit(self.call,'qa.pick');item=self.wait();first=item['items'][1]
  self.send(item,'button',key=item['buttons'][0]['key']);self.wait(lambda x:x['title']=='Paso anterior')
  self.send(item,'itemButton',item=first['key'],key=first['buttons'][0]['key']);self.wait(lambda x:x['items'][0]['label']=='Actualizada ñ')
  self.send(item,'value',value='nuevo');item=self.wait(lambda x:x['items'][0]['label']=='nuevo ñ');key=item['items'][0]['key']
  self.send(item,'active',keys=[key]);self.send(item,'selection',keys=[key]);self.send(item,'accept');result=future.result(8)
  self.assertEqual(result,{'tag':42,'active':1,'selection':1,'backPressed':1,'itemPressed':1})
 def test_validation_blocks_accept_and_outdated_async_result_is_ignored(self):
  future=self.pool.submit(self.call,'qa.input');item=self.wait(lambda x:bool(x.get('validationMessage')))
  self.send(item,'accept');time.sleep(.1);self.assertFalse(future.done())
  self.send(item,'value',value='lento');self.send(item,'value',value='ñandú');item=self.wait(lambda x:x['value']=='ñandú' and not x['busy']);self.send(item,'accept')
  self.assertEqual(future.result(8),'ñandú')
 def test_multiple_selection_initial_pick_and_separators_are_not_values(self):
  future=self.pool.submit(self.call,'qa.multi');item=self.wait();self.assertEqual(len(item['selectedItems']),1)
  self.send(item,'selection',keys=[x['key'] for x in item['items']]);self.send(item,'accept')
  self.assertEqual([x['label'] for x in future.result(8)],['Python','Rust'])
 def test_cancellation_returns_no_value_and_disposes_control(self):
  self.assertIsNone(self.call('qa.cancel'));time.sleep(.1);self.assertFalse(self.app.features.extension_services.snapshot()['quickinputs'])
 def test_stop_host_removes_its_controls(self):
  self.call('qa.idle');self.wait();self.app.features.extension_runtime.stop('qa.quickinput');self.assertFalse(self.app.features.extension_services.snapshot()['quickinputs'])
 def test_programmatic_value_changes_fire_once_and_reach_the_control(self):
  future=self.pool.submit(self.call,'qa.programmatic');item=self.wait();self.assertEqual(item['value'],'creación');self.send(item,'accept');self.assertEqual(future.result(8),['creación'])

class ExtensionReviewFactsTest(unittest.TestCase):
 def test_real_sizes_dependencies_and_icon_survive_install_and_reload(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);ws=root/'ws';ws.mkdir();app=Application(ROOT,ws,data_dir=root/'profile');store=app.features.extensions;raw=io.BytesIO()
   with zipfile.ZipFile(raw,'w',compression=zipfile.ZIP_DEFLATED) as z:
    z.writestr('extension/package.json',json.dumps({'publisher':'qa','name':'facts','version':'1.0.0','icon':'icon.svg','extensionDependencies':['qa.quickinput'],'extensionPack':['qa.optional']}));z.writestr('extension/icon.svg','<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0h2v2"/></svg>');z.writestr('extension/data.txt','x'*10000)
   info=store.inspect_bytes(raw.getvalue());self.assertEqual(info['size'],len(raw.getvalue()));self.assertGreater(info['unpackedSize'],10000);self.assertTrue(info['icon'].startswith('data:image/'));self.assertEqual(info['dependencies'][0],{'id':'qa.quickinput','required':True,'installed':False,'enabled':False,'version':None});store.install(info['ticket'],True)
   app.features.shutdown();app.runner.shutdown();app=Application(ROOT,ws,data_dir=root/'profile');self.assertEqual(app.features.extensions.list()[0]['dependencies'],info['dependencies']);app.features.shutdown();app.runner.shutdown()

if __name__=='__main__':unittest.main()
