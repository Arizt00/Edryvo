"""R4 integration contracts: real processes, checkpointing, range HTTP and executable VSIX."""
from pathlib import Path
import hashlib,io,json,sys,tempfile,threading,time,unittest,zipfile
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.server import Application
from backend.downloads import Downloads,MAX_DOWNLOAD

def until(fn,seconds=15):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        value=fn()
        if value:return value
        time.sleep(.04)
    raise AssertionError('Expected state not reached')

class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.ws=self.base/'project';self.ws.mkdir()
        self.app=Application(ROOT,self.ws,data_dir=self.base/'profile');self.app.workspace.trusted=True
    def tearDown(self):
        self.app.features.shutdown();self.app.runner.shutdown();time.sleep(.1);self.temp.cleanup()
    def test_python_memory_survives_revisions_and_file_switch(self):
        code='lantern_state["count"]=lantern_state.get("count",0)+1\nprint(lantern_state["count"])\n'
        (self.ws/'main.py').write_text(code);(self.ws/'other.py').write_text('print(lantern_state)')
        # Use a helper with assignment outside conditional to avoid testing a synthetic runtime.
        def completed():
            s=self.app.features.lantern.snapshot();return s if s.get('code')==0 else None
        self.app.features.lantern.start(self.app.workspace,'main.py');first=until(completed);self.assertEqual(first['memory']['count'],1)
        self.app.features.lantern.restart();until(lambda:self.app.features.lantern.snapshot()['revision']>first['revision']);second=until(completed);self.assertEqual(second['memory']['count'],2)
        self.app.features.lantern.start(self.app.workspace,'other.py');until(completed)
        self.app.features.lantern.start(self.app.workspace,'main.py');third=until(completed);self.assertEqual(third['memory']['count'],3);self.assertGreaterEqual(len(third['history']),2)
    def test_javascript_memory_survives_process_replacement(self):
        (self.ws/'main.js').write_text('lanternState.count=(lanternState.count||0)+1;console.log(lanternState.count)')
        def completed():
            s=self.app.features.lantern.snapshot();return s if s.get('code')==0 else None
        self.app.features.lantern.start(self.app.workspace,'main.js');a=until(completed);self.assertEqual(a['memory']['count'],1)
        self.app.features.lantern.start(self.app.workspace,'main.js');b=until(completed);self.assertEqual(b['memory']['count'],2)
    def test_executable_extension_commands_and_language_providers(self):
        raw=io.BytesIO()
        with zipfile.ZipFile(raw,'w') as z:
            z.writestr('extension/package.json',json.dumps({'publisher':'lumen','name':'preview-test','version':'1.0.0','main':'main.cjs'}))
            z.writestr('extension/main.cjs',"exports.activate=(context,lumen)=>{lumen.registerCommand('uppercase',doc=>({text:doc.text.toUpperCase()}));lumen.registerInlayHintsProvider('python',()=>[{position:{line:0,character:3},label:': int'}]);lumen.registerCompletionProvider('python',()=>[{label:'hello',insertText:'hello()'}]);};")
        store=self.app.features.extensions;review=store.inspect_bytes(raw.getvalue());self.assertIn('runtime',review['supported']);store.install(review['ticket'],True)
        host=self.app.features.extension_runtime
        (self.ws/'a.py').write_text('hello')
        with self.assertRaises(PermissionError):host.start(self.app.workspace,'lumen.preview-test',False)
        capabilities=host.start(self.app.workspace,'lumen.preview-test',True);self.assertTrue(capabilities['hosts'][0]['running'])
        base={'id':'lumen.preview-test','document':{'path':'a.py','text':'hello','language':'python'}}
        self.assertEqual(host.request(self.app.workspace,{**base,'method':'command','command':'uppercase'})['result']['text'],'HELLO')
        self.assertEqual(host.request(self.app.workspace,{**base,'method':'provide','kind':'inlay'})['items'][0]['label'],': int')
        self.assertEqual(host.request(self.app.workspace,{**base,'method':'provide','kind':'completion'})['items'][0]['insertText'],'hello()')
        host.stop('lumen.preview-test');self.assertEqual(host.snapshot()['hosts'],[])

class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.manager=Downloads(Path(self.temp.name));self.payload=b'R4-download-test\0'*600000;self.ranges=[]
        outer=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                if self.path=='/huge':self.send_response(200);self.send_header('Content-Length',str(MAX_DOWNLOAD+1));self.end_headers();return
                start=int(self.headers.get('Range','bytes=0-').split('=')[1].split('-')[0]);outer.ranges.append((start,self.headers.get('If-Range')))
                self.send_response(206 if start else 200);self.send_header('ETag','"revision-one"');self.send_header('Content-Length',str(len(outer.payload)-start))
                if start:self.send_header('Content-Range',f'bytes {start}-{len(outer.payload)-1}/{len(outer.payload)}')
                self.end_headers()
                try:
                    for offset in range(start,len(outer.payload),128000):self.wfile.write(outer.payload[offset:offset+128000]);self.wfile.flush();time.sleep(.006)
                except OSError:pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=self.server.serve_forever,daemon=True).start();self.url=f'http://127.0.0.1:{self.server.server_port}'
    def tearDown(self):
        self.manager.shutdown()
        for thread in self.manager.threads.values():thread.join(3)
        self.server.shutdown();self.server.server_close();self.temp.cleanup()
    def test_pause_resume_sha_and_no_full_memory_buffer(self):
        self.manager.start(self.url+'/sdk','sdk.zip',hashlib.sha256(self.payload).hexdigest());key=next(iter(self.manager.items))
        until(lambda:self.manager.items[key]['bytes']>1_000_000);self.manager.pause(key);until(lambda:self.manager.items[key]['status']=='paused');self.manager.threads[key].join(2)
        # A fresh manager simulates restarting Lumen between download segments.
        self.manager=Downloads(Path(self.temp.name));self.manager.resume(key);until(lambda:self.manager.items[key]['status']=='complete')
        self.assertEqual((self.manager.root/'sdk.zip').read_bytes(),self.payload);self.assertTrue(any(start>0 and tag=='"revision-one"' for start,tag in self.ranges))
    def test_500gb_limit_enforced_before_reading_body(self):
        self.manager.start(self.url+'/huge','huge.zip');key=next(iter(self.manager.items));until(lambda:self.manager.items[key]['status']=='error')
        self.assertIn('500 GB',self.manager.items[key]['error']);self.assertEqual(self.manager.items[key]['bytes'],0)
    def test_bad_hash_never_publishes_executable(self):
        self.manager.start(self.url+'/sdk','sdk.exe','0'*64);key=next(iter(self.manager.items));until(lambda:self.manager.items[key]['status']=='error');self.assertFalse((self.manager.root/'sdk.exe').exists())

if __name__=='__main__':unittest.main()
