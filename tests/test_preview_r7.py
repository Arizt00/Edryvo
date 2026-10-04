"""Persistence, shared-document conflicts, real PTYs and update verification."""
from pathlib import Path
import hashlib,io,json,os,tempfile,time,unittest,zipfile,threading,subprocess,sys,urllib.request,http.cookiejar
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch
from backend.server import Application
from backend.preferences import Preferences
from backend.session import last_workspace,remember_workspace
from backend.extensions import ExtensionStore
from backend.extension_runtime import ExtensionRuntime
from backend.workspace import Workspace
from backend.buffers import Buffers
from backend.runtime_paths import find_tool
from backend.updates import Updates,update_asset,version_key
from backend.downloads import Downloads
ROOT=Path(__file__).resolve().parents[1]

def wait_for(fn,timeout=20):
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        value=fn()
        if value:return value
        time.sleep(.08)
    raise AssertionError('Timed out waiting for a real operation')

def package(name='r7-test'):
    raw=io.BytesIO()
    with zipfile.ZipFile(raw,'w') as z:
        z.writestr('extension/package.json',json.dumps({'publisher':'lumen','name':name,'displayName':'Extensión ñ','version':'1.0.0','main':'main.cjs'}))
        z.writestr('extension/main.cjs',"const v=require('vscode');exports.activate=()=>{v.commands.registerCommand('r7.files',async()=>{const files=await v.workspace.findFiles('**/*.py');return files.map(x=>x.fsPath);});v.commands.registerCommand('r7.write',async()=>{const uri=v.Uri.joinPath(v.workspace.workspaceFolders[0].uri,'nuevo.py');await v.workspace.fs.writeFile(uri,Buffer.from('áéíóú ñ'));return (await v.workspace.fs.readFile(uri)).toString();});};")
    return raw.getvalue()

class PreviewR7(unittest.TestCase):
    def test_application_reopens_last_folder_after_actual_process_restart(self):
        with tempfile.TemporaryDirectory(prefix='lumen-restart-r7-') as t:
            base=Path(t);profile=base/'profile';first=base/'first';second=base/'Código ñ';first.mkdir();second.mkdir()
            Preferences(profile).update({'updates.automatic':False})
            remember_workspace(first,profile)
            def launch():
                instance=profile/'instance.json';instance.unlink(missing_ok=True)
                process=subprocess.Popen([sys.executable,str(ROOT/'app.py'),'--no-browser','--port','0'],cwd=ROOT,env={**os.environ,'LUMEN_DATA_DIR':str(profile)},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                try:
                    wait_for(instance.exists);url=json.loads(instance.read_text(encoding='utf-8'))['url']
                    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()));opener.open(url).close()
                    with opener.open(url+'/api/bootstrap') as response:token=json.load(response)['token']
                    def api(path,body=None,expected=None):
                        from urllib.parse import quote
                        headers={'X-Lumen-Token':token,'Content-Type':'application/json'}
                        if expected:headers['X-Lumen-Workspace']=quote(str(expected))
                        request=urllib.request.Request(url+'/api'+path,data=json.dumps(body).encode() if body else None,headers=headers)
                        with opener.open(request,timeout=10) as response:return json.load(response)
                    return process,api
                except Exception:process.terminate();process.wait(timeout=5);raise
            process,api=launch()
            try:
                self.assertEqual(api('/state')['workspace'],str(first.resolve()))
                api('/workspace',{'path':str(second)})
                from urllib.error import HTTPError
                with self.assertRaises(HTTPError) as conflict:api('/save',{'path':'main.py','content':'stale window'},first)
                self.assertEqual(conflict.exception.code,409);self.assertFalse((second/'main.py').exists())
            finally:process.terminate();process.wait(timeout=5)
            process,api=launch()
            try:self.assertEqual(api('/state')['workspace'],str(second.resolve()))
            finally:process.terminate();process.wait(timeout=5)

    def test_two_process_stores_do_not_overwrite_each_others_installs(self):
        with tempfile.TemporaryDirectory() as t:
            prefs=Preferences(Path(t));one=ExtensionStore(prefs);two=ExtensionStore(prefs)
            a=one.inspect_bytes(package('first'));b=two.inspect_bytes(package('second'))
            one.install(a['ticket'],True);two.install(b['ticket'],True)
            self.assertEqual({x['id'] for x in one.list()},{'lumen.first','lumen.second'})
            one.update_state('lumen.first',False);two.update_state('lumen.second',False)
            self.assertTrue(all(not x['enabled'] for x in ExtensionStore(prefs).list()))
    def test_workspace_restoration_and_missing_folder(self):
        with tempfile.TemporaryDirectory() as t:
            base=Path(t);ws=base/'Código ñ';ws.mkdir();profile=base/'profile'
            self.assertIsNone(last_workspace(profile));remember_workspace(ws,profile)
            self.assertEqual(last_workspace(profile),ws.resolve());ws.rmdir();self.assertIsNone(last_workspace(profile))
            prefs=Preferences(profile);self.assertTrue(prefs.get('general.restoreWorkspace'))
            prefs.update({'general.restoreWorkspace':False});self.assertFalse(Preferences(profile).get('general.restoreWorkspace'))

    def test_installed_extensions_recover_and_remain_disabled(self):
        with tempfile.TemporaryDirectory() as t:
            prefs=Preferences(Path(t));store=ExtensionStore(prefs);ticket=store.inspect_bytes(package());store.install(ticket['ticket'],True)
            self.assertEqual(ExtensionStore(prefs).list()[0]['displayName'],'Extensión ñ')
            store.update_state('lumen.r7-test',False);store.index.write_bytes(b'broken')
            restored=ExtensionStore(prefs);self.assertFalse(restored.installed['lumen.r7-test']['enabled'])
            restored.update_state('lumen.r7-test',remove=True);self.assertEqual(ExtensionStore(prefs).list(),[])

    @unittest.skipUnless(find_tool('node'),'Node required')
    def test_extension_authorization_restores_real_process_and_filesystem(self):
        with tempfile.TemporaryDirectory() as t:
            base=Path(t);ws=base/'project';ws.mkdir();(ws/'main.py').write_text('print(1)')
            prefs=Preferences(base/'profile');store=ExtensionStore(prefs);ticket=store.inspect_bytes(package());store.install(ticket['ticket'],True)
            workspace=Workspace(ws,None);workspace.trusted=True;runtime=ExtensionRuntime(store)
            try:
                runtime.start(workspace,'lumen.r7-test',True)
                call=lambda cmd:runtime.request(workspace,{'id':'lumen.r7-test','method':'command','command':cmd})['result']
                self.assertIn(str(ws/'main.py'),call('r7.files'));self.assertEqual(call('r7.write'),'áéíóú ñ')
                runtime.shutdown();runtime=ExtensionRuntime(ExtensionStore(prefs))
                self.assertTrue(runtime.restore(workspace)['hosts'][0]['running'])
                runtime.stop('lumen.r7-test',forget=True);self.assertEqual(runtime.restore(workspace)['hosts'],[])
            finally:runtime.shutdown()

    def test_buffer_conflicts_preserve_winning_version_and_disk(self):
        with tempfile.TemporaryDirectory() as t:
            ws=Workspace(Path(t),None);(ws.root/'main.py').write_text('DISK');hub=Buffers()
            first=hub.update(ws,{'path':'main.py','text':'first','sequence':0})
            second=hub.update(ws,{'path':'main.py','text':'second','sequence':first['buffer']['sequence']})
            conflict=hub.update(ws,{'path':'main.py','text':'stale','sequence':first['buffer']['sequence']})
            self.assertTrue(conflict['conflict']);self.assertEqual(conflict['buffer']['text'],'second')
            self.assertEqual((ws.root/'main.py').read_text(),'DISK');hub.clear();self.assertEqual(hub.snapshot()['buffers'],[])

    def test_python_hacker_uses_unsaved_buffer_and_original_imports(self):
        with tempfile.TemporaryDirectory() as t:
            base=Path(t);ws=base/'project';ws.mkdir();(ws/'script.py').write_text('print("DISK")');(ws/'helper.py').write_text('message="UNSAVED ñ"',encoding='utf-8')
            app=Application(ROOT,ws,data_dir=base/'profile');app.workspace.trusted=True
            try:
                result=app.features.hacker.start(app.workspace,'script.py','from helper import message\nprint(message)\n','python')
                terminal=app.features.terminals.get(result['terminal']['id'])
                text=wait_for(lambda:(data if 'UNSAVED ñ' in (data:=terminal.read(0)['data']) else None))
                self.assertIn('UNSAVED ñ',text);self.assertEqual((ws/'script.py').read_text(),'print("DISK")')
            finally:app.features.shutdown();app.runner.shutdown()

    @unittest.skipUnless(find_tool('gcc') and find_tool('gdb'),'GCC/GDB required')
    def test_gcc_gdb_hacker_stops_at_main_and_inspects_variable(self):
        with tempfile.TemporaryDirectory() as t:
            base=Path(t);ws=base/'project';ws.mkdir();(ws/'example.c').write_text('DISK')
            app=Application(ROOT,ws,data_dir=base/'profile');app.workspace.trusted=True
            try:
                code='#include <stdio.h>\nint main(void) {\n int answer=42;\n printf("%d\\n",answer);\n return 0;\n}\n'
                result=app.features.hacker.start(app.workspace,'example.c',code,'gdb');job=app.runner.jobs[result['job']]
                wait_for(lambda:job.done);self.assertEqual(job.code,0,job.output)
                terminal=app.features.terminals.get(app.features.hacker.attach(app.workspace,result['job'])['id'])
                wait_for(lambda:'(gdb)' in terminal.read(0)['data']);terminal.write('next\r');time.sleep(.2);terminal.write('next\r');time.sleep(.2);terminal.write('print answer\r')
                wait_for(lambda:'= 42' in terminal.read(0)['data']);self.assertEqual((ws/'example.c').read_text(),'DISK')
            finally:app.features.shutdown();app.runner.shutdown()

    def test_update_selects_only_newer_verified_official_installer(self):
        asset={'name':'LumenStudio-Setup-0.5.2-R8.exe','size':100,'digest':'sha256:'+'a'*64,'browser_download_url':'https://github.com/Arizt00/LumenStudio/releases/download/v0.5.2-preview.8/LumenStudio-Setup-0.5.2-R8.exe'}
        release={'tag_name':'v0.5.2-preview.8','html_url':'https://github.com/Arizt00/LumenStudio/releases/tag/v0.5.2-preview.8','assets':[asset]}
        self.assertEqual(update_asset([release],'v0.5.2-preview.7','win32','AMD64')['version'],release['tag_name']);self.assertIsNone(update_asset([release],release['tag_name']))
        self.assertIsNone(update_asset([{**release,'draft':True}]))
        self.assertIsNone(update_asset([{**release,'assets':[{**asset,'digest':None}]}]))
        self.assertIsNone(update_asset([{**release,'assets':[{**asset,'browser_download_url':'https://example.com/setup.exe'}]}]))
        self.assertGreater(version_key('v0.5.2'),version_key('v0.5.2-preview.999'))

    def test_background_update_download_verifies_before_install_and_rejects_tampering(self):
        payload=b'MZ'+b'Lumen test installer\x00'*2000
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200);self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as t:
                prefs=Preferences(Path(t));downloads=Downloads(Path(t));updater=Updates(prefs,downloads)
                asset={'version':'v0.5.2-preview.8','name':'LumenStudio-Setup-R8.exe','url':f'http://127.0.0.1:{server.server_port}/setup.exe','sha256':hashlib.sha256(payload).hexdigest(),'size':len(payload)}
                updater.data['available']=asset;updater.download();wait_for(lambda:updater.snapshot()['status']=='ready')
                with patch('backend.updates.sys.platform','win32'),patch('backend.updates.platform.machine',return_value='AMD64'):
                    installer=updater.installer();self.assertEqual(installer.read_bytes(),payload)
                    installer.write_bytes(b'changed');self.assertRaises(ValueError,updater.installer)
                updater.shutdown();downloads.shutdown()
        finally:server.shutdown();server.server_close()

if __name__=='__main__':unittest.main()
