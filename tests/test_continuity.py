"""R3: real watch/restart, syntax analysis, debugger stdin, official account protocol."""
from pathlib import Path
import io
import json
import sys
import tempfile
import time
import unittest
import zipfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.server import Application
from backend.diagnostics import inspect_buffer, output_diagnostics
from backend.extensions import validate_remote
from backend.accounts import CodexAccount, Accounts
from backend.providers import AIJob

def until(fn,timeout=12):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        result=fn()
        if result:return result
        time.sleep(.06)
    raise AssertionError('Timed out waiting for state')

class ContinuityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.ws=self.base/'project';self.ws.mkdir()
        (self.ws/'main.py').write_text('print("first",flush=True)\n',encoding='utf-8')
        self.app=Application(ROOT,self.ws,data_dir=self.base/'profile');self.app.workspace.trusted=True
        self.lantern=self.app.features.lantern
    def tearDown(self):
        self.app.features.shutdown()
        for job in self.app.runner.jobs.values():
            if not job.done:job.cancel()
        self.temp.cleanup()
    def test_lantern_edit_error_recovery(self):
        self.lantern.start(self.app.workspace,'main.py')
        until(lambda:self.lantern.snapshot()['status']=='watching')
        self.assertIn('first',self.lantern.snapshot()['output'])
        (self.ws/'main.py').write_text('print("second",flush=True)\n')
        until(lambda:'second\n' in self.lantern.snapshot()['output'].replace('\r',''))
        before=self.lantern.snapshot()['revision']
        (self.ws/'main.py').write_text('print(\n')
        until(lambda:self.lantern.snapshot()['status']=='error')
        (self.ws/'main.py').write_text('print("recovered",flush=True)\n')
        until(lambda:'recovered\n' in self.lantern.snapshot()['output'].replace('\r',''))
        self.assertGreater(self.lantern.snapshot()['revision'],before)
        self.assertFalse(self.lantern.stop()['active'])
    def test_lantern_restart_cancels_owned_process(self):
        (self.ws/'main.py').write_text('import time\nprint("ready",flush=True)\ntime.sleep(60)\n')
        self.lantern.start(self.app.workspace,'main.py')
        until(lambda:'ready\n' in self.lantern.snapshot()['output'].replace('\r',''));old=self.lantern.job
        (self.ws/'main.py').write_text('print("replacement",flush=True)\n')
        until(lambda:'replacement\n' in self.lantern.snapshot()['output'].replace('\r',''))
        self.assertTrue(old.done);self.assertTrue(old.cancelled);self.assertIsNotNone(old.process.poll())
    def test_lantern_html_and_workspace_boundary(self):
        (self.ws/'index.html').write_text('<h1>Preview</h1>')
        self.lantern.start(self.app.workspace,'index.html')
        state=until(lambda:self.lantern.snapshot() if self.lantern.snapshot().get('preview') else None)
        self.assertTrue(state['preview']['url'].startswith('http://127.0.0.1:'))
        self.app.features.workspace_changed();self.assertFalse(self.lantern.snapshot()['active'])
    def test_lantern_requires_trust(self):
        self.app.workspace.trusted=False
        with self.assertRaises(PermissionError):self.lantern.start(self.app.workspace,'main.py')
    def test_syntax_never_runs_buffer(self):
        sentinel=self.base/'should-not-exist'
        value=inspect_buffer(self.app.workspace,self.app.features.runtimes,'main.py',f'open({str(sentinel)!r},"w").write("x")')
        self.assertEqual(value['diagnostics'],[]);self.assertFalse(sentinel.exists())
        bad=inspect_buffer(self.app.workspace,self.app.features.runtimes,'main.py','def broken(:\n pass')
        self.assertEqual(bad['diagnostics'][0]['startLineNumber'],1)
    def test_compiler_diagnostics_filter_path(self):
        text='C:\\project\\main.c:3:8: error: unknown name\nC:\\project\\other.c:4:2: error: other\n'
        result=output_diagnostics(text,'main.c');self.assertEqual(len(result),1);self.assertEqual(result[0]['startColumn'],8)
    def test_python_debug_input_pause_step_out(self):
        (self.ws/'main.py').write_text('def answer():\n    return 42\nname = input("Name: ")\nvalue = answer()\nprint(name, value)\n')
        debug=self.app.features.debugger;debug.start(self.app.workspace,'main.py',[2,4])
        until(lambda:debug.snapshot()['status']=='paused');debug.command('continue')
        until(lambda:debug.snapshot().get('waitingInput'));debug.input('Lumen\n')
        until(lambda:debug.snapshot()['status']=='paused' and debug.snapshot().get('line')==4)
        debug.command('step');until(lambda:debug.snapshot()['status']=='paused' and debug.snapshot().get('line')==2)
        debug.command('out');until(lambda:debug.snapshot()['status']=='paused');debug.command('continue')
        until(lambda:debug.snapshot()['status']=='finished');self.assertIn('Lumen 42',debug.snapshot()['output'])
    def test_python_pause_without_breakpoints(self):
        (self.ws/'main.py').write_text('import time\ni=0\nwhile i<500:\n    i+=1\n    time.sleep(.02)\n')
        debug=self.app.features.debugger;debug.start(self.app.workspace,'main.py',[])
        until(lambda:debug.snapshot()['status']=='paused');debug.command('continue');time.sleep(.15);debug.command('pause')
        until(lambda:debug.snapshot()['status']=='paused');debug.stop()
    def test_official_cdn_exact_host(self):
        validate_remote('https://openvsx.eclipsecontent.org/PKief/icon.vsix')
        for url in ('https://openvsx.eclipsecontent.org.evil.test/a','http://open-vsx.org/a','https://evil.test/a','https://user@open-vsx.org/a'):
            with self.assertRaises(ValueError):validate_remote(url)
    def test_icon_theme_and_jsonc(self):
        package={'publisher':'qa','name':'icons','version':'1.0.0','contributes':{'iconThemes':[{'id':'glass','path':'theme/icons.json'}]}}
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as archive:
            archive.writestr('extension/package.json',json.dumps(package))
            archive.writestr('extension/theme/icons.json','{// note\n"iconDefinitions":{"py":{"iconPath":"../icons/python.svg"}},"fileExtensions":{"py":"py"},}')
            archive.writestr('extension/icons/python.svg','<svg xmlns="http://www.w3.org/2000/svg"><path d="M1 1h4"/></svg>')
        store=self.app.features.extensions;review=store.inspect_bytes(buf.getvalue());self.assertIn('iconThemes',review['supported'])
        store.install(review['ticket'],True);theme=store.contributions()['iconThemes'][0]
        self.assertTrue(theme['definitions']['py'].startswith('data:image/svg+xml;base64,'))
    def test_official_codex_rpc_stream(self):
        script=self.base/'fake_codex.py'
        script.write_text('''import json,sys
def send(value):print(json.dumps(value),flush=True)
for line in sys.stdin:
 m=json.loads(line);method=m['method'];result={}
 if method=='account/read':result={'account':{'type':'chatgpt','email':'test@example.invalid','planType':'test'}}
 if method=='model/list':result={'data':[{'id':'test-model','model':'test-model'}]}
 if method=='thread/start':
  assert m['params']['sandbox']=='read-only'
  result={'thread':{'id':'test-thread'}}
 if method=='turn/start':result={'turn':{'id':'test-turn'}}
 if 'id' in m:send({'id':m['id'],'result':result})
 if method=='turn/start':
  send({'method':'item/agentMessage/delta','params':{'threadId':'test-thread','delta':'Hello from official protocol'}})
  send({'method':'turn/completed','params':{'threadId':'test-thread','turn':{'id':'test-turn','status':'completed'}}})
''')
        account=CodexAccount(self.base/'test-account')
        with patch('backend.accounts.client_argv',return_value=[sys.executable,str(script)]):
            try:
                self.assertTrue(account.status()['authenticated']);self.assertEqual(account.models()['models'],['test-model'])
                job=AIJob('codex','test-model');account.stream(job,[{'role':'user','content':'hello'}],'review only',3)
                self.assertEqual(job.text,'Hello from official protocol')
            finally:account.shutdown()
    def test_absent_clients_not_reported_connected(self):
        with patch('backend.accounts.executable',return_value=None):
            for provider in ('codex','claude-code','gemini-cli','copilot'):
                result=self.app.features.ai.accounts.status(provider)
                self.assertFalse(result['installed']);self.assertIsNone(result['authenticated'])

if __name__=='__main__':unittest.main()
