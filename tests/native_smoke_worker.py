"""Run with the packaged lumen-python helper, using its embedded modules/runtime."""
import argparse
import json
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path
import webview
from backend.server import Application, LumenServer
from backend.desktop import DesktopAPI
from backend.version import REVISION


def until(fn,timeout=60):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        try:
            result=fn()
            if result:return result
        except Exception:pass
        time.sleep(.15)
    raise AssertionError('Packaged native operation timed out')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    root=Path(sys._MEIPASS);checks=[];errors=[]
    with tempfile.TemporaryDirectory(prefix='lumen-native-package-') as temp:
        base=Path(temp);workspace=base/'project';workspace.mkdir();file=workspace/'first.py';file.write_text('print("DISK")\n',encoding='utf-8')
        app=Application(root,workspace,data_dir=base/'profile');app.workspace.trusted=True
        app.features.studio.update({'onboarded':True});app.features.prefs.update({'general.showWelcome':False,'updates.automatic':False,'appearance.motion':False})
        server=LumenServer(0,app);threading.Thread(target=server.serve_forever,daemon=True).start()
        url=f'http://127.0.0.1:{server.server_port}';api=DesktopAPI();api._application=app;api._url=url
        api._window=webview.create_window('Lumen native package verification',url,js_api=api,width=1300,height=850,hidden=True)
        def verify():
            try:
                until(lambda:api._window.evaluate_js('!!window.lumen?.ready'))
                assert api.status()['revision']==REVISION
                assert api._window.evaluate_js('window.lumen.editorKind')=='monaco'
                assert api._window.evaluate_js('document.querySelector(".brand-tagline").textContent').endswith('R'+str(REVISION))
                checks.append('Packaged runtime, Monaco and native JS bridge')
                assert app.native.lib is not None,app.native.name
                checks.append('Native C/C++ core loaded')
                app.features.buffers.update(app.workspace,{'path':'first.py','text':'print("LUMEN NATIVE R8 ñ",flush=True)\n','sequence':0})
                api.detach_panel('forge','first.py');forge=api._children['forge']
                until(lambda:forge.evaluate_js('!!window.lumen?.ready'))
                assert forge.evaluate_js('document.documentElement.dataset.detachedPanel')=='forge'
                forge.evaluate_js("window.__qaErrors=[];window.addEventListener('error',e=>__qaErrors.push(e.message))")
                until(lambda:forge.evaluate_js('!document.querySelector("[data-action=hacker-python]").disabled'))
                forge.evaluate_js('document.querySelector("[data-action=hacker-python]").click()')
                until(lambda:any('LUMEN NATIVE R8 ñ' in session.read(0)['data'] for session in app.features.terminals.sessions.values()))
                until(lambda:forge.evaluate_js("!!document.querySelector('.xterm-screen')"))
                assert not forge.evaluate_js('window.__qaErrors')
                assert file.read_text(encoding='utf-8')=='print("DISK")\n'
                checks.append('Separate Forge window executes unsaved UTF-8 Python in real PTY')
                forge.evaluate_js('document.querySelector("[data-action=forge-terminal]").click()')
                until(lambda:'forge' not in api._children)
                checks.append('Forge returns to Lumen without replacing the source file')
                print(json.dumps({'checks':checks,'errors':errors}),flush=True)
            except Exception:errors.append(traceback.format_exc());print(errors[-1],flush=True)
            finally:
                for window in list(webview.windows):
                    try:window.destroy()
                    except Exception:pass
        try:webview.start(verify,gui='qt' if sys.platform.startswith('linux') else 'edgechromium' if sys.platform=='win32' else 'cocoa',private_mode=True,storage_path=str(base/'webview'))
        finally:
            server.shutdown();server.server_close();app.features.shutdown();app.runner.shutdown()
            args.report.parent.mkdir(parents=True,exist_ok=True)
            args.report.write_text(json.dumps({'platform':sys.platform,'revision':REVISION,'checks':checks,'errors':errors},indent=2),encoding='utf-8')
        if errors or len(checks)!=4:raise AssertionError('Packaged desktop verification failed')

if __name__=='__main__':main()
