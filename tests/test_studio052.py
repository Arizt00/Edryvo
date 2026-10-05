"""0.5.2: persisted profiles, real Python stepping and staged installer behavior."""
from pathlib import Path
from backend.version import VERSION, REVISION
import json
import tempfile
import time
import unittest
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.server import Application
from backend.studio import StudioState
from installer import Installer

def until(check, timeout=8):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        value=check()
        if value:return value
        time.sleep(.025)
    raise AssertionError('Timed out waiting for debugger')

class StudioTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name)
    def test_profile_survives_server_or_origin_change(self):
        s=StudioState(self.base);s.update({'displayName':'Día 李','onboarded':True,'layout':{'version':3,'sizes':{'right':350}}})
        second=StudioState(self.base)
        self.assertEqual(second.export()['displayName'],'Día 李');self.assertTrue(second.export()['onboarded'])
        self.assertEqual(second.export()['layout']['sizes']['right'],350)
    def test_profile_changes_are_atomic_and_avatar_is_validated(self):
        s=StudioState(self.base);before=s.export()
        with self.assertRaises(ValueError):s.update({'displayName':'New','avatar':'data:image/svg+xml;base64,PHN2Zz4='})
        self.assertEqual(s.export(),before)
        with self.assertRaises(ValueError):s.update({'avatar':'data:image/png;base64,PHNjcmlwdD4='})
        with self.assertRaises(ValueError):s.update({'recent':[{'path':'x.py'}]})
    def test_installer_copies_actual_payload_and_keeps_existing_version(self):
        payload=self.base/'payload';payload.mkdir();(payload/'zenit.exe').write_bytes(b'MZ-test-fixture');(payload/'_internal').mkdir();(payload/'_internal/test.txt').write_text('payload',encoding='utf-8')
        target=self.base/'installed';old=target/f'app-{VERSION}-R{REVISION}';old.mkdir(parents=True);(old/'old.txt').write_text('preserved')
        inst=Installer(payload,target);inst._install({'packages':[],'locale':'es','shortcuts':False,'register':False})
        self.assertEqual(inst.status()['status'],'finished');self.assertEqual((target/f'app-{VERSION}-R{REVISION}/_internal/test.txt').read_text(),'payload')
        self.assertEqual(len(list(target.glob(f'app-{VERSION}-R{REVISION}-previous-*/old.txt'))),1)
        self.assertEqual(json.loads((target/'installation.json').read_text())['version'],VERSION)
    def test_installer_rejects_unknown_packages_before_start(self):
        inst=Installer(self.base/'payload',self.base/'target')
        with self.assertRaises(ValueError):inst.start({'packages':['arbitrary-command']})
        self.assertFalse((self.base/'target').exists())
    def test_preview_upgrade_preserves_the_payload_of_an_older_running_revision(self):
        payload=self.base/'payload';payload.mkdir();(payload/'zenit.exe').write_bytes(b'MZ-new-revision')
        target=self.base/'installed';previous=target/f'app-{VERSION}';previous.mkdir(parents=True);(previous/'zenit.exe').write_bytes(b'MZ-existing-running-revision')
        (target/'installation.json').write_text(json.dumps({'version':VERSION,'revision':2,'directory':previous.name,'directories':[previous.name]}),encoding='utf-8')
        inst=Installer(payload,target);inst._install({'packages':[],'locale':'es','shortcuts':False,'register':False})
        self.assertEqual(inst.status()['status'],'finished');self.assertEqual((previous/'zenit.exe').read_bytes(),b'MZ-existing-running-revision')
        manifest=json.loads((target/'installation.json').read_text());self.assertEqual(manifest['revision'],REVISION);self.assertIn(previous.name,manifest['directories']);self.assertEqual(manifest['directory'],f'app-{VERSION}-R{REVISION}')

class DebuggerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);ws=self.base/'ws';ws.mkdir()
        (ws/'hello.py').write_text('x = 2\nx += 3\nprint("resultado", x)\n',encoding='utf-8')
        self.app=Application(ROOT,ws,data_dir=self.base/'profile');self.d=self.app.features.debugger
        self.addCleanup(self.temp.cleanup);self.addCleanup(self.app.runner.shutdown);self.addCleanup(self.app.features.shutdown)
    def test_trust_is_required(self):
        with self.assertRaises(PermissionError):self.d.start(self.app.workspace,'hello.py',[])
    def test_real_stepping_breakpoints_and_output(self):
        self.app.workspace.trusted=True;self.d.start(self.app.workspace,'hello.py',[3])
        until(lambda:self.d.snapshot()['status']=='paused')
        self.assertEqual(self.d.snapshot()['line'],1)
        self.d.command('next');until(lambda:self.d.snapshot()['status']=='paused' and self.d.snapshot()['line']==2)
        self.assertIn({'name':'x','type':'int','value':'2'},self.d.snapshot()['variables'])
        self.d.command('continue');until(lambda:self.d.snapshot()['status']=='paused' and self.d.snapshot()['line']==3)
        self.assertTrue(self.d.snapshot()['stack']);self.d.command('continue')
        until(lambda:self.d.snapshot()['status']=='finished')
        self.assertIn('resultado 5',self.d.snapshot()['output'])
    def test_workspace_switch_stops_debugger(self):
        self.app.workspace.trusted=True;self.d.start(self.app.workspace,'hello.py',[])
        until(lambda:self.d.snapshot()['status']=='paused');self.app.features.workspace_changed()
        self.assertEqual(self.d.snapshot()['status'],'stopped');self.assertIsNotNone(self.d.process.poll())
    def test_runtime_error_is_reported(self):
        (self.app.workspace.root/'bad.py').write_text('raise RuntimeError("real failure")\n',encoding='utf-8')
        self.app.workspace.trusted=True;self.d.start(self.app.workspace,'bad.py',[])
        until(lambda:self.d.snapshot()['status']=='paused');self.d.command('continue')
        until(lambda:self.d.snapshot()['status']=='error');self.assertIn('real failure',self.d.snapshot()['error'])

if __name__=='__main__':unittest.main()
