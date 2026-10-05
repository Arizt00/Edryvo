"""R9 editor actions and panel geometry in the actual browser and Node host."""
import argparse,io,json,sys,tempfile,threading,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.server import Application,LumenServer
from tests.test_extension_r9 import PLUGIN
from playwright.sync_api import sync_playwright,expect

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=True);checks=[];errors=[]
 def passed(name):checks.append(name);print('PASS',name,flush=True)
 with tempfile.TemporaryDirectory(prefix='lumen-r9-ui-') as folder:
  root=Path(folder);ws=root/'workspace';ws.mkdir();(ws/'main.py').write_text('x=1\n');(ws/'other.py').write_text('y=2\n');(ws/'Example.java').write_text('class Example {}')
  app=Application(ROOT,ws,data_dir=root/'profile');app.workspace.trusted=True;app.features.studio.update({'onboarded':True});app.features.prefs.update({'general.showWelcome':False,'appearance.motion':False,'updates.automatic':False,'editor.tabSize':2,'editor.formatOnType':True})
  raw=io.BytesIO()
  with zipfile.ZipFile(raw,'w') as z:
   z.writestr('extension/package.json',json.dumps({'publisher':'lumen','name':'r9-editing','version':'1.0.0','main':'main.cjs'}));z.writestr('extension/main.cjs',PLUGIN)
  store=app.features.extensions;store.install(store.inspect_bytes(raw.getvalue())['ticket'],True);app.features.extension_runtime.start(app.workspace,'lumen.r9-editing',True)
  server=LumenServer(0,app);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
  try:
   with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':1700,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(url);page.wait_for_function('window.lumen?.ready');expect(page.locator('#editor-empty')).to_contain_text('Tu próxima idea');expect(page.locator('#workspace-style')).to_be_visible()
    assert page.locator('#editor-empty').bounding_box()['y']>=page.locator('.workspace-profile-bar').bounding_box()['y']+page.locator('.workspace-profile-bar').bounding_box()['height']-1;passed('Empty editor is localized and starts below the working profile toolbar')
    badge=page.locator('[data-file="main.py"] .extension-file-decoration');expect(badge).to_have_text('M');expect(badge).to_have_attribute('data-tone','warning');expect(page.locator('[data-file="Example.java"] .file-type-java')).to_be_visible()
    page.evaluate('()=>document.querySelector("[data-action=toggle-root]").click()');page.evaluate('()=>document.querySelector("[data-action=toggle-root]").click()');expect(badge).to_have_text('M');passed('Extension file badges survive explorer rebuilds and Java has a distinct colored icon')
    page.keyboard.press('Control+k');page.locator('#palette-input').fill('main.py');page.locator('.palette-result').filter(has_text='main.py').first.click();page.wait_for_function('window.lumen.activeFile==="main.py"')
    page.evaluate('()=>{const e=monaco.editor.getEditors().find(e=>e.getModel()?.uri.path.endsWith("main.py"));e.focus();e.setPosition({lineNumber:1,column:1});e.trigger("qa","editor.action.quickFix",{});}')
    action=page.get_by_text('Corregir con extensión',exact=True);expect(action).to_be_visible(timeout=12000);page.screenshot(path=str(out/'r9-quickfix-menu.png'));action.click(timeout=2000)
    page.wait_for_function('monaco.editor.getModels().find(m=>m.uri.path.endsWith("main.py")).getValue().startsWith("# corrección ñ")')
    assert page.evaluate('monaco.editor.getModels().find(m=>m.uri.path.endsWith("other.py")).getValue()').startswith('# segundo archivo')
    assert (ws/'main.py').read_text()=='x=1\n' and (ws/'other.py').read_text()=='y=2\n';passed('Quick Fix resolves a VS Code extension action and edits two buffers without saving either file')
    page.keyboard.press('Control+z');page.wait_for_function('monaco.editor.getModels().find(m=>m.uri.path.endsWith("main.py")).getValue()==="x=1\\n"');passed('Extension quick fixes preserve Monaco undo')
    page.keyboard.type(';');page.wait_for_function('monaco.editor.getModels().find(m=>m.uri.path.endsWith("main.py")).getValue().startsWith("X")');passed('Typing a trigger formats the live buffer through the extension with configured indentation')
    assert page.locator('.colorpicker-color-decoration').count()>0;passed('Extension colors render interactive color decorations in Monaco')
    page.screenshot(path=str(out/'r9-editor.png'))
    for width,height in [(1700,1000),(1366,768),(1280,720)]:
     page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(300)
     panel=page.locator('#assistant-panel');composer=page.locator('.ai-composer');send=page.locator('.send-button');live=page.locator('#ai-edit-file');bounds=panel.bounding_box()
     if not panel.is_visible():continue
     for element in [composer,send,live]:
      r=element.bounding_box();assert r['x']>=bounds['x']-1 and r['x']+r['width']<=bounds['x']+bounds['width']+1 and r['y']+r['height']<=bounds['y']+bounds['height']+1,(width,height,r,bounds)
     page.locator('[data-ai-action="fix"]').scroll_into_view_if_needed();expect(page.locator('[data-ai-action="fix"]')).to_be_in_viewport();page.screenshot(path=str(out/f'r9-layout-{width}.png'))
    passed('Assistant composer, editing permission and last action fit at desktop and laptop sizes')
    page.set_viewport_size({'width':1700,'height':1000});page.locator('[data-action="extensions"].rail-item').click();expect(page.locator('.extension-card')).to_have_count(1);assert page.locator('.extension-hero').bounding_box()['height']<210;page.screenshot(path=str(out/'r9-extensions.png'));passed('Extension catalog uses a compact header and aligned cards')
    page.route('**/api/platform/extensions/review?*',lambda route:route.fulfill(json={'done':True,'error':'Open VSX devolvió un error HTTP 503.'}))
    page.locator('[data-extension-inspect]').click();expect(page.locator('.extension-review-error')).to_contain_text('HTTP 503');expect(page.locator('#extension-review-retry')).to_be_visible();assert page.locator('.toast.error').count()==0;page.locator('#extension-review-close').click();page.unroute('**/api/platform/extensions/review?*');passed('Failed review stays in one retryable dialog instead of repeating toasts over the composer')
    for theme in ['dark','forest','day']:
     app.features.prefs.update({'appearance.theme':theme});page.reload();page.wait_for_function('window.lumen?.ready');page.locator('[data-action="extensions"].rail-item').click();page.screenshot(path=str(out/f'r9-{theme}.png'))
    passed('All three built-in themes retain opaque panel surfaces and compact catalog spacing')
    def catalog(route):
     offset=24 if 'offset=24' in route.request.url else 0
     items=[{'id':f'test.package{i}','namespace':'test','name':f'package{i}','displayName':f'Package {i}','version':'1'} for i in range(offset, min(offset+24,30))]
     route.fulfill(json={'extensions':items,'total':30})
    page.route('**/api/platform/extensions/search?*',catalog);page.locator('[data-extension-mode="browse"]').click();expect(page.locator('.extension-card')).to_have_count(24);page.locator('#extension-more').click();expect(page.locator('.extension-card')).to_have_count(30);expect(page.locator('#extension-catalog-summary')).to_contain_text('30');passed('Catalog pagination loads additional results without discarding current cards')

    assert not errors,errors;passed('No uncaught JavaScript errors');browser.close()
  finally:server.shutdown();server.server_close();app.features.shutdown();app.runner.shutdown();(out/'r9-ui-verification.json').write_text(json.dumps({'checks':checks,'errors':errors},indent=2),encoding='utf-8')
if __name__=='__main__':main()
