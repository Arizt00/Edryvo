"""0.5.3 R1 extension services in the real browser, Python server and Node host."""
import argparse,concurrent.futures,io,json,os,sys,tempfile,threading,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.server import Application,LumenServer
from tests.test_extension_053 import PLUGIN
from playwright.sync_api import sync_playwright,expect

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=True);checks=[];errors=[]
 def passed(name):checks.append(name);print('PASS',name,flush=True)
 with tempfile.TemporaryDirectory(prefix='edryvo-ui-') as folder:
  root=Path(folder);ws=root/'workspace';ws.mkdir()
  for name,text in {'main.py':'x=1\n','delete.py':'delete\n','other.py':'y=2\n','debug.py':'value=41\nprint(value+1)\n'}.items():(ws/name).write_text(text,encoding='utf-8')
  app=Application(ROOT,ws,data_dir=root/'profile');app.workspace.trusted=True;app.features.studio.update({'onboarded':True});app.features.prefs.update({'general.showWelcome':False,'appearance.motion':False,'updates.automatic':False})
  raw=io.BytesIO()
  with zipfile.ZipFile(raw,'w') as z:
   z.writestr('extension/package.json',json.dumps({'publisher':'qa','name':'services-053','version':'1.0.0','main':'main.cjs'}));z.writestr('extension/main.cjs',PLUGIN)
  store=app.features.extensions;store.install(store.inspect_bytes(raw.getvalue())['ticket'],True);os.environ['QA_PYTHON']=sys.executable
  runtime=app.features.extension_runtime;runtime.start(app.workspace,'qa.services-053',True)
  def call(name):return runtime.request(app.workspace,{'id':'qa.services-053','method':'command','command':name})['result']
  server=LumenServer(0,app);threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   with sync_playwright() as pw,concurrent.futures.ThreadPoolExecutor() as pool:
    browser=pw.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':1700,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(f'http://127.0.0.1:{server.server_port}');
    try:page.wait_for_function('window.lumen?.ready')
    except Exception:
     print('BOOT',errors,page.locator('#connection-overlay').inner_text(),flush=True);page.screenshot(path=str(out/'failure.png'));raise
    expect(page.locator('.brand-name')).to_contain_text('EDRYVO');passed('Edryvo branding and first launch load without fabricated recent files')
    page.locator('[data-file="main.py"]').click();page.wait_for_function('window.lumen.activeFile==="main.py"')
    ident=call('qa.webview');frame=page.frame_locator('.extension-webview-surface iframe');expect(frame.locator('#send')).to_be_visible();frame.locator('#send').click();expect(frame.locator('#answer')).to_have_text('42');page.screenshot(path=str(out/'webview.png'));passed('Webview JavaScript sends a message to the real extension and receives its answer')
    page.locator('[data-file="other.py"]').click();expect(page.locator('.extension-webview-surface')).to_be_hidden();expect(page.locator('.extension-webview-tab')).to_be_visible();page.locator('.extension-webview-tab').click();expect(frame.locator('#send')).to_be_visible();passed('File activation hides a webview and its tab survives the editor tab rebuild')
    page.locator('.extension-webview-surface header button').click();expect(page.locator('.extension-webview-surface')).to_have_count(0);passed('Closing a webview disposes the extension panel instead of leaving an invisible overlay')
    future=pool.submit(call,'qa.pickTask');expect(page.locator('.extension-pick-list')).to_be_visible(timeout=12000);page.get_by_role('button',name='Listado QA').click();assert future.result(timeout=12);expect(page.locator('#terminal-panel')).to_be_visible();passed('Task picker launches a registered extension task in the integrated terminal')
    call('qa.edit');page.wait_for_function('monaco.editor.getModels().some(m=>m.uri.path.endsWith("created.py")&&m.getValue().includes("nuevo ñ"))');expect(page.locator('[data-file="renamed.py"]')).to_be_visible();expect(page.locator('[data-file="delete.py"]')).to_have_count(0);assert (ws/'created.py').read_text()=='';passed('WorkspaceEdit resources refresh the explorer and text is kept unsaved')
    page.locator('[data-file="created.py"]').click();page.locator('.monaco-editor textarea').first.focus();page.keyboard.press('Control+z');page.wait_for_function('monaco.editor.getModels().find(m=>m.uri.path.endsWith("created.py")).getValue()===""');passed('WorkspaceEdit text keeps Monaco undo')
    assert call('qa.debug');page.wait_for_function('window.lumen.platformPage==="debug"',timeout=15000);page.wait_for_timeout(1000);assert app.features.debugger.snapshot()['status']=='paused';app.features.debugger.command('continue');page.wait_for_timeout(1000);assert '42' in app.features.debugger.snapshot()['output'];passed('An extension DAP adapter pauses and runs a Python program in integrated debugging')
    page.locator('[data-file="created.py"]').click()
    for width,height in [(1700,1000),(1366,768),(1280,720)]:
     page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(200)
     for selector in ['#assistant-panel','#editor-panel']:
      bounds=page.locator(selector).bounding_box();assert bounds['x']>=0 and bounds['x']+bounds['width']<=width+1
     page.screenshot(path=str(out/f'layout-{width}.png'))
    passed('Editor and assistant remain inside the work area at three desktop sizes')
    assert not errors,errors;browser.close()
  finally:server.shutdown();server.server_close();app.features.shutdown();app.runner.shutdown()
 (out/'verification.json').write_text(json.dumps({'checks':checks,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
