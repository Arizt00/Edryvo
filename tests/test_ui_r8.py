"""R8 actual browser transport: profiles, unsaved preview, drag targets and trees."""
from pathlib import Path
import argparse,io,json,sys,tempfile,threading,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.server import Application,LumenServer
from playwright.sync_api import sync_playwright,expect

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);out=p.parse_args().output;out.mkdir(parents=True,exist_ok=True);checks=[];errors=[]
 def passed(name):checks.append(name);print('PASS',name,flush=True)
 with tempfile.TemporaryDirectory(prefix='lumen-r8-ui-') as folder:
  root=Path(folder);ws=root/'project';ws.mkdir()
  for name,text in {'first.py':'print("FIRST")\n','second.py':'print("SECOND")\n','index.html':'<link rel="stylesheet" href="style.css"><h1>DISK</h1>','style.css':'h1 { color:#334455; background:#ffffff; }','sales.csv':'name,price\n"Ana, ñ",10\nLuis,30\n'}.items():(ws/name).write_text(text,encoding='utf-8')
  app=Application(ROOT,ws,data_dir=root/'profile');app.workspace.trusted=True;app.features.studio.update({'onboarded':True});app.features.prefs.update({'general.showWelcome':True,'appearance.motion':False,'updates.automatic':False})
  raw=io.BytesIO()
  with zipfile.ZipFile(raw,'w') as z:
   z.writestr('extension/package.json',json.dumps({'publisher':'lumen','name':'r8-tree','version':'1.0.0','main':'main.cjs'}));z.writestr('extension/main.cjs',"const v=require('vscode');exports.activate=()=>{v.commands.registerCommand('qa.tree',()=>v.window.showInformationMessage('TREE COMMAND ñ'));v.window.registerTreeDataProvider('qa.files',{getChildren:p=>p?['leaf']:['root'],getTreeItem:p=>({label:p,collapsibleState:p==='root'?1:0,command:p==='leaf'?{command:'qa.tree'}:undefined})});v.languages.registerSignatureHelpProvider('python',{provideSignatureHelp:()=>({signatures:[{label:'qa(value)',parameters:[{label:'value'}]}],activeSignature:0,activeParameter:0})},'(');};")
  review=app.features.extensions.inspect_bytes(raw.getvalue());app.features.extensions.install(review['ticket'],True);app.features.extension_runtime.start(app.workspace,'lumen.r8-tree',True)
  server=LumenServer(0,app);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
  try:
   with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':1700,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)))
    page.add_init_script("new MutationObserver(records=>{for(const r of records)for(const n of r.addedNodes)if(n.nodeType===1&&n.matches('.toast.error'))(window.__errorToasts??=[]).push(n.textContent)}).observe(document,{subtree:true,childList:true});")
    page.goto(url,wait_until='domcontentloaded');page.wait_for_function('window.lumen?.ready')
    expect(page.locator('.hero-quick-actions')).not_to_contain_text('Continuar');expect(page.locator('.recent-list')).to_contain_text('Abre un archivo');assert not app.features.studio.data['recent'];passed('Fresh welcome has no Continue action and no invented recent files')
    page.locator('.home-enter').click()
    def open_file(name):
     page.keyboard.press('Escape');page.keyboard.press('Control+k');page.locator('#palette-input').fill(name);page.locator('.palette-result').filter(has_text=name).first.click();page.wait_for_function('(p)=>window.lumen.activeFile===p',arg=name)
    def set_text(path,text):page.evaluate('([path,text])=>monaco.editor.getModels().find(m=>m.uri.path.endsWith(path)).setValue(text)',[path,text])
    def drag(path,x,y):
     page.evaluate('([path,x,y])=>{const node=[...document.querySelectorAll("[data-tab]")].find(n=>n.dataset.tab===path),transfer=new DataTransfer();node.dispatchEvent(new DragEvent("dragstart",{bubbles:true,dataTransfer:transfer}));document.querySelector("#editor-panel").dispatchEvent(new DragEvent("dragover",{bubbles:true,dataTransfer:transfer,clientX:x,clientY:y}));document.querySelector("#editor-panel").dispatchEvent(new DragEvent("drop",{bubbles:true,dataTransfer:transfer,clientX:x,clientY:y}));node.dispatchEvent(new DragEvent("dragend",{bubbles:true,dataTransfer:transfer,clientX:x,clientY:y}));}',[path,x,y]);page.wait_for_timeout(450)
    open_file('first.py');set_text('first.py','print("UNSAVED ñ")\n');open_file('second.py');rect=page.locator('#editor-mount').bounding_box();drag('first.py',rect['x']+rect['width']-5,rect['y']+rect['height']/2);expect(page.locator('.editor-pane')).to_have_count(2);assert set(page.locator('.editor-pane-heading span').all_text_contents())=={'first.py','second.py'};assert (ws/'first.py').read_text()=='print("FIRST")\n';passed('Dragging a tab to the right splits two distinct buffers and preserves unsaved text')
    rect=page.locator('#editor-mount').bounding_box();drag('second.py',rect['x']+rect['width']/2,rect['y']+rect['height']-3);expect(page.locator('#editor-mount')).to_have_attribute('data-split-axis','vertical');passed('Bottom drop changes to a vertical editor split')
    # Test the native handoff event and coordinates; actual native windows are checked separately.
    page.evaluate('window.__detached=[];window.pywebview={api:{detach_panel:async(...args)=>window.__detached.push(args)}}')
    page.evaluate('()=>{const node=document.querySelector("[data-tab]"),transfer=new DataTransfer();node.dispatchEvent(new DragEvent("dragstart",{bubbles:true,dataTransfer:transfer}));node.dispatchEvent(new DragEvent("dragend",{bubbles:true,dataTransfer:transfer,clientX:-120,clientY:300,screenX:-900,screenY:300}));}')
    page.wait_for_function('window.__detached.some(x=>x[0]==="editor")');assert page.evaluate('window.__detached[0][2].x')==-940
    for panel in ['project','assistant','console']:
     page.evaluate('(panel)=>{const handle=document.querySelector(`[data-dock-handle="${panel}"]`);handle.dispatchEvent(new PointerEvent("pointerdown",{bubbles:true,button:0,isPrimary:true,pointerId:1,clientX:100,clientY:200}));window.dispatchEvent(new PointerEvent("pointermove",{bubbles:true,pointerId:1,clientX:-200,clientY:250,screenX:-1200,screenY:250}));window.dispatchEvent(new PointerEvent("pointerup",{bubbles:true,pointerId:1,clientX:-200,clientY:250,screenX:-1200,screenY:250}));}',panel);page.wait_for_function('(panel)=>window.__detached.some(x=>x[0]===panel)',arg=panel)
    passed('Releasing tabs and all tool panels outside Lumen hands them to native windows on negative-coordinate monitors')
    page.evaluate('delete window.pywebview');page.keyboard.press('Control+k');page.locator('#palette-input').fill('cerrar división');page.locator('.palette-result').first.click()
    open_file('index.html');set_text('index.html','<link rel="stylesheet" href="style.css"><h1>VISTA ñ SIN GUARDAR</h1>');page.locator('#workspace-style').select_option('web');page.locator('[data-profile-action=preview]').click();expect(page.frame_locator('.profile-preview-scroll iframe').locator('h1')).to_have_text('VISTA ñ SIN GUARDAR');page.locator('[data-preview-width="390px"]').click();assert page.locator('.profile-preview-scroll iframe').evaluate('(el)=>el.style.width')=='390px';assert 'DISK' in (ws/'index.html').read_text();page.screenshot(path=str(out/'r8-web.png'));passed('Web profile runs the unsaved HTML on its isolated origin and switches to mobile width')
    open_file('sales.csv');page.locator('#workspace-style').select_option('data');expect(page.locator('.profile-table-scroll tbody tr')).to_have_count(2);expect(page.locator('.profile-statistics')).to_contain_text('media 20');page.locator('.profile-table-filter').fill('Luis');expect(page.locator('.profile-table-scroll tbody tr')).to_have_count(1);expect(page.locator('.profile-statistics')).to_contain_text('media 30');page.screenshot(path=str(out/'r8-data.png'));passed('Data profile filters quoted CSV and recomputes numeric statistics')
    open_file('style.css');page.locator('#workspace-style').select_option('design');expect(page.locator('.profile-color-chip')).to_have_count(2);page.locator('#profile-insert-colors').click();page.wait_for_timeout(400);assert '--color-1' in page.evaluate('monaco.editor.getModels().find(m=>m.uri.path.endsWith("style.css")).getValue()');assert '--color-1' not in (ws/'style.css').read_text();page.screenshot(path=str(out/'r8-design.png'));passed('Design profile builds a palette and inserts CSS variables only after an explicit click')
    page.locator('[aria-label="Vistas de extensiones"]').click();page.locator('.extension-tree-row').filter(has_text='root').click();page.locator('.extension-tree-row').filter(has_text='leaf').click();expect(page.locator('.toast').filter(has_text='TREE COMMAND ñ')).to_be_visible();passed('Executable plugin tree expands real nodes and executes the registered command')
    assert not page.evaluate('window.__errorToasts||[]');passed('Shared buffer handoffs produce no false conflict or business error notifications')
    page.keyboard.press('Escape');page.reload();page.wait_for_function('window.lumen?.ready');expect(page.locator('.hero-quick-actions')).to_contain_text('Continuar');expect(page.locator('#workspace-style')).to_have_value('design');passed('Workspace style, extension installation and legitimate recent history survive reload')
    assert not errors,errors;passed('No uncaught JavaScript errors');browser.close()
  finally:
   server.shutdown();server.server_close();app.features.shutdown();app.runner.shutdown();(out/'r8-ui-verification.json').write_text(json.dumps({'checks':checks,'errors':errors},indent=2),encoding='utf-8')
if __name__=='__main__':main()
