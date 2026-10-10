"""Run with the packaged zenit-python helper, using its embedded modules/runtime."""
import argparse
import concurrent.futures
import io
import json
import sys
import tempfile
import threading
import time
import traceback
import zipfile
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


def focus_native(window):
    if sys.platform.startswith('linux'):
        # Xvfb has no window manager to focus newly opened windows. Give the
        # actual X window focus; do not bypass document.hasFocus() in the app.
        import ctypes
        from webview.platforms.qt import BrowserView
        x11=ctypes.CDLL('libX11.so.6');x11.XOpenDisplay.argtypes=[ctypes.c_char_p];x11.XOpenDisplay.restype=ctypes.c_void_p
        x11.XSetInputFocus.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong]
        x11.XFlush.argtypes=[ctypes.c_void_p];x11.XCloseDisplay.argtypes=[ctypes.c_void_p]
        display=x11.XOpenDisplay(None)
        if not display:raise AssertionError('Xvfb display unavailable')
        try:x11.XSetInputFocus(display,int(BrowserView.instances[window.uid].winId()),2,0);x11.XFlush(display)
        finally:x11.XCloseDisplay(display)
    window.evaluate_js('monaco.editor.getEditors().find(e=>e.getModel()).focus()')
    until(lambda:window.evaluate_js('document.hasFocus()'))


def main():
    javascript_errors=[]
    if sys.platform.startswith('linux'):
        from webview.platforms.qt import BrowserView
        original_console=BrowserView.WebPage.javaScriptConsoleMessage
        def console(page,level,message,line,source):
            if 'Error' in str(level):javascript_errors.append({'source':source,'line':line,'message':message})
            original_console(page,level,message,line,source)
        BrowserView.WebPage.javaScriptConsoleMessage=console
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
                focus_native(data)
                assert data.evaluate_js("document.querySelector('.profile-table-filter').getBoundingClientRect().width>50")
                data.evaluate_js("monaco.editor.getModels().find(m=>m.uri.path.endsWith('data.csv')).setValue('name,value\\none,8\\n')")
                until(lambda:parent.evaluate_js("monaco.editor.getModels().find(m=>m.uri.path.endsWith('data.csv')).getValue().includes('one,8')"))
                # Require the new adapter from the frozen package and use its actual UI.
                raw=io.BytesIO()
                with zipfile.ZipFile(raw,'w') as z:
                    z.writestr('extension/package.json',json.dumps({'publisher':'qa','name':'native-input','version':'1.0.0','main':'main.cjs'}))
                    z.writestr('extension/main.cjs',"const v=require('vscode');exports.activate=()=>{v.commands.registerCommand('qa.nativeViews',()=>v.window.visibleTextEditors.map(e=>({path:e.document.uri.fsPath,ranges:e.visibleRanges.length})));return v.commands.registerCommand('qa.nativeInput',()=>v.window.showInputBox({title:'Entrada nativa',validateInput:value=>value.length<3?'Tres letras':undefined}));};")
                store=app.features.extensions;store.install(store.inspect_bytes(raw.getvalue())['ticket'],True)
                runtime=app.features.extension_runtime;runtime.start(app.workspace,'qa.native-input',True)
                until(lambda:any(x['ranges']>0 and x['path'].endswith('data.csv') for x in runtime.request(app.workspace,{'id':'qa.native-input','method':'command','command':'qa.nativeViews'})['result']))
                checks.append('Packaged Monaco sends actual visible editor ranges to the Node extension')
                data.evaluate_js("document.querySelector('.profile-detach').click()")
                until(lambda:'profile-data' not in api._children)
                assert (workspace/'data.csv').read_text(encoding='utf-8')=='name,value\none,2\n'
                checks.append('Native development mode shares edits and reattaches with the same control')
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result=pool.submit(runtime.request,app.workspace,{'id':'qa.native-input','method':'command','command':'qa.nativeInput'})
                    until(lambda:parent.evaluate_js("document.querySelector('#zenit-quick-title')?.textContent==='Entrada nativa'"))
                    parent.evaluate_js("const input=document.querySelector('.zenit-quick-field input');input.value='proyecto ñ';input.dispatchEvent(new Event('input',{bubbles:true}))")
                    until(lambda:parent.evaluate_js("document.querySelector('.zenit-quick-validation')?.textContent===''"))
                    parent.evaluate_js("document.querySelector('.zenit-quick-accept').click()")
                    assert result.result(20)['result']=='proyecto ñ'
                until(lambda:parent.evaluate_js("!document.querySelector('.zenit-quickinput')"))
                checks.append('Packaged QuickInput receives native UI text and returns it to the real extension')
                def dependency_package(name,dependencies=()):
                    raw=io.BytesIO()
                    with zipfile.ZipFile(raw,'w') as z:
                        z.writestr('extension/package.json',json.dumps({'publisher':'qa','name':name,'version':'1.0.0','license':'MIT','main':'main.cjs','extensionDependencies':list(dependencies)}))
                        z.writestr('extension/main.cjs',"exports.activate=c=>({sum:(a,b)=>a+b,id:c.extension.id});" if name=='native-child' else "const v=require('vscode');exports.activate=async()=>{const child=await v.extensions.getExtension('qa.native-child').activate();v.commands.registerCommand('qa.nativeSum',()=>({sum:child.sum(7,5),owner:child.id}));};")
                    return raw.getvalue()
                original=store.inspect_remote
                try:
                    store.inspect_remote=lambda eid,**kw:store.inspect_bytes(dependency_package('native-child'),'Open VSX')
                    root_review=store.inspect_bytes(dependency_package('native-plan',['qa.native-child']))
                    plan=store.prepare_plan(root_review['ticket']);assert len(plan['packages'])==2
                    store.install_plan(plan['plan'],True)
                    assert {'qa.native-child','qa.native-plan'}<=set(type(store)(store.prefs).installed)
                    runtime.start(app.workspace,'qa.native-plan',True)
                    assert runtime.request(app.workspace,{'id':'qa.native-plan','method':'command','command':'qa.nativeSum'})['result']=={'sum':12,'owner':'qa.native-child'}
                finally:store.inspect_remote=original
                checks.append('Packaged dependency plan persists packages and shares real function exports with their parent')
                assert not javascript_errors,javascript_errors
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
            args.report.write_text(json.dumps({'platform':sys.platform,'revision':REVISION,'checks':checks,'errors':errors,'javascriptErrors':javascript_errors},indent=2),encoding='utf-8')
        if errors or len(checks)!=12:raise AssertionError('Packaged desktop verification failed')

if __name__=='__main__':main()
