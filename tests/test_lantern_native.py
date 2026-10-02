from pathlib import Path
import json,sys,tempfile,time,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.server import Application

class NativeContinuity(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.ws=self.base/'project';self.ws.mkdir()
        self.app=Application(ROOT,self.ws,data_dir=self.base/'profile');self.app.workspace.trusted=True;self.lantern=self.app.features.lantern
    def tearDown(self):
        self.app.features.shutdown();self.app.runner.shutdown();self.temp.cleanup()
    def finished(self):
        end=time.monotonic()+60
        while time.monotonic()<end:
            state=self.lantern.snapshot()
            if state.get('code') is not None or state.get('error'):return state
            time.sleep(.05)
        self.fail(str(self.lantern.snapshot()))
    def test_real_c_and_cpp_survive_recompile(self):
        for suffix in ('c','cpp'):
            code=(ROOT/f'examples/lantern/counter.{suffix}').read_text();name='counter.'+suffix
            (self.ws/name).write_text(code)
            self.lantern.start(self.app.workspace,name);a=self.finished();self.assertEqual(a.get('code'),0,a['output']);self.assertIn('LANTERN_NATIVE 1 ',a['output'])
            self.lantern.stop();(self.ws/name).write_text(code+'\n// A different executable revision\n')
            self.lantern.start(self.app.workspace,name);b=self.finished();self.assertEqual(b.get('code'),0,b['output']);self.assertIn('LANTERN_NATIVE 2 ',b['output']);self.assertEqual(b['nativeMemory']['schema'],1)
    def test_schema_migration_rejection_and_checksum(self):
        code=(ROOT/'examples/lantern/counter.c').read_text();file=self.ws/'counter.c';file.write_text(code)
        self.lantern.start(self.app.workspace,'counter.c');self.assertEqual(self.finished()['code'],0);self.lantern.stop()
        checkpoint=Path(self.lantern.snapshot()['nativeMemory']['path']);original=checkpoint.read_bytes()
        # Same-size changed schema must not silently reinterpret old fields.
        changed=code.replace('sizeof(state),1,','sizeof(state),2,').replace('sizeof(state),1)','sizeof(state),2)')
        file.write_text(changed);self.lantern.start(self.app.workspace,'counter.c');state=self.finished();self.assertEqual(state['code'],1);self.assertIn('error -2',state['output']);self.assertEqual(checkpoint.read_bytes(),original);self.lantern.stop()
        migration='int migrate(uint64_t version,const void *old,size_t old_size,void *next,size_t size){if(version!=1||old_size!=size)return 0;memcpy(next,old,size);((State*)next)->total+=100;return 1;}\n'
        file.write_text(changed.replace('int main(void)',migration+'int main(void)').replace('2,NULL','2,migrate'))
        self.lantern.start(self.app.workspace,'counter.c');state=self.finished();self.assertEqual(state['code'],0,state['output']);self.assertIn('LANTERN_NATIVE 2 105.0',state['output']);self.assertEqual(state['nativeMemory']['schema'],2);self.lantern.stop()
        damaged=bytearray(checkpoint.read_bytes());damaged[-1]^=1;checkpoint.write_bytes(damaged)
        self.lantern.start(self.app.workspace,'counter.c');state=self.finished();self.assertEqual(state['code'],1);self.assertIn('error -3',state['output']);self.assertEqual(checkpoint.read_bytes(),damaged)
    def test_cooperative_shutdown_saves_last_safe_state(self):
        code='''#include "lantern.h"
int main(void){int value=0;if(lantern_restore(&value,sizeof(value),1,NULL)<0)return 2;value+=7;
puts("READY");fflush(stdout);while(!lantern_reload_requested()){
#ifdef _WIN32
Sleep(5);
#else
usleep(5000);
#endif
}return lantern_poll(&value,sizeof(value),1)==1?0:3;}'''
        file=self.ws/'safe.c';file.write_text(code);self.lantern.start(self.app.workspace,'safe.c')
        end=time.monotonic()+20
        while 'READY' not in self.lantern.snapshot()['output'] and time.monotonic()<end:time.sleep(.05)
        self.assertIn('READY',self.lantern.snapshot()['output']);self.lantern.stop()
        self.assertEqual(self.lantern.snapshot()['history'][-1]['code'],0)
        file.write_text('#include "lantern.h"\nint main(void){int v=0;int r=lantern_restore(&v,sizeof(v),1,NULL);printf("RESTORED %d %d\\n",r,v);return 0;}')
        self.lantern.start(self.app.workspace,'safe.c');state=self.finished();self.assertIn('RESTORED 1 7',state['output'])
    def test_nc_native_json_migration_and_restart(self):
        name='counter.n';code=(ROOT/'examples/lantern/counter.n').read_text();(self.ws/name).write_text(code)
        self.lantern.start(self.app.workspace,name);state=self.finished();self.assertEqual(state.get('code'),0,state['output']);self.assertIn('LANTERN_NC 1',state['output']);self.assertEqual(state['memory']['count'],1);self.lantern.stop()
        checkpoint=Path(state['checkpoint']);checkpoint.write_text(json.dumps({'schema':1,'count':40}))
        (self.ws/name).write_text(code+'\n// Recompile and migrate version one\n')
        self.lantern.start(self.app.workspace,name);state=self.finished();self.assertEqual(state.get('code'),0,state['output']);self.assertEqual(state['memory'],{'schema':2,'count':41,'total':0});self.lantern.stop()
        self.lantern.start(self.app.workspace,name);state=self.finished();self.assertEqual(state['memory']['count'],42)

if __name__=='__main__':unittest.main()
