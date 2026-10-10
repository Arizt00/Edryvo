import json,tempfile,threading,unittest
from pathlib import Path
from backend.checkpoint_io import read_checkpoint
from backend.preferences import atomic_json


class CheckpointReads(unittest.TestCase):
    def test_monitor_does_not_block_atomic_program_checkpoints(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.json';atomic_json(path,{'revision':0,'payload':'ñ'*2000})
            done=threading.Event();errors=[];seen=[]
            def monitor():
                while not done.is_set():
                    try:seen.append(json.loads(read_checkpoint(path,10000))['revision'])
                    except Exception as error:errors.append(error);break
            reader=threading.Thread(target=monitor);reader.start()
            try:
                for revision in range(1,51):atomic_json(path,{'revision':revision,'payload':'ñ'*2000})
            finally:done.set();reader.join(5)
            self.assertFalse(errors);self.assertTrue(seen)
            self.assertEqual(json.loads(read_checkpoint(path,10000))['revision'],50)
    def test_read_limits_and_missing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.json';path.write_bytes(b'x'*101)
            with self.assertRaises(ValueError):read_checkpoint(path,100)
            self.assertEqual(read_checkpoint(path,101),b'x'*101)
            with self.assertRaises(OSError):read_checkpoint(path.with_name('missing'),100)

if __name__=='__main__':unittest.main()
