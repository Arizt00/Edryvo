"""Regression coverage for the installer waits and AI cancellation reported by the user."""
import sys
import threading
import time
import unittest
from unittest.mock import patch
from installer import Installer
from installer import InstallerAPI
from backend.desktop import DesktopAPI
from backend.providers import AIJob, AIRouter
from backend.preferences import Preferences
import tempfile
import os
import subprocess
from pathlib import Path
from backend.runner import Job

@unittest.skipUnless(os.name=='nt','Windows console attachment regression')
class HiddenProcessTests(unittest.TestCase):
    def test_integrated_tasks_have_no_external_console_and_keep_output(self):
        code='import ctypes; print("CONSOLE_HANDLE="+str(ctypes.windll.kernel32.GetConsoleWindow()))'
        with tempfile.TemporaryDirectory() as directory:
            for shell in (False,True):
                with self.subTest(shell=shell):
                    command=[sys.executable,'-c',code]
                    job=Job('console-check',[subprocess.list2cmdline(command) if shell else command],Path(directory),shell=shell)
                    job.run()
                    self.assertEqual(job.code,0,job.output)
                    self.assertIn('CONSOLE_HANDLE=0',job.output.splitlines())

class InstallerResponsivenessTests(unittest.TestCase):
    def test_native_bridges_expose_operations_not_internal_objects(self):
        for bridge in (InstallerAPI(Installer()), DesktopAPI()):
            public = [getattr(bridge, name) for name in dir(bridge) if not name.startswith('_')]
            self.assertTrue(public)
            self.assertTrue(all(callable(value) for value in public))

    def test_silent_process_has_a_deadline(self):
        installer=Installer();start=time.monotonic()
        code,output,reason=installer._run_tool([sys.executable,'-c','import time;time.sleep(60)'],timeout=.2)
        self.assertEqual(reason,'tiempo de espera agotado');self.assertNotEqual(code,0)
        self.assertLess(time.monotonic()-start,5)

    def test_skip_interrupts_only_owned_process(self):
        installer=Installer();installer.state['phase']='tools'
        timer=threading.Timer(.2,installer.skip_tools);timer.start()
        _,_,reason=installer._run_tool([sys.executable,'-c','import time;time.sleep(60)'])
        timer.join();self.assertEqual(reason,'omitido')

    def test_existing_sdk_is_not_reinstalled(self):
        installer=Installer();installer.state['packages']=[{'id':'python','status':'pending'}]
        with patch('installer.shutil.which',return_value='winget'),patch.object(installer,'_run_tool',return_value=(0,'Python.Python.3.12 3.12.10','')) as run:
            installer._install_tools(['python'])
        self.assertEqual(run.call_count,1);self.assertEqual(installer.state['packages'][0]['status'],'available')

    def test_skip_preserves_pending_tool_visibility(self):
        installer=Installer();installer.skip.set();installer.state['packages']=[{'id':'java','status':'pending'}]
        with patch.object(installer,'_run_tool') as run:installer._install_tools(['java'])
        run.assert_not_called();self.assertEqual(installer.state['packages'][0]['status'],'skipped')

class AIResponsivenessTests(unittest.TestCase):
    def test_cancel_does_not_wait_for_blocked_socket_reader(self):
        gate=threading.Event()
        class Response:
            def close(self):gate.wait(3)
        job=AIJob('ollama','test');job.response=Response();start=time.monotonic()
        job.cancel();self.assertLess(time.monotonic()-start,.2)
        self.assertTrue(job.state()['done']);self.assertTrue(job.state()['cancelled']);gate.set()

    def test_emma_is_local_and_catalog_uses_configured_folder(self):
        with tempfile.TemporaryDirectory() as d:
            router=AIRouter(Preferences(d))
            with patch('backend.emma.models',return_value={'models':['local-model']}) as probe:
                self.assertEqual(router.models('emma',True)['models'],['local-model'])
                probe.assert_called_once_with(router.prefs.get('ai.emmaDirectory'))
            with self.assertRaises(PermissionError):router.models('emma',False)

if __name__=='__main__':unittest.main()
