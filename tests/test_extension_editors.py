"""Actual Node viewport events, split editors and unsaved document state."""
import io,json,tempfile,time,unittest,zipfile
from pathlib import Path
from backend.server import Application
ROOT=Path(__file__).resolve().parents[1]
PLUGIN="""const v=require('vscode');exports.activate=()=>{
 const events=[];for(const [name,subscribe] of [['ranges',v.window.onDidChangeTextEditorVisibleRanges],['selection',v.window.onDidChangeTextEditorSelection],['visible',v.window.onDidChangeVisibleTextEditors],['options',v.window.onDidChangeTextEditorOptions]])subscribe(value=>events.push(name));
 v.commands.registerCommand('qa.views',()=>({events,active:v.window.activeTextEditor?.document.fileName,views:v.window.visibleTextEditors.map(e=>({file:e.document.fileName,text:e.document.getText(),ranges:e.visibleRanges.map(r=>({start:r.start.line,end:r.end.line,typed:r instanceof v.Range})),anchor:e.selection.anchor,position:e.selection.active,options:e.options,column:e.viewColumn}))}));
};"""

def install(app):
    raw=io.BytesIO()
    with zipfile.ZipFile(raw,'w') as z:
        z.writestr('extension/package.json',json.dumps({'publisher':'qa','name':'editor-state','version':'1.0.0','main':'main.cjs'}));z.writestr('extension/main.cjs',PLUGIN)
    app.features.extensions.install(app.features.extensions.inspect_bytes(raw.getvalue())['ticket'],True)
    app.features.extension_runtime.start(app.workspace,'qa.editor-state',True)

class EditorStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();base=Path(self.tmp.name);ws=base/'ws';ws.mkdir()
        for name in ['one.js','two.js']:(ws/name).write_text('const value = 1;\n',encoding='utf-8')
        self.app=Application(ROOT,ws,data_dir=base/'profile');self.app.workspace.trusted=True;install(self.app)
    def tearDown(self):self.app.features.shutdown();self.app.runner.shutdown();self.tmp.cleanup()
    def view(self,path='one.js',ident='0',active=True,start=0):
        return {'id':ident,'path':path,'active':active,'language':'javascript','visibleRanges':[{'start':{'line':start,'character':0},'end':{'line':start+5,'character':0}}],
            'selections':[{'anchor':{'line':0,'character':8},'active':{'line':0,'character':2}}],'options':{'tabSize':4,'insertSpaces':True}}
    def state(self,views):return self.app.features.post('/extensions/editor-state',{'editors':views})
    def result(self):return self.app.features.extension_runtime.request(self.app.workspace,{'id':'qa.editor-state','method':'command','command':'qa.views'})['result']
    def wait(self,check):
        end=time.monotonic()+4
        while time.monotonic()<end:
            result=self.result()
            if check(result):return result
            time.sleep(.02)
        self.fail('No llegó el evento del editor al host real.')
    def test_ranges_selections_and_dirty_text_reach_real_extension(self):
        self.app.features.buffers.update(self.app.workspace,{'path':'one.js','text':'const value = "ñ";\n','saved':False})
        self.state([self.view()]);result=self.wait(lambda r:len(r['views'])==1);view=result['views'][0]
        self.assertEqual(view['text'],'const value = "ñ";\n');self.assertTrue(view['ranges'][0]['typed']);self.assertEqual(view['anchor']['character'],8);self.assertEqual(view['position']['character'],2)
        self.assertIn('ranges',result['events']);self.assertIn('selection',result['events']);self.assertEqual((self.app.workspace.root/'one.js').read_text(),'const value = 1;\n')
    def test_split_views_scroll_and_close_emit_without_duplicate_events(self):
        self.state([self.view(),self.view('two.js','1',False)]);initial=self.wait(lambda r:len(r['views'])==2)
        self.state([self.view(),self.view('two.js','1',False)]);self.assertEqual(initial['events'],self.result()['events'])
        self.state([self.view(start=10),self.view('two.js','1',False)]);updated=self.wait(lambda r:r['views'][0]['ranges'][0]['start']==10);self.assertEqual(len(updated['events']),len(initial['events'])+1)
        self.state([self.view('two.js','1')]);single=self.wait(lambda r:len(r['views'])==1);self.assertTrue(single['active'].endswith('two.js'));self.assertEqual(single['views'][0]['column'],1)
        self.state([]);self.wait(lambda r:len(r['views'])==0)
    def test_invalid_ranges_and_untrusted_state_do_not_mutate_snapshot(self):
        bad=self.view();bad['visibleRanges'][0]['start']['line']=-1
        with self.assertRaises(ValueError):self.state([bad])
        self.assertIsNone(self.app.features.extension_services.editor_snapshot)
        self.app.workspace.trusted=False
        with self.assertRaises(PermissionError):self.state([self.view()])
    def test_new_host_receives_last_viewport_during_activation(self):
        self.state([self.view(start=7)]);runtime=self.app.features.extension_runtime;runtime.stop('qa.editor-state');runtime.start(self.app.workspace,'qa.editor-state',True)
        result=self.result();self.assertEqual(result['views'][0]['ranges'][0]['start'],7)
        self.assertEqual(result['events'],[])

if __name__=='__main__':unittest.main()
