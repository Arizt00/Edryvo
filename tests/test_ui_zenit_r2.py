"""Browser windows share live buffers through the same services as native windows."""
import io,json,tempfile,threading,zipfile,sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.server import Application,LumenServer
OUT=Path(r'C:/Users/arist/Documents/Codex/2026-09-29/va/outputs/qa-053-zenit-r2')

def main():
 OUT.mkdir(parents=True,exist_ok=True);checks=[];errors=[]
 def passed(name):checks.append(name);print('PASS',name,flush=True)
 with tempfile.TemporaryDirectory(prefix='zenit-live-ui-') as temp:
  base=Path(temp);ws=base/'project';ws.mkdir();html='<!doctype html><html><head><link rel="stylesheet" href="style.css"></head><body><h1>Primera idea</h1></body></html>'
  for name,content in {'Web.html':html,'style.css':'h1 { color: rgb(10, 20, 30); }','data.csv':'nombre,valor\nuno,2\ndos,4\n','main.py':'print("DISK")\n'}.items():(ws/name).write_text(content,encoding='utf-8')
  app=Application(ROOT,ws,data_dir=base/'profile');app.workspace.trusted=True;app.features.studio.update({'onboarded':True,'workspaceStyle':'web'});app.features.prefs.update({'general.showWelcome':False,'updates.automatic':False,'appearance.motion':False,'files.autoSave':False})
  raw=io.BytesIO()
  with zipfile.ZipFile(raw,'w') as z:
   z.writestr('extension/package.json',json.dumps({'publisher':'qa','name':'icon','version':'1.0.0','displayName':'Icono propio','icon':'icon.svg'}));z.writestr('extension/icon.svg','<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" fill="#00aabb"/></svg>')
  store=app.features.extensions;store.install(store.inspect_bytes(raw.getvalue())['ticket'],True)
  server=LumenServer(0,app);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
  try:
   with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='msedge',headless=True);context=browser.new_context(viewport={'width':1500,'height':960});context.on('page',lambda p:p.on('pageerror',lambda e:errors.append(str(e))));page=context.new_page();page.goto(url);page.wait_for_function('window.lumen?.ready')
    expect(page.locator('.brand-name')).to_contain_text('ZÉNIT');page.locator('[data-file="Web.html"]').click();page.locator('[data-profile-action="preview"]').click();expect(page.frame_locator('.workspace-profile-tools iframe').locator('h1')).to_have_text('Primera idea');passed('Zénit branding and live HTML preview')
    with page.expect_popup() as popup:page.locator('[data-surface-panel="preview"]').click()
    child=popup.value;child.wait_for_function('window.lumen?.ready');expect(child.locator('.native-auxiliary-surface')).to_be_visible();expect(child.frame_locator('.workspace-profile-tools iframe').locator('h1')).to_have_text('Primera idea')
    page.evaluate('''()=>{const m=monaco.editor.getModels().find(x=>x.uri.path.endsWith('Web.html'));m.setValue(m.getValue().replace('Primera idea','Nueva creación ñ'));}''')
    expect(child.frame_locator('.workspace-profile-tools iframe').locator('h1')).to_have_text('Nueva creación ñ',timeout=15000);assert (ws/'Web.html').read_text()==html;passed('Detached preview follows unsaved HTML without touching disk')
    page.locator('[data-file="style.css"]').click();page.wait_for_function('window.lumen.activeFile==="style.css"');page.evaluate("()=>monaco.editor.getModels().find(x=>x.uri.path.endsWith('style.css')).setValue('h1 { color: rgb(90, 80, 70); }')")
    child.frame_locator('.workspace-profile-tools iframe').locator('h1').wait_for();child.wait_for_function("()=>document.querySelector('.workspace-profile-tools iframe')?.contentWindow!==null")
    expect(child.frame_locator('.workspace-profile-tools iframe').locator('h1')).to_have_css('color','rgb(90, 80, 70)',timeout=15000);passed('Detached HTML also receives unsaved CSS from another active file')
    with child.expect_event('close'):child.locator('[data-surface-panel="preview"]').click()
    expect(page.locator('.workspace-profile-tools')).to_be_visible(timeout=12000);passed('The preview detach control reattaches to the parent')
    page.locator('[data-file="Web.html"]').click();page.locator('[data-lantern="start"]').first.click();page.wait_for_function("!!document.querySelector('#lantern-inline .lantern-preview iframe')",timeout=15000)
    with page.expect_popup() as popup:page.locator('#lantern-inline [data-lantern="detach"]').click()
    lantern=popup.value;lantern.wait_for_function('window.lumen?.ready');expect(lantern.locator('.native-auxiliary-surface')).to_be_visible();revision=app.features.lantern.snapshot()['revision'];lantern.wait_for_timeout(1200);assert app.features.lantern.snapshot()['revision']==revision;passed('Detached Lantern shares the existing session without a new execution')
    page.evaluate("()=>{const m=monaco.editor.getModels().find(x=>x.uri.path.endsWith('Web.html'));m.setValue(m.getValue().replace('Nueva creación ñ','Lantern en vivo'));}")
    expect(lantern.frame_locator('.lantern-preview iframe').locator('h1')).to_have_text('Lantern en vivo',timeout=15000)
    with lantern.expect_event('close'):lantern.locator('[data-lantern="detach"]').click()
    expect(page.locator('#lantern-inline')).to_be_visible(timeout=12000);assert (ws/'Web.html').read_text()==html;passed('Lantern shows live revisions and returns without saving source')
    page.locator('[data-lantern="stop"]').first.click();app.features.studio.update({'workspaceStyle':'data'});page.reload();page.wait_for_function('window.lumen?.ready');page.locator('[data-file="data.csv"]').click();expect(page.locator('.profile-tool-heading')).to_contain_text('2 filas')
    with page.expect_popup() as popup:page.locator('.profile-detach').click()
    data=popup.value;data.wait_for_function('window.lumen?.ready');expect(data.locator('.profile-tool-heading')).to_contain_text('2 filas');data.locator('.profile-table-filter').fill('uno');expect(data.locator('.profile-table-scroll tbody tr')).to_have_count(1)
    data.evaluate("()=>monaco.editor.getModels().find(x=>x.uri.path.endsWith('data.csv')).setValue('nombre,valor\\nuno,8\\ndos,12\\n')")
    page.wait_for_function("()=>monaco.editor.getModels().find(x=>x.uri.path.endsWith('data.csv')).getValue().includes('uno,8')",timeout=15000)
    with data.expect_event('close'):data.locator('.native-return').click()
    expect(page.locator('.workspace-profile-tools')).to_be_visible();assert 'uno,2' in (ws/'data.csv').read_text();passed('Data workspace detaches, filters, edits a shared buffer and reattaches')
    for style in ['general','design','web']:
     app.features.studio.update({'workspaceStyle':style});page.reload();page.wait_for_function('window.lumen?.ready');page.locator('[data-file="Web.html"]').first.click();page.wait_for_function('window.lumen.activeFile==="Web.html"')
     with page.expect_popup() as popup:page.locator('.profile-detach').click()
     mode=popup.value;mode.wait_for_function('window.lumen?.ready');expect(mode.locator('#editor-panel')).to_be_visible();assert mode.locator('#workspace-style').input_value()==style
     if style=='design':expect(mode.locator('.workspace-profile-tools')).to_be_visible()
     if style=='web':expect(mode.frame_locator('.workspace-profile-tools iframe').locator('h1')).to_be_visible()
     with mode.expect_event('close'):mode.locator('.profile-detach').click()
     passed(style+' workspace opens as a separate shared editor and returns with the same control')
    page.locator('[data-action="extensions"]').first.click();expect(page.locator('.extension-package-icon')).to_be_visible();assert page.locator('.extension-package-icon').evaluate('(img)=>img.complete&&img.naturalWidth>0');passed('Installed extension displays its own validated icon')
    for width,height in [(1500,960),(1366,768),(1100,760)]:
     page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(150);assert page.evaluate('document.documentElement.scrollWidth')<=width;page.screenshot(path=str(OUT/f'extensions-{width}.png'))
    passed('Catalog remains framed at three desktop sizes');assert not errors,errors;browser.close()
  finally:server.shutdown();server.server_close();app.features.shutdown();app.runner.shutdown()
 (OUT/'verification.json').write_text(json.dumps({'checks':checks,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
