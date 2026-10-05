"""Run with the packaged zenit-python helper, using its embedded modules/runtime."""
import argparse
import json
import sys
import tempfile
import threading
import time
import traceback
from urllib.request import urlopen
from pathlib import Path
import webview
from backend.server import Application, LumenServer
from backend.desktop import DesktopAPI
from backend.version import PRODUCT_NAME, REVISION


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
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]));checks=[];errors=[]
    with tempfile.TemporaryDirectory(prefix='lumen-native-package-') as temp:
        base=Path(temp);workspace=base/'project';workspace.mkdir();file=workspace/'first.py';file.write_text('print("DISK")\n',encoding='utf-8')
        html='<!doctype html><html><body><h1>DISK</h1></body></html>'
        (workspace/'Web.html').write_text(html,encoding='utf-8')
        (workspace/'data.csv').write_text('name,value\none,2\n',encoding='utf-8')
        app=Application(root,workspace,data_dir=base/'profile');app.workspace.trusted=True
        app.features.studio.update({'onboarded':True});app.features.prefs.update({'general.showWelcome':False,'updates.automatic':False,'appearance.motion':False})
        server=LumenServer(0,app);threading.Thread(target=server.serve_forever,daemon=True).start()
        url=f'http://127.0.0.1:{server.server_port}';api=DesktopAPI();api._application=app;api._url=url
        # Qt exits when its last visible child closes if the parent stays hidden.
        # Linux QA runs in its own Xvfb display, so keep its parent visible there.
        api._window=webview.create_window(PRODUCT_NAME+' native package verification',url,js_api=api,width=1300,height=850,hidden=sys.platform!='linux')
        def verify():
            try:
                until(lambda:api._window.evaluate_js('!!window.lumen?.ready'))
                assert api.status()['revision']==REVISION
                assert api._window.evaluate_js('window.lumen.editorKind')=='monaco'
                assert api._window.evaluate_js('document.title').startswith(PRODUCT_NAME)
                assert api._window.evaluate_js('document.querySelector(".brand-tagline").textContent').endswith('R'+str(REVISION))
                checks.append('Packaged runtime, Monaco and native JS bridge')
                assert app.native.lib is not None,app.native.name
                checks.append('Native C/C++ core loaded')
                app.features.buffers.update(app.workspace,{'path':'first.py','text':'print("ZENIT NATIVE R2 ñ",flush=True)\n','sequence':0})
                api.detach_panel('forge','first.py');forge=api._children['forge']
                until(lambda:forge.evaluate_js('!!window.lumen?.ready'))
                assert forge.evaluate_js('document.documentElement.dataset.detachedPanel')=='forge'
                forge.evaluate_js("window.__qaErrors=[];window.addEventListener('error',e=>__qaErrors.push(e.message))")
                until(lambda:forge.evaluate_js('!document.querySelector("[data-action=hacker-python]").disabled'))
                forge.evaluate_js('document.querySelector("[data-action=hacker-python]").click()')
                until(lambda:any('ZENIT NATIVE R2 ñ' in session.read(0)['data'] for session in app.features.terminals.sessions.values()))
                until(lambda:forge.evaluate_js("!!document.querySelector('.xterm-screen')"))
                assert not forge.evaluate_js('window.__qaErrors')
                assert file.read_text(encoding='utf-8')=='print("DISK")\n'
                checks.append('Separate Forge window executes unsaved UTF-8 Python in real PTY')
                forge.evaluate_js('document.querySelector("[data-action=forge-terminal]").click()')
                until(lambda:'forge' not in api._children)
                checks.append('Forge returns to '+PRODUCT_NAME+' without replacing the source file')
                parent=api._window
                parent.evaluate_js("document.querySelector('[data-file=\"Web.html\"]').click()")
                until(lambda:parent.evaluate_js("window.lumen.activeFile==='Web.html'"))
                parent.evaluate_js("const select=document.querySelector('#workspace-style');select.value='web';select.dispatchEvent(new Event('change'))")
                until(lambda:parent.evaluate_js("document.documentElement.dataset.workspaceStyle==='web'"))
                parent.evaluate_js("document.querySelector('[data-profile-action=preview]').click()")
                until(lambda:parent.evaluate_js("!!document.querySelector('.workspace-profile-tools iframe')"))
                parent.evaluate_js("document.querySelector('[data-surface-panel=preview]').click()")
                preview=until(lambda:api._children.get('preview'))
                until(lambda:preview.evaluate_js('!!window.lumen?.ready'))
                assert preview.evaluate_js("document.querySelector('.native-auxiliary-surface').getBoundingClientRect().height>100")
                parent.evaluate_js("monaco.editor.getModels().find(m=>m.uri.path.endsWith('Web.html')).setValue('<!doctype html><h1>NATIVE LIVE</h1>')")
                def rendered(window,selector,marker):
                    source=window.evaluate_js(f"document.querySelector({json.dumps(selector)})?.src")
                    return source and marker in urlopen(source,timeout=3).read().decode('utf-8')
                until(lambda:rendered(preview,'.workspace-profile-tools iframe','NATIVE LIVE'))
                assert (workspace/'Web.html').read_text(encoding='utf-8')==html
                checks.append('Native web preview receives unsaved HTML in its separate desktop window')
                preview.evaluate_js("document.querySelector('[data-surface-panel=preview]').click()")
                until(lambda:'preview' not in api._children)
                until(lambda:parent.evaluate_js("!document.querySelector('.workspace-profile-tools').hidden"))
                checks.append('Same preview control reattaches the live surface to the main native window')
                parent.evaluate_js("document.querySelector('[data-lantern=start]').click()")
                until(lambda:app.features.lantern.snapshot().get('preview'))
                parent.evaluate_js("document.querySelector('#lantern-inline [data-lantern=detach]').click()")
                lantern=until(lambda:api._children.get('lantern'))
                until(lambda:lantern.evaluate_js('!!window.lumen?.ready'))
                revision=app.features.lantern.snapshot()['revision'];time.sleep(1)
                assert app.features.lantern.snapshot()['revision']==revision
                checks.append('Native Lantern shares the active session without a duplicate execution')
                parent.evaluate_js("monaco.editor.getModels().find(m=>m.uri.path.endsWith('Web.html')).setValue('<!doctype html><h1>LANTERN LIVE</h1>')")
                until(lambda:rendered(lantern,'.lantern-preview iframe','LANTERN LIVE'))
                lantern.evaluate_js("document.querySelector('[data-lantern=detach]').click()")
                until(lambda:'lantern' not in api._children)
                until(lambda:parent.evaluate_js("!document.querySelector('#lantern-inline').hidden"))
                assert (workspace/'Web.html').read_text(encoding='utf-8')==html
                checks.append('Native Lantern updates in vivo and returns without saving the source')
                parent.evaluate_js("document.querySelector('[data-lantern=stop]').click();document.querySelector('[data-file=\"data.csv\"]').click()")
                until(lambda:parent.evaluate_js("window.lumen.activeFile==='data.csv'"))
                parent.evaluate_js("const select=document.querySelector('#workspace-style');select.value='data';select.dispatchEvent(new Event('change'))")
                until(lambda:parent.evaluate_js("document.documentElement.dataset.workspaceStyle==='data'"))
                parent.evaluate_js("document.querySelector('.profile-detach').click()")
                data=until(lambda:api._children.get('profile-data'))
                until(lambda:data.evaluate_js('!!window.lumen?.ready'))
                assert data.evaluate_js("document.querySelector('.profile-table-filter').getBoundingClientRect().width>50")
                data.evaluate_js("monaco.editor.getModels().find(m=>m.uri.path.endsWith('data.csv')).setValue('name,value\\none,8\\n')")
                until(lambda:parent.evaluate_js("monaco.editor.getModels().find(m=>m.uri.path.endsWith('data.csv')).getValue().includes('one,8')"))
                data.evaluate_js("document.querySelector('.profile-detach').click()")
                until(lambda:'profile-data' not in api._children)
                assert (workspace/'data.csv').read_text(encoding='utf-8')=='name,value\none,2\n'
                checks.append('Native development mode shares edits and reattaches with the same control')
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
        if errors or len(checks)!=9:raise AssertionError('Packaged desktop verification failed')

if __name__=='__main__':main()
