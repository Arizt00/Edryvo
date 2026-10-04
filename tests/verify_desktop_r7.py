"""Real WebView2 multiwindow probe; all fixtures/windows use an isolated profile."""
from pathlib import Path
import argparse,json,sys,tempfile,threading,time,traceback
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import webview
from backend.server import Application,LumenServer
from backend.desktop import DesktopAPI

def until(fn,timeout=35):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  try:
   value=fn()
   if value:return value
  except Exception:pass
  time.sleep(.15)
 raise AssertionError('Native window operation timed out')

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True);checks=[];failure=[]
 with tempfile.TemporaryDirectory(prefix='lumen-native-r7-') as t:
  base=Path(t);ws=base/'project';ws.mkdir();(ws/'first.py').write_text('print("DISK")\n')
  app=Application(ROOT,ws,data_dir=base/'profile');app.workspace.trusted=True;app.features.studio.update({'onboarded':True});app.features.prefs.update({'general.showWelcome':False,'updates.automatic':False})
  server=LumenServer(0,app);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}';api=DesktopAPI();api._application=app;api._url=url
  real_create=webview.create_window
  # Exercise native windows offscreen/hidden without interrupting the user's app.
  def create(*a,**kw):return real_create(*a,**{**kw,'hidden':True})
  webview.create_window=create
  api._window=create('Lumen R7 isolated QA',url,js_api=api,width=1300,height=900)
  def check():
   try:
    until(lambda:api._window.evaluate_js('!!window.lumen?.ready'))
    app.features.buffers.update(app.workspace,{'path':'first.py','text':'print("NATIVE UNSAVED")\n','sequence':0})
    api.detach_panel('editor','first.py');child=api._children['editor:first.py'];until(lambda:child.evaluate_js('!!window.lumen?.ready'))
    info=child.evaluate_js('({panel:document.documentElement.dataset.detachedPanel,path:window.lumen.activeFile,text:monaco.editor.getModels().find(m=>m.uri.path.endsWith("first.py")).getValue(),bridge:!!window.pywebview?.api?.detach_panel})')
    assert info=={'panel':'editor','path':'first.py','text':'print("NATIVE UNSAVED")\n','bridge':True},info
    child.move(1900,60);child.resize(900,700)
    checks.append('Native WebView2 editor receives unsaved buffer and can move outside the parent window');print('PASS',checks[-1],flush=True)
    api.detach_panel('editor','first.py');assert len(api._children)==1
    api.detach_panel('assistant','first.py');assistant=api._children['assistant'];until(lambda:assistant.evaluate_js('!!window.lumen?.ready'))
    assert assistant.evaluate_js('!document.querySelector("#assistant-panel").inert && !document.querySelector("#assistant-panel").hidden')
    assistant.evaluate_js('document.querySelector("#assistant-panel textarea").value="Consulta de prueba";document.querySelector("#assistant-panel textarea").focus()')
    assistant.resize(520,600)
    assert assistant.evaluate_js('document.activeElement.matches("#assistant-panel textarea") && document.querySelector("#assistant-panel").parentElement.id==="app"')
    assistant.destroy();until(lambda:'assistant' not in api._children)
    checks.append('Native assistant remains interactive and detached after layout changes');print('PASS',checks[-1],flush=True)
    term=app.features.hacker.start(app.workspace,'first.py','import time\nprint("NATIVE TERMINAL",flush=True)\ntime.sleep(60)\n','python')['terminal']
    api.detach_panel('console');console=api._children['console'];until(lambda:console.evaluate_js('!!window.lumen?.ready'))
    assert console.evaluate_js('document.querySelector(".pty-session-tabs").textContent.includes("Python")')
    console.destroy();until(lambda:'console' not in api._children)
    assert not app.features.terminals.get(term['id']).closed
    checks.append('Native terminal attaches to the existing PTY and closing its window leaves the process running');print('PASS',checks[-1],flush=True)
    api.detach_panel('forge','first.py');forge=api._children['forge'];until(lambda:forge.evaluate_js('!!window.lumen?.ready'))
    assert forge.evaluate_js('document.documentElement.dataset.detachedPanel==="forge" && document.querySelector(".forge-file").textContent==="first.py" && !document.querySelector("[data-action=hacker-python]").disabled')
    forge.move(1920,60);forge.resize(680,720);forge.evaluate_js('document.querySelector("[data-action=hacker-python]").click()')
    until(lambda:any('NATIVE UNSAVED' in s.read(0)['data'] for s in app.features.terminals.sessions.values()))
    assert (ws/'first.py').read_text()=='print("DISK")\n';forge.evaluate_js('document.querySelector("[data-action=forge-terminal]").click()');until(lambda:'forge' not in api._children)
    checks.append('Native Forge window executes the shared unsaved buffer outside the parent and preserves the disk file');print('PASS',checks[-1],flush=True)
    child.destroy();until(lambda:not api._children)
    checks.append('Closing native windows releases their registry and returns the parent panel');print('PASS',checks[-1],flush=True)
   except Exception:failure.append(traceback.format_exc());print(failure[-1],flush=True)
   finally:
    for window in list(webview.windows):
     try:window.destroy()
     except Exception:pass
  try:webview.start(check,gui='edgechromium',private_mode=True,storage_path=str(base/'webview'))
  finally:server.shutdown();server.server_close();app.features.shutdown();app.runner.shutdown();(args.output/'r7-native-verification.json').write_text(json.dumps({'checks':checks,'errors':failure},indent=2),encoding='utf-8')
  if failure:raise AssertionError('Native verification failed')
if __name__=='__main__':main()
