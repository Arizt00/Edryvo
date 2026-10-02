"""R4 browser integration. AI transport is a deterministic fixture, not cloud inference."""
from pathlib import Path
import argparse,base64,io,json,shutil,sys,tempfile,threading,time,zipfile,re
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.server import Application,LumenServer
from playwright.sync_api import sync_playwright,expect

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);out=p.parse_args().output;out.mkdir(parents=True,exist_ok=True)
 checks=[];errors=[];page=None
 def passed(name):checks.append(name);print('PASS',name,flush=True)
 with tempfile.TemporaryDirectory(prefix='lumen-r4-ui-') as temp:
  base=Path(temp);ws=base/'Project';shutil.copytree(ROOT/'workspace/MyProject',ws)
  (ws/'live.py').write_text('lantern_state["count"]=lantern_state.get("count",0)+1\nprint("COUNT",lantern_state["count"])\n')
  (ws/'other.py').write_text('print("OTHER_FILE")\n');(ws/'native.c').write_text((ROOT/'examples/lantern/counter.c').read_text())
  app=Application(ROOT,ws,data_dir=base/'profile');app.workspace.trusted=True;app.features.studio.update({'onboarded':True});app.features.prefs.update({'general.showWelcome':False,'ai.provider':'ollama','ai.model':'r4-fixture','lantern.autoSave':False,'files.autoSave':False})
  # Real Node extension installation and execution; no provider stubs.
  raw=io.BytesIO()
  with zipfile.ZipFile(raw,'w') as z:
   z.writestr('extension/package.json',json.dumps({'publisher':'lumen','name':'preview-qa','displayName':'Preview QA','version':'1.0.0','main':'main.cjs'}))
   z.writestr('extension/main.cjs',"exports.activate=(context,lumen)=>{lumen.registerCommand('qa.uppercase',doc=>({text:doc.text.toUpperCase()}),'QA uppercase');lumen.registerInlayHintsProvider('python',()=>[{position:{line:0,character:3},label:': int'}]);lumen.registerCompletionProvider('python',()=>[{label:'r4Hello',kind:1,insertText:'r4Hello()'}]);lumen.registerDefinitionProvider('python',()=>[{path:'other.py',range:{start:{line:0,character:0},end:{line:0,character:5}}}]);lumen.registerDiagnosticsProvider('python',()=>[{line:1,column:1,endColumn:4,message:'R4 diagnostic',severity:'warning'}]);};")
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
    def wait_output(text):expect(page.locator('#lantern-inline .lantern-output')).to_contain_text(text,timeout=25000)
    page.goto(f'http://127.0.0.1:{server.server_port}',wait_until='networkidle');page.wait_for_function('window.lumen?.ready')
    if page.locator('.home-enter').is_visible():page.locator('.home-enter').click()
    open_file('live.py');page.keyboard.press('Control+Alt+l');expect(page.locator('#lantern-inline')).to_be_visible();wait_output('COUNT 1');assert not page.evaluate('window.lumen.platformPage');passed('Lantern shortcut runs active file inline without opening Debug')
    page.locator('#lantern-inline [data-lantern=restart]').click();wait_output('COUNT 2');passed('Real Python checkpoint restored on next inline revision')
    open_file('other.py');wait_output('OTHER_FILE');open_file('live.py');wait_output('COUNT 3');passed('Lantern follows the active tab and restores its separate memory')
    page.screenshot(path=str(out/'r4-lantern.png'));page.locator('#lantern-inline [data-lantern=stop]').click();page.locator('#lantern-inline [data-lantern=close-inline]').click()
    expect(page.locator('.file-groups')).to_be_visible();page.locator('[data-file-group=Proyecto]').click();expect(page.get_by_role('menuitem',name='other.py',exact=True)).to_be_visible();page.get_by_role('menuitem',name='other.py',exact=True).click();assert page.evaluate('window.lumen.activeFile')=='other.py';passed('Folder groups open their file menu and activate a file')
    expect(page.locator('.rail-compact-toggle')).to_have_attribute('aria-expanded','true');page.locator('.rail-compact-toggle').click();expect(page.locator('.rail-compact-toggle')).to_have_attribute('aria-expanded','false');page.wait_for_function('document.querySelector(".activity-rail").getBoundingClientRect().width<60');small=page.locator('.activity-rail').bounding_box()['width'];page.locator('.rail-compact-toggle').click();expect(page.locator('.rail-compact-toggle')).to_have_attribute('aria-expanded','true');page.wait_for_function('document.querySelector(".activity-rail").getBoundingClientRect().width>70');large=page.locator('.activity-rail').bounding_box()['width'];assert small<large,(small,large);passed('Activity navigation collapses and expands')
    replace('print("SAVED_BY_CTRL_O")\n');page.keyboard.press('Control+o');page.wait_for_timeout(300);assert 'SAVED_BY_CTRL_O' in (ws/'other.py').read_text();page.keyboard.press('Control+Shift+o');expect(page.locator('#save-as-form')).to_be_visible();page.locator('#save-as-path').fill('saved-copy.py');page.locator('#save-as-form button').click();page.wait_for_function('window.lumen.activeFile==="saved-copy.py"');assert 'SAVED_BY_CTRL_O' in (ws/'saved-copy.py').read_text();passed('Requested Ctrl+O save and Ctrl+Shift+O save-as work')
    page.keyboard.press('Control+n');expect(page.locator('#new-file-form')).to_be_visible();page.keyboard.press('Escape')
    with page.expect_popup() as popup:page.keyboard.press('Control+Shift+n')
    popup.value.wait_for_load_state();popup.value.close();passed('Ctrl+N opens new file; Ctrl+Shift+N opens another window')
    # Profile upload / crop / persist / reopen must recover the actual picture.
    page.locator('[data-action=profile]').first.click();expect(page.locator('#profile-crop')).to_be_visible()
    data=page.evaluate('''()=>{let c=document.createElement('canvas');c.width=512;c.height=256;let x=c.getContext('2d');x.fillStyle='#eb5040';x.fillRect(0,0,256,256);x.fillStyle='#206fe2';x.fillRect(256,0,256,256);return c.toDataURL('image/png').split(',')[1]}''')
    page.locator('#profile-picture').set_input_files({'name':'profile-qa.png','mimeType':'image/png','buffer':base64.b64decode(data)})
    expect(page.locator('#profile-zoom')).to_be_enabled();page.locator('#profile-zoom').fill('1.5');page.locator('#profile-name').fill('R4 Preview');page.locator('#profile-form .primary-button').click();expect(page.locator('#profile-form')).to_have_count(0)
    page.locator('[data-action=profile]').first.click();expect(page.locator('#profile-zoom')).to_be_enabled();pixel=page.locator('#profile-crop').evaluate('(c)=>Array.from(c.getContext("2d").getImageData(390,256,1,1).data)');assert pixel[2]>pixel[0]+70,pixel;page.screenshot(path=str(out/'r4-profile.png'));passed('Uploaded profile crop, name and saved picture survive reopening')
    page.locator('#remove-avatar').click();expect(page.locator('#profile-zoom')).to_be_disabled();page.locator('#profile-form .primary-button').click();assert not app.features.studio.export()['avatar'];passed('Remove profile photo persists without breaking name')
    # In-memory stream fixture exercises permission, current buffer, visible edits and undo.
    open_file('other.py');replace('print("UNSAVED_CONTEXT")\n');before=buffer();sent=[];chunks=['```python\nprint(', '"LIVE_EDIT")\n', '```'];calls=[0]
    def ai_start(route):sent.append(route.request.post_data_json);route.fulfill(json={'id':'r4-stream'});calls[0]=0
    def ai_job(route):
     i=calls[0];calls[0]+=1;route.fulfill(json={'delta':chunks[i] if i<len(chunks) else '', 'offset':i+1,'done':i>=len(chunks)-1})
    page.route('**/api/platform/ai/start',ai_start);page.route('**/api/platform/ai/job?*',ai_job);page.route('**/api/platform/ai/cancel',lambda r:r.fulfill(json={'ok':True}))
    page.locator('#ai-input').fill('Reescribe el archivo abierto');page.locator('#ai-edit-file').click();page.get_by_role('button',name='Enviar esta petición',exact=True).click();page.get_by_role('button',name='Permitir esta edición',exact=True).click();page.wait_for_function('monaco.editor.getModels().some(m=>m.getValue()===\'print("LIVE_EDIT")\\n\')');expect(page.locator('#ai-form .send-button')).to_be_enabled();assert sent[-1]['content']==before;assert 'SAVED_BY_CTRL_O' in (ws/'other.py').read_text();replace_current=buffer();assert replace_current=='print("LIVE_EDIT")\n';page.locator('.monaco-editor textarea').first.focus();page.keyboard.press('Control+z');assert buffer()==before;passed('AI fixture receives unsaved current buffer, edits visibly with consent, leaves disk unchanged and supports undo')
    page.unroute('**/api/platform/ai/job?*')
    page.route('**/api/platform/ai/job?*',lambda route:route.fulfill(json={'delta':'```python\n# AI partial\n' if calls[0]==0 else '', 'offset':1,'done':False}) or calls.__setitem__(0,calls[0]+1))
    page.locator('#ai-input').fill('Editar de nuevo');page.locator('#ai-edit-file').click();page.get_by_role('button',name='Enviar esta petición',exact=True).click();page.get_by_role('button',name='Permitir esta edición',exact=True).click();page.wait_for_function('monaco.editor.getModels().some(m=>m.getValue()==="# AI partial\\n")');replace('# USER_CHANGE\n');expect(page.locator('#ai-form .send-button')).to_be_enabled();assert buffer()=='# USER_CHANGE\n';passed('Live edit cancels on concurrent typing and preserves the user buffer')
    page.unroute('**/api/platform/ai/start');page.unroute('**/api/platform/ai/job?*')
    page.locator('[data-action=extensions]:visible').first.click();expect(page.locator('[data-extension-execute="lumen.preview-qa"]')).to_be_visible();page.locator('[data-extension-execute="lumen.preview-qa"]').click();page.get_by_role('button',name='Autorizar motor',exact=True).click();expect(page.locator('[data-extension-execute="lumen.preview-qa"]')).to_have_text('Detener motor');page.keyboard.press('Escape');page.keyboard.press('Control+k');page.locator('#palette-input').fill('QA uppercase');expect(page.locator('.palette-result').first).to_contain_text('QA uppercase');page.locator('.palette-result').first.click();expect(page.get_by_role('heading',name='Propuesta',exact=True)).to_be_visible();page.keyboard.press('Escape');passed('Installed executable extension starts a real Node host and its command produces an editor diff')
    open_file('live.py');page.wait_for_function('monaco.editor.getModelMarkers({}).some(m=>m.message==="R4 diagnostic" && m.severity===4 && m.startLineNumber===1)');passed('Executable plugin diagnostics reach Monaco with real warning markers')
    page.wait_for_function('Array.from(document.querySelectorAll(".monaco-editor .view-lines")).some(e=>e.textContent.replaceAll("\\u00a0"," ").includes(": int"))');passed('Executable plugin inlay hints render in the editor')
    replace('r4');page.keyboard.press('Control+Space');expect(page.locator('.suggest-widget')).to_contain_text('r4Hello');page.keyboard.press('Escape');page.locator('.monaco-editor textarea').first.focus();page.keyboard.press('F12');page.wait_for_timeout(1500);print('DEFINITION QA',page.evaluate('({active:window.lumen.activeFile,focus:document.activeElement?.className,editors:monaco.editor.getEditors().map(e=>({uri:e.getModel()?.uri.toString(),supported:e.getAction("editor.action.revealDefinition")?.isSupported()}))})'),errors,flush=True);page.screenshot(path=str(out/'r4-definition.png'));page.wait_for_function('window.lumen.activeFile==="other.py"');passed('Executable plugin completion and F12 definition navigation work end to end')
    open_file('native.c');page.keyboard.press('Control+Alt+l');wait_output('LANTERN_NATIVE 1');page.locator('#lantern-inline [data-lantern=memory]').click();expect(page.locator('#modal')).to_contain_text('schema');page.locator('[data-lantern=support]').click();page.locator('#lantern-template-path').fill('native-example.c');page.locator('#lantern-template .primary-button').click();page.wait_for_function('window.lumen.activeFile==="native-example.c"');assert (ws/'native-example.c').exists();passed('Native checkpoint metadata and creation of working cooperative SDK example are available in Lantern')
    app.features.lantern.stop();page.locator('#lantern-inline [data-lantern=close-inline]').click()
    for width,height in ((1050,720),(1366,768),(1920,1080)):
     page.set_viewport_size({'width':width,'height':height});page.locator('.debug-button').click();page.wait_for_timeout(300);assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');bars=page.locator('.debug-card>h3').evaluate_all('(es)=>es.map(e=>getComputedStyle(e).backgroundColor)');assert all(x=='rgba(0, 0, 0, 0)' for x in bars),bars;page.screenshot(path=str(out/f'r4-debug-{width}.png'));page.keyboard.press('Escape')
    passed('Debug headings have no gray strips and layouts fit three viewport sizes')
    assert not errors,errors;passed('No uncaught JavaScript errors');browser.close()
  except Exception:
   if page:
    try:page.screenshot(path=str(out/'r4-failure.png'));(out/'r4-failure.html').write_text(page.content(),encoding='utf-8')
    except Exception:pass
   raise
  finally:
   server.shutdown();server.server_close();app.features.shutdown();app.runner.shutdown();(out/'r4-ui-verification.json').write_text(json.dumps({'checks':checks,'errors':errors},indent=2),encoding='utf-8')
if __name__=='__main__':main()
