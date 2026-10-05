"""R5: real buffer execution, observed values, recoverable operations and removal."""
from pathlib import Path
import json,sys,tempfile,time,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.server import Application
from backend.uninstall import Uninstaller
from backend.file_actions import perform
from backend.package_sizes import package_total

def until(fn,seconds=35):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        value=fn()
        if value:return value
        time.sleep(.04)
    raise AssertionError('Expected state not reached')

class LiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.ws=self.base/'workspace';self.ws.mkdir()
        self.app=Application(ROOT,self.ws,data_dir=self.base/'profile');self.app.workspace.trusted=True;self.live=self.app.features.lantern
    def tearDown(self):self.app.features.shutdown();self.app.runner.shutdown();self.tmp.cleanup()
    def done(self,version):
        def check():
            s=self.live.snapshot()
            return s if s.get('bufferVersion')==version and s.get('code') is not None else None
        state=until(check);self.assertEqual(state['code'],0,state['output']);return state
    def test_unsaved_buffer_lens_and_disk_independence(self):
        original=b'print("ON_DISK")\r\n';(self.ws/'test.py').write_bytes(original)
        self.live.start(self.app.workspace,'test.py','answer = 6 * 7\nitems = [answer, True]\nprint(answer)\n',1)
        s=self.done(1);self.assertIn('42',s['output']);self.assertEqual((self.ws/'test.py').read_bytes(),original)
        self.assertTrue(any(x['line']==1 and '42' in x['value'] for x in s['lens']),s)
        self.assertTrue(any('True' in x['value'] for x in s['lens']),s)
        self.live.stop();self.assertEqual(self.live.snapshot()['lens'],[])
    def test_new_unsaved_file_and_incomplete_revision_waits(self):
        self.live.start(self.app.workspace,'new.py','value = (\n',1)
        until(lambda:self.live.snapshot()['status']=='waiting');self.assertEqual(self.live.snapshot()['revision'],0);self.assertFalse((self.ws/'new.py').exists())
        self.live.buffer(self.app.workspace,'new.py','value = (41+1)\nprint(value)\n',2)
        self.assertIn('42',self.done(2)['output']);self.assertFalse((self.ws/'new.py').exists())
    def test_stale_program_cancel_and_checkpoint(self):
        self.live.start(self.app.workspace,'mem.py','lantern_state["count"] = 20\nprint("READY",flush=True)\nwhile True: pass\n',1)
        until(lambda:'READY' in self.live.snapshot()['output'])
        self.live.buffer(self.app.workspace,'mem.py','lantern_state["count"] += 1\nprint("LATEST", lantern_state["count"])\n',2)
        s=self.done(2);self.assertIn('LATEST 21',s['output']);self.assertNotIn('READY',s['output']);self.assertEqual(s['memory']['count'],21)
    def test_shadow_preserves_local_imports_without_writing_sources(self):
        (self.ws/'helper.py').write_text('def result(): return 42\n')
        self.live.start(self.app.workspace,'main.py','from helper import result\nvalue = result()\nprint(value)\n',1)
        self.assertIn('42',self.done(1)['output']);self.assertFalse((self.ws/'__pycache__').exists())
    def test_compiled_buffers_native_lens_and_invalid_code(self):
        for suffix in ('c','cpp'):
            source='#include "lantern_lens.h"\nint main(){int count=0;LANTERN_LENS_NUMBER(++count);printf("COUNT %d\\n",count);return 0;}\n'
            path='live.'+suffix;self.live.start(self.app.workspace,path,source,1);s=self.done(1)
            self.assertIn('COUNT 1',s['output']);self.assertEqual(s['lens'][0]['value'],'1');self.assertFalse((self.ws/path).exists());self.live.stop()
        self.live.start(self.app.workspace,'invalid.c','int main( {',2);until(lambda:self.live.snapshot()['status']=='waiting');self.assertIsNone(self.live.snapshot().get('job'))
    def test_javascript_observed_values_are_not_evaluated_twice(self):
        self.live.start(self.app.workspace,'a.js','let count=0;console.log(++count);\nlanternLens({count},2,"object");\n',1)
        s=self.done(1);self.assertIn('\n1\n',s['output']);self.assertTrue(any('count: 1' in x['value'] for x in s['lens']),s)
    def test_operations_restore_and_boundary(self):
        ws=self.app.workspace;(self.ws/'original.py').write_text('secret to keep')
        perform(ws,{'operation':'copy','path':'original.py','destination':'copy.py'})
        deleted=perform(ws,{'operation':'delete','path':'copy.py'});self.assertFalse((self.ws/'copy.py').exists())
        perform(ws,{'operation':'restore','ticket':deleted['ticket']});self.assertEqual((self.ws/'copy.py').read_text(),'secret to keep')
        for name in ('../outside','.lumen',''):
            with self.assertRaises((ValueError,PermissionError,FileNotFoundError)):perform(ws,{'operation':'delete','path':name})
        self.assertTrue((self.ws/'original.py').exists())
    def test_search_scoped_before_result_limit(self):
        (self.ws/'a').mkdir();(self.ws/'b').mkdir()
        (self.ws/'a/file.py').write_text('match\n'*210);(self.ws/'b/file.py').write_text('match\n')
        self.assertEqual(len(self.app.workspace.search('match',content=True,folder='b')),1)

class UninstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();base=Path(self.tmp.name);self.root=base/'installation';self.profile=base/'profile'
        (self.root/'app-0.5.2').mkdir(parents=True);(self.root/'app-0.5.2/lumen.exe').write_text('fixture')
        (self.root/'installation.json').write_text(json.dumps({'directory':'app-0.5.2'}));(self.profile/'workspaces/Project').mkdir(parents=True)
        for name in ('Uninstall-Lumen.exe','Uninstall-Zenit.exe'):(self.root/name).write_bytes(b'launcher fixture')
        (self.profile/'workspaces/Project/main.py').write_text('keep me');(self.profile/'preferences.json').write_text('{}')
        self.external=base/'outside.py';self.external.write_text('external')
    def tearDown(self):self.tmp.cleanup()
    def remove(self,**options):
        service=Uninstaller(self.root,self.profile,integrate_windows=False);service.start({'confirm':True,**options})
        until(lambda:service.status()['status']!='removing');self.assertEqual(service.status()['status'],'finished',service.status());self.assertTrue(self.external.exists());return service
    def test_default_keeps_all_user_data(self):
        self.remove();self.assertTrue((self.profile/'preferences.json').exists());self.assertFalse(self.root.exists())
    def test_remove_settings_preserves_projects_unless_explicit(self):
        self.remove(deleteData=True);self.assertFalse((self.profile/'preferences.json').exists());self.assertTrue((self.profile/'workspaces/Project/main.py').exists())
    def test_explicit_data_and_projects_purge(self):
        self.remove(deleteData=True,deleteProjects=True);self.assertFalse(self.profile.exists())
    def test_invalid_manifest_cannot_remove_other_paths(self):
        (self.root/'installation.json').write_text(json.dumps({'directories':['../../']}))
        with self.assertRaises(ValueError):Uninstaller(self.root,self.profile,integrate_windows=False)
        self.assertTrue(self.external.exists())
    def test_missing_confirmation_and_project_selection(self):
        service=Uninstaller(self.root,self.profile,integrate_windows=False)
        with self.assertRaises(ValueError):service.start({})
        with self.assertRaises(ValueError):service.start({'confirm':True,'deleteProjects':True})
        self.assertTrue((self.root/'app-0.5.2/lumen.exe').exists())
    def test_dependency_size_dedup_and_unknown_total(self):
        shared={'package':'shared','version':'1','bytes':50,'complete':True}
        items=[{'package':x,'version':'1','bytes':100,'complete':True,'dependencies':[shared]} for x in ('a','b')]
        self.assertEqual(package_total(items),{'bytes':250,'complete':True,'packages':3})
        items[1]['complete']=False;self.assertFalse(package_total(items)['complete'])

if __name__=='__main__':unittest.main()
