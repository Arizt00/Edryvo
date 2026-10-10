import io,json,tempfile,unittest,zipfile
from pathlib import Path
from backend.server import Application
ROOT=Path(__file__).resolve().parents[1]
GRAMMAR={'scopeName':'source.python','patterns':[{'name':'keyword.control.zenit','match':'\\bzenit_kw\\b'},{'name':'comment.block.zenit','begin':'/\\*','end':'\\*/'}]}
INJECTION={'scopeName':'zenit.todo','injectionSelector':'L:comment.block.zenit','patterns':[{'name':'constant.todo.zenit','match':'TODO'}]}

def install_fixture(store):
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as archive:
        manifest={'publisher':'qa','name':'grammar','version':'1.0.0','license':'MIT','contributes':{
            'grammars':[{'language':'python','scopeName':'source.python','path':'python.json'},{'scopeName':'zenit.todo','path':'todo.json','injectTo':['source.python']}],
            'themes':[{'label':'Gramática QA','id':'qa','uiTheme':'vs','path':'theme.json'}]}}
        archive.writestr('extension/package.json',json.dumps(manifest));archive.writestr('extension/python.json',json.dumps(GRAMMAR));archive.writestr('extension/todo.json',json.dumps(INJECTION))
        archive.writestr('extension/theme.json',json.dumps({'colors':{'editor.background':'#ffffff','editor.foreground':'#202030'},'tokenColors':[
            {'scope':'source.python keyword.control.zenit','settings':{'foreground':'#125ede'}},
            {'scope':'comment.block.zenit','settings':{'foreground':'#476847','fontStyle':'italic'}},
            {'scope':'constant.todo.zenit','settings':{'foreground':'#b12769','fontStyle':'bold'}}]}))
    review=store.inspect_bytes(data.getvalue());store.install(review['ticket'],True);return review

class GrammarContributionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name);project=root/'project';project.mkdir();self.app=Application(ROOT,project,data_dir=root/'profile');self.store=self.app.features.extensions
    def tearDown(self):self.app.features.shutdown();self.app.runner.shutdown();self.tmp.cleanup()
    def test_declarative_grammars_do_not_need_executable_host(self):
        review=install_fixture(self.store);data=self.store.contributions();self.assertEqual(len(data['grammars']),2);self.assertFalse(data['errors']);self.assertEqual(data['grammars'][1]['injectTo'],['source.python']);self.assertEqual(json.loads(data['grammars'][0]['content']),GRAMMAR);self.assertFalse(self.app.features.extension_runtime.snapshot()['hosts']);self.assertFalse(any('no se ejecutan' in x for x in review['warnings']))
    def test_disabled_grammar_is_removed_without_deleting_the_package(self):
        install_fixture(self.store);self.store.update_state('qa.grammar',enabled=False);self.assertFalse(self.store.contributions()['grammars']);self.assertEqual(len(self.store.list()),1)
    def test_grammar_cannot_read_outside_its_installed_package(self):
        install_fixture(self.store);root=self.store.root/self.store.list()[0]['directory']/'extension';manifest=json.loads((root/'package.json').read_text());manifest['contributes']['grammars'][0]['path']='../../outside.json';(root/'package.json').write_text(json.dumps(manifest));data=self.store.contributions();self.assertEqual(len(data['grammars']),1);self.assertTrue(data['errors'])
    def test_plist_is_transferred_with_its_real_format(self):
        install_fixture(self.store);root=self.store.root/self.store.list()[0]['directory']/'extension';manifest=json.loads((root/'package.json').read_text());manifest['contributes']['grammars'][0]['path']='python.tmLanguage';(root/'package.json').write_text(json.dumps(manifest));xml='<?xml version="1.0"?><plist version="1.0"><dict><key>scopeName</key><string>source.python</string><key>patterns</key><array/></dict></plist>';(root/'python.tmLanguage').write_text(xml);self.assertEqual(self.store.contributions()['grammars'][0]['content'],xml)
