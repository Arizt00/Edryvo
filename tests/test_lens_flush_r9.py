"""Completed Lens snapshots survive transient Windows sharing violations."""
import json
import os
import tempfile
import unittest
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
from backend.lantern_lens import Lens
from backend.lantern_memory import main as run_memory


class LensFinalSnapshot(unittest.TestCase):
    def test_python_final_checkpoint_retries_reader_sharing_conflicts(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'main.py';state=root/'state.json'
            source.write_text('lantern_state["count"]=1\n',encoding='utf-8')
            replace=os.replace;calls=[];path=list(sys.path)
            def busy_checkpoint(src,dst):
                if Path(dst)==state:
                    calls.append(dst)
                    if len(calls)<3:raise PermissionError('Transient checkpoint reader')
                return replace(src,dst)
            try:
                with patch('backend.lantern_memory.os.replace',side_effect=busy_checkpoint),patch('backend.lantern_memory.time.sleep'),patch.object(sys,'argv',list(sys.argv)):
                    run_memory([str(source),str(state)])
                self.assertEqual(json.loads(state.read_text())['count'],1)
                self.assertGreaterEqual(len(calls),3)
            finally:sys.path[:]=path

    @unittest.skipUnless(shutil.which('node'),'Node is required for JS checkpoint verification')
    def test_javascript_final_lens_and_memory_retry_transient_sharing_conflicts(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);state=root/'state.json';lens=root/'lens.json'
            runtime=Path(__file__).resolve().parents[1]/'backend/lantern_memory.cjs'
            script=r'''const fs=require('fs');require(process.argv[1]);let counts={};const rename=fs.renameSync;fs.renameSync=(a,b)=>{counts[b]=(counts[b]||0)+1;if(counts[b]<3){const e=Error('Transient reader');e.code='EPERM';throw e;}return rename(a,b);};lanternState.count=42;lanternLens(true,2);process.on('exit',()=>process.stdout.write(JSON.stringify({counts,state:JSON.parse(fs.readFileSync(process.env.LUMEN_LANTERN_STATE)),lens:JSON.parse(fs.readFileSync(process.env.LUMEN_LANTERN_LENS))})));'''
            result=subprocess.run([shutil.which('node'),'-e',script,str(runtime)],env={**os.environ,'LUMEN_LANTERN_STATE':str(state),'LUMEN_LANTERN_LENS':str(lens),'LUMEN_LANTERN_GENERATION':'2'},capture_output=True,text=True,timeout=10,check=True)
            data=json.loads(result.stdout);self.assertEqual(data['state']['count'],42);self.assertEqual(data['lens']['values'][0]['value'],'true')
            self.assertEqual(data['counts'][str(state)],3);self.assertEqual(data['counts'][str(lens)],3)

    def test_final_values_replace_previous_snapshot_after_reader_releases_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source=root/'main.py'; destination=root/'lens.json'
            source.write_text('answer=42\nitems=[answer,True]\n',encoding='utf-8')
            with patch.dict(os.environ,{'LUMEN_LANTERN_LENS':str(destination),'LUMEN_LANTERN_GENERATION':'1'}):
                lens=Lens(source); lens.record(1,'answer = 42'); lens.record(2,'items = [42, True]')
                replace=os.replace
                calls=[]
                def sharing_then_replace(src,dst):
                    calls.append(dst)
                    if len(calls)<3: raise PermissionError('Reader still holds destination')
                    return replace(src,dst)
                with patch('backend.lantern_lens.os.replace',side_effect=sharing_then_replace),patch('backend.lantern_lens.time.sleep'):
                    lens.flush(True)
                self.assertEqual(len(calls),3)
                self.assertTrue(any('True' in value['value'] for value in json.loads(destination.read_text(encoding='utf-8'))['values']))
                with patch('backend.lantern_lens.os.replace',side_effect=PermissionError('Still held')) as failure,patch('backend.lantern_lens.time.sleep'):
                    lens.flush(True)
                self.assertEqual(failure.call_count,8)


if __name__=='__main__': unittest.main()
