"""Runtime configuration, command construction and isolated preview contracts."""
import http.cookiejar
import json
from pathlib import Path
import tempfile
import sys
import time
import unittest
import urllib.request
from unittest.mock import patch
from backend.server import Application

ROOT=Path(__file__).resolve().parents[1]

class LanguageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();base=Path(self.temp.name);ws=base/'project';ws.mkdir()
        self.app=Application(ROOT,ws,data_dir=base/'profile');self.rt=self.app.features.runtimes
        self.addCleanup(self.temp.cleanup);self.addCleanup(self.app.runner.shutdown);self.addCleanup(self.app.features.shutdown)
        self.app.workspace.trusted=True
    def test_trust_before_any_generated_artifact(self):
        self.app.workspace.trusted=False
        with self.assertRaises(PermissionError):self.rt.plan(self.app.workspace,'hello.py')
        self.assertFalse((self.app.workspace.root/'.lumen/run').exists())
    def test_arguments_stay_separate_and_settings_persist(self):
        name='a file & data.n';(self.app.workspace.root/name).write_text('source')
        value={'languages':{'nc':{'run':['compiler','run','${file}'],'check':['compiler','check','${file}']}}}
        self.rt.save(value);plan=self.rt.plan(self.app.workspace,name)
        self.assertEqual(plan['commands'],[['compiler','run',str(self.app.workspace.root/name)]])
        self.assertEqual(self.rt.plan(self.app.workspace,name,check=True)['commands'][0][1],'check')
        self.assertEqual(json.loads(self.rt.path.read_text())['languages'],value['languages'])
    def test_running_program_accepts_standard_input(self):
        file=self.app.workspace.root/'input.py';file.write_text('print("READY",flush=True)\nx=input()\nprint("REPLY",x)\n')
        job=self.app.runner.jobs[self.app.runner.start([[sys.executable,'-u',str(file)]],self.app.workspace.root)['job']]
        end=time.monotonic()+8
        while 'READY' not in job.output and time.monotonic()<end:time.sleep(.03)
        job.write('Lumen\n')
        while not job.done and time.monotonic()<end:time.sleep(.03)
        self.assertTrue(job.done);self.assertEqual(job.code,0);self.assertIn('REPLY Lumen',job.output)
    def test_bad_configuration_does_not_replace_saved_profile(self):
        before=self.rt.config
        for data in ({'languages':{'madeup':{}}},{'languages':{'c':{'run':'gcc file.c'}}},{'languages':{'c':{'debug':{'adapter':['lldb-dap'],'transport':'remote'}}}},{'languages':{},'tools':{'ncc':123}}):
            with self.assertRaises(ValueError):self.rt.save(data)
        self.assertEqual(self.rt.config,before)
    def test_missing_sdk_reports_actionable_error(self):
        (self.app.workspace.root/'hello.go').write_text('package main')
        with patch('backend.runtimes.find_tool',return_value=None):
            with self.assertRaisesRegex(ValueError,'Falta go'):self.rt.plan(self.app.workspace,'hello.go')
    def test_preview_separate_origin_root_assets_and_path_boundaries(self):
        ws=self.app.workspace
        (ws.root/'index.html').write_text('<link rel="stylesheet" href="/style.css">')
        (ws.root/'style.css').write_text('h1{color:red}')
        (ws.root/'.env').write_text('private-test')
        result=self.app.features.preview.start(ws,'style.css');base=result['url'].split('/'+self.app.features.preview.token)[0]
        jar=http.cookiejar.CookieJar();client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        with client.open(result['url']) as response:self.assertIn(b'link',response.read())
        with client.open(base+'/style.css') as response:self.assertEqual(response.read(),b'h1{color:red}')
        for url in (base+'/.env',base+'/../outside',base+'/style.css'):
            opener=urllib.request.urlopen if url.endswith('style.css') else client.open
            with self.assertRaises(urllib.error.HTTPError):opener(url)
        ws.trusted=False
        with self.assertRaises(PermissionError):self.app.features.preview.start(ws,'index.html')

if __name__=='__main__':unittest.main()
