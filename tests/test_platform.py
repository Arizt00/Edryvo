"""0.4 platform tests. AI/registry SDK contracts use explicit test doubles.

PTY and LSP processes, storage, native system readings and task execution use
real local components. Nothing contacts a paid provider or installs a compiler.
"""
from __future__ import annotations
import asyncio
import io
import json
import os
import shutil
import stat
import sys
import tempfile
import time
import types
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.server import Application
from backend.preferences import Preferences,SCHEMA,atomic_json
from backend.extensions import ExtensionStore,validate_remote,safe_member
from backend.toolchains import Toolchains,resolve_argv,validate_argv
from backend.terminals import TerminalManager,child_environment
from backend.providers import AIRouter,CredentialVault,AIJob,build_request,stream_delta
from backend.lsp import LanguageSession
from tools.install_user import locations


def wait_for(check,seconds=8):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        value=check()
        if value:return value
        time.sleep(.035)
    raise AssertionError('Timed out waiting for local test result')


def archive(extra=None,main=False):
    manifest={'publisher':'sample','name':'package','version':'1.0.0','contributes':{'languages':[{'id':'test-lang','extensions':['.tst']}],'snippets':[{'language':'test-lang','path':'snippets.json'}]}}
    if main:manifest['main']='main.js'
    files={'extension/package.json':json.dumps(manifest),'extension/snippets.json':json.dumps({'A':{'prefix':'aaa','body':'hello'}})}
    if main:files['extension/main.js']='throw new Error("MUST NEVER EXECUTE");'
    files.update(extra or {});stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        for name,value in files.items():z.writestr(name,value)
    return stream.getvalue()


class PlatformCase(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.wsroot=self.base/'workspace';self.wsroot.mkdir();(self.wsroot/'hello.py').write_text('print(42)\n')
        self.app=Application(ROOT,self.wsroot,data_dir=self.base/'data');self.f=self.app.features;self.ws=self.app.workspace
        self.addCleanup(self.temp.cleanup);self.addCleanup(self.app.runner.shutdown);self.addCleanup(self.f.shutdown)
    def test_defaults_include_no_cloud_or_hardware(self):
        self.assertFalse(self.f.prefs.get('security.cloudAI'));self.assertFalse(self.f.prefs.get('hardware.enabled'));self.assertGreaterEqual(len(SCHEMA),40)
    def test_settings_validated_atomically(self):
        with self.assertRaises(ValueError):self.f.prefs.update({'general.locale':'en','editor.fontSize':999})
        self.assertEqual(self.f.prefs.get('general.locale'),'es')
    def test_unknown_setting_rejected(self):
        with self.assertRaises(ValueError):self.f.prefs.update({'apiKey':'secret'})
    def test_bool_is_not_number(self):
        with self.assertRaises(ValueError):self.f.prefs.update({'editor.fontSize':True})
    def test_prefs_real_disk_roundtrip(self):
        self.f.prefs.update({'general.locale':'en','appearance.theme':'forest'})
        self.assertEqual(Preferences(self.base/'data').get('appearance.theme'),'forest')
    def test_atomic_json_mode_and_content(self):
        path=self.base/'json';atomic_json(path,{'es':'día'})
        self.assertEqual(json.loads(path.read_text(encoding='utf-8')),{'es':'día'})
        if os.name!='nt':self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
    def test_settings_no_credentials(self):
        self.f.ai.vault.set('openai','TEST_ONLY_CREDENTIAL_012345')
        self.assertNotIn('TEST_ONLY_CREDENTIAL',json.dumps(self.f.state()))
        self.assertNotIn('TEST_ONLY_CREDENTIAL',json.dumps(self.f.prefs.export()))
    def test_audit_does_not_log_content(self):
        self.f.prefs.audit('test',content='secret prompt',key='secret value',provider='openai')
        data=(self.base/'data/audit.jsonl').read_text();self.assertNotIn('secret',data)
    def test_marketplace_network_gate(self):
        self.f.prefs.update({'extensions.network':False})
        with self.assertRaises(PermissionError):self.f.extensions.search('python')
    def test_marketplace_search_contract_mock(self):
        with patch('backend.extensions.download',return_value=json.dumps({'extensions':[{'namespace':'sample','name':'package','version':'1.0.0'}],'totalSize':1}).encode()):
            self.assertEqual(self.f.extensions.search('sample')['extensions'][0]['id'],'sample.package')
    def test_remote_origins_restricted(self):
        for url in ('http://open-vsx.org/a','https://evil.invalid/a','https://user:pass@open-vsx.org/a','https://storage.googleapis.com/other/a'):
            with self.assertRaises(ValueError):validate_remote(url)
        validate_remote('https://open-vsx.org/a');validate_remote('https://storage.googleapis.com/open-vsx/a')
    def test_vsix_preview_no_install(self):
        review=self.f.extensions.inspect_bytes(archive());self.assertIn('ticket',review);self.assertEqual(self.f.extensions.list(),[])
    def test_vsix_consent_required(self):
        review=self.f.extensions.inspect_bytes(archive())
        with self.assertRaises(PermissionError):self.f.extensions.install(review['ticket'])
    def test_vsix_declarative_contributions(self):
        review=self.f.extensions.inspect_bytes(archive());item=self.f.extensions.install(review['ticket'],True)
        self.assertEqual(item['compatibility'],'declarative');self.assertEqual(self.f.extensions.contributions()['snippets'][0]['body'],'hello')
    def test_vsix_executable_entry_is_not_run(self):
        review=self.f.extensions.inspect_bytes(archive(main=True));self.assertEqual(review['compatibility'],'partial');self.assertTrue(review['warnings']);self.f.extensions.install(review['ticket'],True)
        self.assertEqual(len(self.f.extensions.contributions()['languages']),1)
    def test_vsix_toggle_and_remove_payload(self):
        item=self.f.extensions.install(self.f.extensions.inspect_bytes(archive())['ticket'],True)
        folder=self.f.extensions.root/item['directory'];self.assertTrue(folder.exists())
        self.f.extensions.update_state(item['id'],False);self.assertFalse(self.f.extensions.contributions()['languages'])
        self.f.extensions.update_state(item['id'],remove=True);self.assertFalse(folder.exists())
    def test_vsix_zip_slip_rejected(self):
        for relative in ('extension/../../evil','/absolute','extension/..\\evil','extension/C:evil'):
            with self.assertRaises(ValueError):self.f.extensions.inspect_bytes(archive({relative:'evil'}))
    def test_vsix_duplicate_case_rejected(self):
        with self.assertRaises(ValueError):self.f.extensions.inspect_bytes(archive({'extension/SNIPPETS.JSON':'{}'}))
    def test_vsix_symbolic_link_rejected(self):
        raw=io.BytesIO(archive())
        with zipfile.ZipFile(raw,'a') as z:
            entry=zipfile.ZipInfo('extension/link');entry.create_system=3;entry.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(entry,'/etc/passwd')
        with self.assertRaises(ValueError):self.f.extensions.inspect_bytes(raw.getvalue())
    def test_vsix_eight_pending_can_install(self):
        reviews=[self.f.extensions.inspect_bytes(archive()) for _ in range(8)]
        self.f.extensions.install(reviews[0]['ticket'],True)
        self.assertEqual(len(self.f.extensions.pending),7)
    def test_vsix_expired_ticket(self):
        review=self.f.extensions.inspect_bytes(archive());ticket=review['ticket'];_,folder,result=self.f.extensions.pending[ticket];self.f.extensions.pending[ticket]=(time.monotonic()-601,folder,result)
        with self.assertRaises(ValueError):self.f.extensions.install(ticket,True)
    def test_vsix_original_examples_load(self):
        for file in (ROOT/'examples/extensions').glob('*.vsix'):self.f.extensions.install(self.f.extensions.inspect_local(str(file))['ticket'],True)
        contributions=self.f.extensions.contributions();self.assertEqual(len(contributions['themes']),1);self.assertEqual(len(contributions['snippets']),2);self.assertEqual(contributions['errors'],[])
    def test_argv_preserves_shell_metacharacters(self):
        argv=resolve_argv(['echo','${file}','a;b'],self.ws,'hello.py');self.assertEqual(argv[-1],'a;b');self.assertEqual(argv[1],str(self.wsroot/'hello.py'))
    def test_argv_external_file_denied(self):
        with self.assertRaises(PermissionError):resolve_argv(['echo','${file}'],self.ws,'../outside')
    def test_argv_string_not_shell(self):
        with self.assertRaises(ValueError):validate_argv('echo hello && rm nothing')
    def test_toolchain_configuration_roundtrip(self):
        data={'tasks':[{'id':'hello','argv':[sys.executable,'${file}']}],'servers':[],'associations':{'.custom':'python'}}
        self.f.tools.save(data);self.assertEqual(Toolchains(self.f.prefs,self.app.runner).config['associations'],data['associations'])
    def test_duplicate_task_rejected(self):
        with self.assertRaises(ValueError):self.f.tools.save({'tasks':[{'id':'x','argv':['echo']},{'id':'x','argv':['echo']}]})
    def test_tool_plan_no_execution(self):
        with patch('backend.toolchains.shutil.which',return_value='/usr/bin/apt'),patch('backend.toolchains.subprocess.Popen') as pop:
            result=self.f.tools.plan('cmake','apt');self.assertEqual(result['argv'],['sudo','apt','install','cmake']);pop.assert_not_called()
    def test_unknown_package_rejected(self):
        with self.assertRaises(ValueError):self.f.tools.plan('arbitrary;command','apt')
    def test_real_python_task(self):
        self.ws.trusted=True;self.f.tools.save({'tasks':[{'id':'test','argv':[sys.executable,'${file}']}]})
        job=self.f.tools.run(self.ws,'test','hello.py',True);self.assertTrue(job)
        # API runner transport is separately tested by the original suite.
    def test_task_without_trust_rejected(self):
        with self.assertRaises(PermissionError):self.f.tools.run(self.ws,'test','hello.py',True)
    def test_hardware_opt_in(self):
        self.assertFalse(self.f.hardware.sample()['enabled'])
    def test_hardware_actual_cpu_and_memory(self):
        try:import psutil
        except ImportError:self.skipTest('Optional psutil not installed')
        self.f.prefs.update({'hardware.enabled':True});data=self.f.hardware.sample();self.assertTrue(data['enabled']);self.assertTrue(data['psutil']);self.assertGreater(data['memoryTotal'],0);self.assertGreater(data['processRSS'],0)
    def test_terminal_secret_environment_scrubbed(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'TEST_KEY','ANTHROPIC_API_KEY':'TEST_KEY','GITHUB_TOKEN':'TEST_KEY','LUMEN_KEPT':'yes'}):
            env=child_environment();self.assertNotIn('OPENAI_API_KEY',env);self.assertNotIn('GITHUB_TOKEN',env);self.assertEqual(env['LUMEN_KEPT'],'yes')
    @unittest.skipIf(os.name=='nt','POSIX test; ConPTY needs native Windows validation')
    def test_real_pty_state_resize_and_exit(self):
        self.ws.trusted=True;info=self.f.terminals.create(self.ws,'bash',True);terminal=self.f.terminals.get(info['id'])
        terminal.resize(121,31);terminal.write('export LUMEN_TEST_VALUE=7341\r')
        terminal.write('printf "CHECK_%s\\n" "$LUMEN_TEST_VALUE"; stty size\r')
        data=wait_for(lambda:terminal.read()['data'] if 'CHECK_7341' in terminal.read()['data'] and '31 121' in terminal.read()['data'] else False)
        self.assertIn('31 121',data);terminal.write('exit\r');wait_for(lambda:terminal.closed)
    @unittest.skipIf(os.name=='nt','POSIX test')
    def test_real_pty_interrupt(self):
        self.ws.trusted=True;terminal=self.f.terminals.get(self.f.terminals.create(self.ws,'bash',True)['id'])
        terminal.write('sleep 15\r');time.sleep(.3);terminal.write('\x03');terminal.write('echo INTERRUPTED_OK\r');wait_for(lambda:'INTERRUPTED_OK\r\n' in terminal.read()['data'])
    def test_terminal_trust_gate(self):
        with self.assertRaises(PermissionError):self.f.terminals.create(self.ws,'bash',True)
    def test_terminal_security_switch(self):
        self.ws.trusted=True;self.f.prefs.update({'security.terminals':False})
        with self.assertRaises(PermissionError):self.f.terminals.create(self.ws,'bash',True)
    def test_focus_queue_sequence(self):
        self.f.post('/ui/command',{'command':'lumen.focus.toggle'});self.f.post('/ui/command',{'command':'lumen.focus.toggle'});data=self.f.get('/ui/events',{'after':['0']})
        self.assertEqual([e['seq'] for e in data['events']],[1,2])
    def test_focus_queue_rejects_arbitrary_script(self):
        with self.assertRaises(ValueError):self.f.post('/ui/command',{'command':'javascript:evil'})
    def test_cloud_ai_disabled_by_default(self):
        with self.assertRaises(PermissionError):self.f.ai.start({'provider':'openai','consent':True,'question':'hi','model':'test'})
    def test_ai_explicit_consent(self):
        self.f.prefs.update({'security.cloudAI':True})
        with self.assertRaises(PermissionError):self.f.ai.start({'provider':'gemini','question':'hi','model':'test'})
    def test_ai_secret_context_denied(self):
        with self.assertRaises(PermissionError):self.f.ai.start({'provider':'ollama','consent':True,'question':'hi','model':'test','content':'secret','path':'.env'})
    def test_ai_missing_model(self):
        with self.assertRaises(ValueError):self.f.ai.start({'provider':'ollama','consent':True,'question':'hi','model':''})
    def test_ai_protocol_builders(self):
        messages=[{'role':'user','content':'hi'},{'role':'assistant','content':'hello'}]
        for provider in ('openai','anthropic','gemini','ollama'):
            path,body=build_request(provider,'test-model',messages,'system',4096);self.assertIsInstance(path,str);self.assertNotIn('api_key',json.dumps(body))
        self.assertFalse(build_request('openai','x',messages,'s',1000)[1]['store'])
        self.assertEqual(build_request('gemini','x',messages,'s',1000)[1]['contents'][1]['role'],'model')
    def test_ai_stream_protocols(self):
        self.assertEqual(stream_delta('openai',{'type':'response.output_text.delta','delta':'A'}),'A')
        self.assertEqual(stream_delta('anthropic',{'type':'content_block_delta','delta':{'text':'B'}}),'B')
        self.assertEqual(stream_delta('gemini',{'candidates':[{'content':{'parts':[{'text':'C'},{'thought':True,'text':'private'}]}}]}),'C')
        self.assertEqual(stream_delta('ollama',{'message':{'content':'D'}}),'D')
    def test_ai_provider_error_does_not_fake_answer(self):
        for provider,obj in [('openai',{'type':'error'}),('anthropic',{'type':'error'}),('gemini',{'error':{}}),('ollama',{'error':'broken'})]:
            with self.assertRaises(ValueError):stream_delta(provider,obj)
    def test_ai_mock_sse_accumulation(self):
        self.f.prefs.update({'security.cloudAI':True})
        wire=b'data: {"type":"response.output_text.delta","delta":"hello "}\n\ndata: {"type":"response.output_text.delta","delta":"world"}\n\ndata: [DONE]\n'
        with patch.object(self.f.ai,'_connection',return_value=io.BytesIO(wire)):
            info=self.f.ai.start({'provider':'openai','consent':True,'question':'hi','model':'fixture-model'});job=self.f.ai.get(info['id']);wait_for(lambda:job.done);self.assertEqual(job.text,'hello world');self.assertEqual(job.error,'')
    def test_ai_mock_error_redacts_key(self):
        with patch.object(self.f.ai,'_connection',side_effect=ValueError('bad sk-fixturekey0123456789')):
            info=self.f.ai.start({'provider':'ollama','consent':True,'question':'hi','model':'fixture-model'});job=self.f.ai.get(info['id']);wait_for(lambda:job.done);self.assertNotIn('sk-fixture',job.error);self.assertTrue(job.error)
    def test_ai_cancel_append_is_ignored(self):
        job=AIJob('ollama','test');job.append('a');job.cancel();job.append('b');self.assertEqual(job.text,'a');self.assertTrue(job.state()['cancelled'])
    def test_vault_no_plaintext_fallback(self):
        vault=CredentialVault()
        with patch.object(vault,'_native',return_value=None):
            with self.assertRaises(ValueError):vault.set('openai','TEST_ONLY_SECRET_123',True)
        self.assertFalse(vault.memory)
    def test_vault_session_forget(self):
        vault=CredentialVault()
        with patch.object(vault,'_native',return_value=None):
            vault.set('gemini','TEST_ONLY_SECRET_123');self.assertEqual(vault.get('gemini')[0],'TEST_ONLY_SECRET_123');vault.delete('gemini');self.assertNotIn('gemini',vault.memory)
    def test_ai_copilot_current_sdk_contract_mock(self):
        captured={}
        class Reject:
            def __init__(self,feedback=''):self.feedback=feedback
        class Session:
            def on(self,handler):self.handler=handler
            async def send_and_wait(self,prompt,*,timeout):
                self.assert_string=prompt;captured['prompt']=prompt
                self.handler(types.SimpleNamespace(type='assistant.message_delta',data=types.SimpleNamespace(delta_content='SDK fixture')))
                return types.SimpleNamespace(data=types.SimpleNamespace(content='SDK fixture'))
            async def abort(self):captured['aborted']=True
            async def disconnect(self):captured['disconnected']=True
        class Client:
            def __init__(self,**kwargs):captured['client']=kwargs
            async def start(self):pass
            async def stop(self):captured['stopped']=True
            async def create_session(self,**kwargs):captured['session']=kwargs;return Session()
        module=types.ModuleType('copilot');module.CopilotClient=Client;rpc=types.ModuleType('copilot.rpc');rpc.PermissionDecisionReject=Reject
        with patch.dict(sys.modules,{'copilot':module,'copilot.rpc':rpc}), patch.object(self.f.ai.accounts,'copilot_client',lambda cwd=None:Client(working_directory=cwd)):
            job=AIJob('copilot','fixture');asyncio.run(self.f.ai._copilot(job,[{'role':'user','content':'hello'}],'system'))
        self.assertEqual(job.text,'SDK fixture');self.assertIsInstance(captured['prompt'],str);self.assertEqual(captured['session']['available_tools'],[]);self.assertIsInstance(captured['session']['on_permission_request'](None,None),Reject);self.assertTrue(captured['disconnected'])
    def test_real_lsp_process_initialize_sync_complete_hover(self):
        profile={'id':'fixture','label':'Protocol fixture','argv':[sys.executable,str(ROOT/'tests/fixtures/lsp_server.py')],'languages':['python']}
        session=LanguageSession(profile,self.ws);self.addCleanup(session.close)
        uri=(self.wsroot/'hello.py').as_uri();session.notify('textDocument/didOpen',{'textDocument':{'uri':uri,'languageId':'python','version':1,'text':'print(42)'}})
        data=session.request('textDocument/completion',{'textDocument':{'uri':uri},'position':{'line':0,'character':2}})
        self.assertEqual(data['items'][0]['label'],'fixtureCompletion');self.assertEqual(session.capabilities['positionEncoding'],'utf-16')
        self.assertIn('fixture',session.request('textDocument/hover',{'textDocument':{'uri':uri},'position':{'line':0,'character':2}})['contents']['value'])
        wait_for(lambda:session.poll(0)['events'])
    def test_lsp_manager_trust_gate(self):
        with self.assertRaises(PermissionError):self.f.lsp.start(self.ws,'none',True)
    def test_installer_platform_plans(self):
        for platform in ('linux','darwin','win32'):
            app,bin=locations(platform,self.base);self.assertIsInstance(app,Path);self.assertIsInstance(bin,Path)

if __name__=='__main__':unittest.main(verbosity=2)
