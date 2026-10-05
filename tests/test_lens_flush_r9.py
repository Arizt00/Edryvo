"""Completed Lens snapshots survive transient Windows sharing violations."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.lantern_lens import Lens


class LensFinalSnapshot(unittest.TestCase):
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
