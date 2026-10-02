"""R6 UI regressions with a real local backend and Node extension.

Only AI transport is deterministic: this checks consent and buffer ownership,
not model quality. All documents/profile data are disposable synthetic fixtures.
"""
from pathlib import Path
import argparse,io,json,sys,tempfile,threading,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.server import Application,LumenServer
from playwright.sync_api import sync_playwright,expect

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);out=p.parse_args().output;out.mkdir(parents=True,exist_ok=True)
 checks=[];errors=[];page=None
 def passed(name):checks.append(name);print('PASS',name,flush=True)
 with tempfile.TemporaryDirectory(prefix='lumen-r6-') as temp:
  base=Path(temp);ws=base/'Project';ws.mkdir()
  (ws/'example.py').write_text('print("Hola, Lumen")\n',encoding='utf-8');(ws/'other.py').write_text('print("OTHER")\n',encoding='utf-8')
  (ws/'Demo.java').write_text('class Demo {\n public static void main(String[] args) {\n try { System.out.println("Hola"); }\n }\n}',encoding='utf-8')
  app=Application(ROOT,ws,data_dir=base/'profile');app.workspace.trusted=True;app.features.studio.update({'onboarded':True});app.features.prefs.update({'general.showWelcome':False,'ai.provider':'ollama','ai.model':'r6-fixture','files.autoSave':False,'general.locale':'es'})
  raw=io.BytesIO()
  with zipfile.ZipFile(raw,'w') as z:
   z.writestr('extension/package.json',json.dumps({'publisher':'lumen','name':'r6-qa','displayName':'Ocean · R6 QA','version':'1.0.0','main':'main.cjs','contributes':{'themes':[{'label':'Ocean','uiTheme':'vs-dark','path':'themes/ocean.json'}]}}))
   z.writestr('extension/themes/base.json',json.dumps({'colors':{'editor.foreground':'#e2edf6','sideBar.background':'#172c3d','terminal.foreground':'#9ae5bd','focusBorder':'#54c7ec'}}))
   z.writestr('extension/themes/ocean.json',json.dumps({'include':'base.json','colors':{'editor.background':'#0d202f','titleBar.activeBackground':'#102536','input.background':'#173044','list.activeSelectionBackground':'#204158'}}))
   z.writestr('extension/main.cjs',"const v=require('vscode');exports.activate=()=>{v.workspace.onWillSaveTextDocument(e=>{if(!e.document.getText().startsWith('# formatted'))e.waitUntil(Promise.resolve([v.TextEdit.insert(new v.Position(0,0),'# formatted · ñ\\n')]));});v.workspace.onDidSaveTextDocument(d=>{require('fs').writeFileSync(require('path').join(require('path').dirname(d.uri.fsPath),'saved-event.json'),JSON.stringify({dirty:d.isDirty,text:d.getText()}));});};")
  review=app.features.extensions.inspect_bytes(raw.getvalue());app.features.extensions.install(review['ticket'],True)
  server=LumenServer(0,app);threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='msedge',headless=True,args=['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist'])
    page=browser.new_page(viewport={'width':1672,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)))
    def open_file(name):
     page.keyboard.press('Escape');page.keyboard.press('Control+k');page.locator('#palette-input').fill(name);page.locator('.palette-result').filter(has_text=name).first.click();page.wait_for_function('(name)=>window.lumen.activeFile===name',arg=name)
    def buffer():return page.evaluate('monaco.editor.getModels().find(m=>m.uri.path.endsWith(window.lumen.activeFile)).getValue()')
    def replace(text):
     page.locator('.monaco-editor textarea').first.focus();page.keyboard.press('Control+a');page.keyboard.insert_text(text)
    page.goto(f'http://127.0.0.1:{server.server_port}',wait_until='networkidle');page.wait_for_function('window.lumen?.ready')
    if page.locator('.home-enter').is_visible():page.locator('.home-enter').click()
    open_file('example.py')
    # Right-click near the editor boundary; the menu must escape panel clipping.
    box=page.locator('#editor-mount').bounding_box();page.mouse.click(box['x']+box['width']-130,box['y']+90,button='right')
    page.screenshot(path=str(out/'r6-context-probe.png'));menu=page.locator('.monaco-menu .monaco-action-bar.vertical:visible');expect(menu).to_be_visible();expect(menu).to_contain_text('Copiar');assert 'Copy' not in menu.inner_text()
    bounds=menu.bounding_box();assert bounds['x']>=0 and bounds['x']+bounds['width']<=1672
    assert menu.evaluate('(e)=>{const b=e.getBoundingClientRect(),root=e.getRootNode();return e.contains(root.elementFromPoint(b.right-12,b.top+16))}')
    assert menu.evaluate('e=>getComputedStyle(e).backgroundColor')!='rgba(0, 0, 0, 0)'
    page.screenshot(path=str(out/'r6-context-menu.png'));page.keyboard.press('Escape');passed('Spanish editor menu fits viewport and stays above the assistant without clipping')
    page.locator('[data-action=extensions]:visible').first.click();page.locator('[data-external-theme]').first.click();page.wait_for_function('document.documentElement.dataset.extensionTheme')
    assert app.features.prefs.get('appearance.extensionTheme')=='lumen.r6-qa:Ocean'
    values=page.evaluate("Object.fromEntries(['editor','surface','terminal-text','header'].map(k=>[k,getComputedStyle(document.documentElement).getPropertyValue('--'+k).trim()]))")
    assert values=={'editor':'#0d202f','surface':'#172c3d','terminal-text':'#9ae5bd','header':'#102536'},values
    page.screenshot(path=str(out/'r6-theme.png'));page.reload(wait_until='networkidle');page.wait_for_function('window.lumen?.ready && document.documentElement.dataset.extensionTheme');passed('Installed theme inheritance colors the shell, editor and terminal and survives reload')
    if page.locator('.home-enter').is_visible():page.locator('.home-enter').click()
    page.locator('[data-action=settings]:visible').first.click();page.locator('[data-setting-category=appearance]').click();page.locator('[data-platform-theme=day]').click();page.wait_for_function('!document.documentElement.dataset.extensionTheme');assert app.features.prefs.get('appearance.extensionTheme')=='';page.keyboard.press('Escape');passed('Selecting a built-in theme clears every extension override')
    page.locator('[data-action=extensions]:visible').first.click();page.locator('[data-extension-execute="lumen.r6-qa"]').click();page.get_by_role('button',name='Autorizar motor',exact=True).click();expect(page.locator('[data-extension-execute="lumen.r6-qa"]')).to_have_text('Detener motor')
    open_file('example.py');replace('print("áéíóú ñ")\n');page.keyboard.press('Control+s');page.wait_for_timeout(700)
    saved=(ws/'example.py').read_text(encoding='utf-8');assert saved.startswith('# formatted · ñ\n'),saved
    event=json.loads((ws/'saved-event.json').read_text(encoding='utf-8'));assert event=={'dirty':False,'text':saved},repr((event,saved));assert buffer()==saved;passed('Executable extension formats before save and receives did-save only after the Unicode buffer is saved')
    open_file('Demo.java');page.keyboard.press('Control+Alt+l');expect(page.locator('#lantern-inline [data-lantern-status]')).to_have_text('Esperando código válido',timeout=25000)
    page.wait_for_function('monaco.editor.getModelMarkers({}).some(m=>m.source==="Java" && m.startLineNumber===3)')
    page.locator('.debug-button').click();expect(page.locator('#lantern-inline')).not_to_be_visible();expect(page.locator('#lantern-workbench')).to_be_visible();expect(page.locator('#lantern-workbench [data-lantern-summary]')).to_contain_text('1 diagnósticos');page.screenshot(path=str(out/'r6-java-diagnostics.png'));passed('Java try-without-catch is reported at the source line and the inline monitor never overlays Debug')
    page.keyboard.press('Escape');expect(page.locator('#lantern-inline')).to_be_visible();page.locator('#lantern-inline [data-lantern=stop]').click();page.locator('#lantern-inline [data-lantern=close-inline]').click()
    open_file('example.py');before=buffer();sent=[];stage=[0];release=[False]
    def start(route):sent.append(route.request.post_data_json);stage[0]=0;route.fulfill(json={'id':'r6-stream'})
    def job(route):
     if stage[0]==0:stage[0]=1;delta='```python\nprint("GENERANDO")\n';done=False
     elif release[0]:delta='print("EN SEGUNDO PLANO")\n```';done=True
     else:delta='';done=False
     route.fulfill(json={'delta':delta,'offset':stage[0],'done':done})
    page.route('**/api/platform/ai/start',start);page.route('**/api/platform/ai/job?*',job);page.route('**/api/platform/ai/cancel',lambda r:r.fulfill(json={'ok':True}))
    page.locator('#ai-input').fill('Escribe el código en vivo');page.locator('#ai-form .send-button').click();page.get_by_role('button',name='Enviar esta petición',exact=True).click();page.get_by_role('button',name='Permitir esta edición',exact=True).click()
    page.wait_for_function('monaco.editor.getModels().some(m=>m.getValue().includes("GENERANDO"))');open_file('other.py');other=buffer();release[0]=True;expect(page.locator('#ai-form .send-button')).to_be_enabled(timeout=15000)
    assert buffer()==other;assert (ws/'example.py').read_text(encoding='utf-8')==before;open_file('example.py');assert 'EN SEGUNDO PLANO' in buffer();passed('Natural-language live writing requires permission and completes in the original background buffer without saving')
    before=buffer();page.unroute('**/api/platform/ai/job?*');page.route('**/api/platform/ai/job?*',lambda route:route.fulfill(json={'delta':'```python\nprint("DO_NOT_APPLY")\n```','offset':1,'done':True}))
    page.locator('#ai-input').fill('Explica cómo funciona este código');page.locator('#ai-form .send-button').click();page.get_by_role('button',name='Enviar esta petición',exact=True).click();expect(page.locator('#ai-form .send-button')).to_be_enabled();assert buffer()==before;assert 'EDICIÓN EN VIVO AUTORIZADA' not in sent[-1]['question'];passed('Explanation following live editing remains read-only even when the model returns code')
    assert not errors,errors;passed('No uncaught browser errors');browser.close()
  finally:
   server.shutdown();server.server_close();app.features.shutdown();app.runner.shutdown();(out/'r6-ui-verification.json').write_text(json.dumps({'checks':checks,'errors':errors},indent=2),encoding='utf-8')
if __name__=='__main__':main()
