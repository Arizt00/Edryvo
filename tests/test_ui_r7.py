"""R7 browser checks against the real backend, shared buffers and integrated PTYs."""
from pathlib import Path
import argparse,json,sys,tempfile,threading,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.server import Application,LumenServer
from playwright.sync_api import sync_playwright,expect

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);out=p.parse_args().output;out.mkdir(parents=True,exist_ok=True)
 checks=[];errors=[]
 def passed(name):checks.append(name);print('PASS',name,flush=True)
 with tempfile.TemporaryDirectory(prefix='lumen-ui-r7-') as t:
  base=Path(t);ws=base/'project';ws.mkdir()
  (ws/'first.py').write_text('print("FIRST DISK")\n');(ws/'second.py').write_text('print("SECOND DISK")\n')
  (ws/'hello.c').write_text('#include <stdio.h>\nint main(void) {\n int answer=42;\n printf("%d\\n",answer);\n return 0;\n}\n')
  app=Application(ROOT,ws,data_dir=base/'profile');app.workspace.trusted=True;app.features.studio.update({'onboarded':True});app.features.prefs.update({'general.showWelcome':False,'files.autoSave':False,'updates.automatic':False})
  server=LumenServer(0,app);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
  try:
   with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='msedge',headless=True,args=['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']);context=browser.new_context(viewport={'width':1672,'height':1000});page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.on('response',lambda r:errors.append('HTTP '+str(r.status)+' '+r.url) if r.status>=500 else None)
    def open_file(name):
     page.keyboard.press('Escape');page.keyboard.press('Control+k');page.locator('#palette-input').fill(name);page.locator('.palette-result').filter(has_text=name).first.click();page.wait_for_function('(name)=>window.lumen.activeFile===name',arg=name)
    def model(page,path):return page.evaluate('(path)=>monaco.editor.getModels().find(m=>m.uri.path.endsWith(path)).getValue()',path)
    def set_text(page,path,text):page.evaluate('([path,text])=>monaco.editor.getModels().find(m=>m.uri.path.endsWith(path)).setValue(text)',[path,text])
    page.goto(url,wait_until='domcontentloaded');page.wait_for_function('window.lumen?.ready');open_file('first.py');open_file('second.py')
    page.locator('[data-action=split-editor]').click();expect(page.locator('.editor-pane')).to_have_count(2)
    texts=page.locator('.editor-pane-heading span').all_text_contents();assert set(texts)=={'first.py','second.py'},texts
    # Focus and edit both visible files; Ctrl+S must target the focused pane.
    for i,text in enumerate(['print("LEFT ñ")\n','print("RIGHT ñ")\n']):
     pane=page.locator('.editor-pane').nth(i);name=pane.locator('.editor-pane-heading span').inner_text();pane.locator('textarea').focus();page.keyboard.press('Control+a');page.keyboard.insert_text(text);page.keyboard.press('Control+s');page.wait_for_timeout(400);assert (ws/name).read_text(encoding='utf-8')==text
    assert (ws/'first.py').read_text(encoding='utf-8')!=(ws/'second.py').read_text(encoding='utf-8');page.screenshot(path=str(out/'r7-two-editors.png'));passed('Two visible editors keep distinct buffers, active paths and manual saves')
    # Actions added to the second pane must work there as well.
    second=page.locator('.editor-pane').nth(1).bounding_box();page.mouse.click(second['x']+160,second['y']+95,button='right');menu=page.locator('.monaco-menu .monaco-action-bar.vertical:visible');expect(menu).to_contain_text('Lantern: ejecutar este búfer');page.keyboard.press('Escape');passed('Lumen contextual actions also exist in the second editor')
    target=page.evaluate('window.lumen.activeFile');set_text(page,target,'print("SHARED UNSAVED ñ")\n')
    with page.expect_popup() as pop:page.locator('[data-action=detach-editor]').click()
    child=pop.value;child.on('pageerror',lambda e:errors.append(str(e)));child.wait_for_function('window.lumen?.ready');expect(child.locator('#editor-panel')).to_be_visible();assert model(child,target)=='print("SHARED UNSAVED ñ")\n'
    set_text(child,target,'print("CHILD EDIT ñ")\n');page.wait_for_function('(p)=>monaco.editor.getModels().some(m=>m.uri.path.endsWith(p)&&m.getValue().includes("CHILD EDIT"))',arg=target)
    assert 'CHILD EDIT' not in (ws/target).read_text(encoding='utf-8');child.locator('.monaco-editor textarea').first.focus();child.keyboard.press('Control+s');page.wait_for_timeout(700)
    assert (ws/target).read_text(encoding='utf-8')=='print("CHILD EDIT ñ")\n';set_text(page,target,'print("PARENT AFTER SAVE")\n');page.locator('.editor-pane').nth(1).locator('textarea').focus();page.keyboard.press('Control+s');page.wait_for_timeout(500);assert (ws/target).read_text()=='print("PARENT AFTER SAVE")\n'
    child.screenshot(path=str(out/'r7-detached-editor.png'));child.close();passed('Detached editor shares unsaved edits, save state and disk revisions in both directions')
    # Project and assistant use independent viewports, not clipped floating DIVs.
    detached=context.new_page();detached.goto(url+'/?panel=project',wait_until='domcontentloaded');detached.wait_for_function('window.lumen?.ready');expect(detached.locator('#project-panel')).to_be_visible();assert not detached.locator('#workspace').is_visible()
    detached.locator('[data-file="hello.c"]').click();page.wait_for_function('window.lumen.activeFile==="hello.c"');detached.close();passed('Detached project clicks open files in the main editor')
    # Forge follows the focused editor and executes its actual unsaved buffer.
    open_file('first.py');set_text(page,'first.py','print("FORGE BUFFER ñ")\n');page.keyboard.press('Control+k');page.locator('#palette-input').fill('Forge: abrir en la terminal integrada');page.locator('.palette-result').first.click();expect(page.locator('.forge-dashboard')).to_be_visible()
    expect(page.locator('.forge-file')).to_have_text('first.py');expect(page.locator('.forge-buffer')).to_have_text('Sin guardar');expect(page.locator('[data-action=hacker-python]')).to_be_enabled();expect(page.locator('[data-action=hacker-gdb]')).to_be_disabled()
    page.wait_for_function('document.querySelector("#terminal-panel").getBoundingClientRect().height>=400');assert page.locator('.forge-tool.available').count()==3
    passed('Forge tracks the focused file and dirty buffer, gates language actions and expands its console')
    page.locator('[data-action=hacker-python]').click()
    page.wait_for_function('document.querySelector(".pty-session-tabs")?.textContent.includes("Python")');page.wait_for_timeout(1200);assert any('FORGE BUFFER ñ' in s.read(0)['data'] for s in app.features.terminals.sessions.values());assert 'FORGE BUFFER' not in (ws/'first.py').read_text(encoding='utf-8');expect(page.locator('.forge-status')).to_contain_text('Sesión finalizada');passed('Forge Python button executes current unsaved text in the integrated terminal')
    open_file('hello.c');expect(page.locator('.forge-file')).to_have_text('hello.c');expect(page.locator('[data-action=hacker-python]')).to_be_disabled();expect(page.locator('[data-action=hacker-gdb]')).to_be_enabled();page.locator('[data-action=hacker-gdb]').click();page.wait_for_function('document.querySelector(".pty-session-tabs")?.textContent.includes("GDB")',timeout=20000);
    for _ in range(100):
     if any('(gdb)' in s.read(0)['data'] for s in app.features.terminals.sessions.values()):break
     page.wait_for_timeout(200)
    else:raise AssertionError({s.profile['label']:s.read(0) for s in app.features.terminals.sessions.values()})
    expect(page.locator('.forge-status')).to_contain_text('Depurador preparado');page.mouse.move(600,200);page.wait_for_timeout(200);page.screenshot(path=str(out/'r7-forge-gdb.png'));passed('Forge C button compiles debug symbols and opens a real GDB prompt in Lumen')
    # Independent terminal viewports stay usable on narrower screens and respect reduced motion.
    forge=context.new_page();forge.goto(url+'/?panel=console',wait_until='domcontentloaded');forge.wait_for_function('window.lumen?.ready');forge.set_viewport_size({'width':440,'height':720});forge.emulate_media(reduced_motion='reduce');forge.wait_for_timeout(300)
    assert forge.locator('.forge-dashboard').evaluate('(n)=>n.scrollWidth<=n.clientWidth');assert forge.evaluate('getComputedStyle(document.querySelector(".forge-dashboard")).animationName')=='none';forge.screenshot(path=str(out/'r7-forge-compact.png'));forge.close()
    passed('Forge fits an independent narrow terminal window and respects reduced motion')
    gdb=next(s for s in app.features.terminals.sessions.values() if s.profile['label'].startswith('GDB'))
    page.locator('.pty-session:not([hidden]) .xterm-helper-textarea').focus();page.keyboard.type('next');page.keyboard.press('Enter');page.wait_for_timeout(400);page.keyboard.type('print answer');page.keyboard.press('Enter')
    for _ in range(50):
     if '$1 = 42' in gdb.read(0)['data']:break
     page.wait_for_timeout(100)
    else:raise AssertionError(gdb.read(0))
    passed('GDB commands entered in the UI inspect variables after a second terminal view attaches')
    with page.expect_popup() as pop:page.locator('.forge-toggle').click()
    forge=pop.value;forge.wait_for_function('window.lumen?.ready');assert forge.evaluate('document.documentElement.dataset.detachedPanel')=='forge';expect(forge.locator('.forge-file')).to_have_text('hello.c')
    open_file('first.py');set_text(page,'first.py','print("FORGE WINDOW LIVE ñ")\n');forge.wait_for_function('monaco.editor.getModels().some(m=>m.uri.path.endsWith("first.py")&&m.getValue().includes("FORGE WINDOW LIVE"))');expect(forge.locator('.forge-file')).to_have_text('first.py')
    forge.locator('[data-action=hacker-python]').click()
    for _ in range(80):
     if any('FORGE WINDOW LIVE ñ' in s.read(0)['data'] for s in app.features.terminals.sessions.values()):break
     page.wait_for_timeout(100)
    else:raise AssertionError('Forge did not execute its synchronized unsaved buffer')
    forge.mouse.move(500,400);forge.screenshot(path=str(out/'r7-forge-window.png'));forge.locator('[data-action=forge-terminal]').click();page.wait_for_timeout(400);assert forge.is_closed();expect(page.locator('.forge-dashboard')).to_be_visible()
    passed('Dedicated Forge window follows the parent file and live buffer, executes Python and returns to the integrated terminal')
    # Builtin modes remain solid and colorized without theme extensions.
    for theme in ['day','dark','forest']:
     page.locator('[data-action=settings]:visible').first.click();page.locator('[data-setting-category=appearance]').click();page.locator('[data-platform-theme='+theme+']').click();page.keyboard.press('Escape');page.wait_for_timeout(250)
     glass=page.evaluate('getComputedStyle(document.documentElement).getPropertyValue("--glass")');assert '.9' in glass,glass
     assert page.locator('.monaco-editor .view-line span').evaluate_all('(items)=>new Set(items.map(x=>getComputedStyle(x).color)).size')>=3
     page.screenshot(path=str(out/('r7-'+theme+'.png')))
    passed('All builtin themes have opaque panels and visible syntax colors')
    page.keyboard.press('Control+k');page.locator('#palette-input').fill('Lumen: comprobar actualizaciones');page.locator('.palette-result').first.click();expect(page.locator('#update-status')).to_be_visible();expect(page.locator('#automatic-updates')).not_to_be_checked();expect(page.locator('#update-install')).to_be_disabled();passed('Update controls show current release, auto-download preference and a gated install action')
    assert not errors,errors;passed('No uncaught JavaScript errors');browser.close()
  finally:
   server.shutdown();server.server_close();app.features.shutdown();app.runner.shutdown();(out/'r7-ui-verification.json').write_text(json.dumps({'checks':checks,'errors':errors},indent=2),encoding='utf-8')
if __name__=='__main__':main()
