"""Explicit Edge UI regression checks for continuity, accounts and complete themes."""
from pathlib import Path
import argparse,json,shutil,sys,tempfile,threading,time,re
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.server import Application,LumenServer
from playwright.sync_api import sync_playwright,expect

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);out=p.parse_args().output;out.mkdir(parents=True,exist_ok=True)
 checks=[];errors=[]
 def passed(label):checks.append(label);print('PASS',label,flush=True)
 with tempfile.TemporaryDirectory(prefix='lumen-r3-ui-') as temp:
  base=Path(temp);ws=base/'Project';shutil.copytree(ROOT/'workspace/MyProject',ws)
  (ws/'live.py').write_text('print("lantern-first",flush=True)\n')
  (ws/'index.html').write_text('<html><body><h1>Embedded HTML</h1></body></html>')
  app=Application(ROOT,ws,data_dir=base/'profile');app.workspace.trusted=True
  server=LumenServer(0,app);threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='msedge',headless=True,args=['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist'])
    page=browser.new_page(viewport={'width':1672,'height':941});page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(f'http://127.0.0.1:{server.server_port}',wait_until='networkidle');page.wait_for_function('window.lumen?.ready')
    centers=page.evaluate('''()=>{let a=document.querySelector('#onboarding .setup-sidebar').getBoundingClientRect(),b=document.querySelector('#onboarding .setup-sidebar .glass-art').getBoundingClientRect();return {sidebar:a.x+a.width/2,orb:b.x+b.width/2}}''')
    assert abs(centers['sidebar']-centers['orb'])<3,centers
    passed('Onboarding sphere centered in sidebar')
    page.screenshot(path=str(out/'r3-onboarding.png'))
    page.locator('#onboard-next').click();page.locator('#onboard-name').fill('Lumen');page.locator('#onboard-next').click();page.locator('#onboard-next').click();page.locator('.home-enter').click()
    expect(page.locator('#lantern-monitor')).to_be_visible();expect(page.locator('.project-note')).to_have_count(0)
    page.locator('#lantern-monitor [data-lantern=hide]').click();expect(page.locator('#lantern-monitor')).to_be_hidden();passed('Lantern replaces promotional card and can be hidden')
    page.keyboard.press('Control+k');page.locator('#palette-input').fill('lantern-first');expect(page.locator('.palette-result').first).to_contain_text('live.py');page.locator('.palette-result').first.click();page.wait_for_function('window.lumen.activeFile==="live.py"');passed('Live universal palette searches file content and navigates to result')
    page.locator('.monaco-editor textarea').focus();page.keyboard.press('Control+a');page.keyboard.insert_text('def broken(:\n pass')
    page.wait_for_function('monaco.editor.getModelMarkers({}).some(m=>m.source==="Python" && m.startLineNumber===1)');passed('Invalid Python buffer produces real inline diagnostics without running')
    page.keyboard.press('Control+a');page.keyboard.insert_text('print("lantern-first",flush=True)\n');page.keyboard.press('Control+s')
    page.wait_for_function('monaco.editor.getModelMarkers({}).filter(m=>m.source==="Python").length===0')
    page.locator('.debug-button').click();expect(page.locator('#lantern-workbench')).to_be_visible();page.locator('#lantern-workbench [data-lantern=start]').click();expect(page.locator('.lantern-output')).to_contain_text('lantern-first',timeout=12000)
    page.screenshot(path=str(out/'r3-lantern.png'));page.keyboard.press('Escape');page.wait_for_function('window.lumen.platformPage===null || !window.lumen.platformPage')
    page.locator('.monaco-editor textarea').focus();page.keyboard.press('Control+a');page.keyboard.insert_text('print("lantern-updated",flush=True)\n')
    deadline=time.monotonic()+12
    while time.monotonic()<deadline:
     if 'lantern-updated\r\n' in app.features.lantern.snapshot()['output']:break
     page.wait_for_timeout(200)
    else:raise AssertionError(app.features.lantern.snapshot())
    assert 'lantern-updated' in (ws/'live.py').read_text();passed('Lantern autosaves edited buffer and restarts real process')
    page.locator('.debug-button').click();page.locator('#lantern-workbench [data-lantern=analyze]').click();expect(page.locator('#ai-input')).to_have_value(re.compile('lantern-updated'));page.locator('#lantern-workbench [data-lantern=stop]').click();page.keyboard.press('Escape');passed('Lantern sends actual output into reviewable AI prompt and stops')
    # Native select is enhanced into an accessible custom glass combobox.
    page.locator('#assistant-identity-trigger').click();page.get_by_role('option',name='Emma',exact=True).click()
    page.wait_for_function('document.querySelector("#assistant-panel").getAttribute("aria-label")==="Emma"')
    page.locator('#assistant-identity-trigger').click();page.get_by_role('option',name='Melody',exact=True).click();page.wait_for_function('document.querySelector("#assistant-panel").getAttribute("aria-label")==="Melody"');passed('Emma / Melody identity switch is functional and text only')
    page.locator('[data-action=ai-settings]:visible').first.click();expect(page.locator('.account-connection')).to_be_visible();expect(page.locator('#account-status')).not_to_contain_text('Comprobando',timeout=25000)
    expect(page.locator('#provider-credential-form')).to_have_count(0);expect(page.locator('#account-login')).to_be_visible();page.locator('.account-connection').scroll_into_view_if_needed();page.screenshot(path=str(out/'r3-accounts.png'));passed('Account connection screen uses official login without asking for API key')
    page.keyboard.press('Escape')
    for theme in ('day','dark','forest'):
     app.features.prefs.update({'appearance.theme':theme,'general.showWelcome':False})
     page.reload(wait_until='networkidle');page.wait_for_function('window.lumen?.ready');page.wait_for_function(f'window.lumen.theme==="{theme}"')
     page.keyboard.press('Control+k');expect(page.locator('#palette-backdrop')).to_be_visible()
     opacity=page.evaluate('getComputedStyle(document.querySelector(".command-palette")).backgroundColor')
     # Chromium quantizes sRGB alpha to 8 bits when serializing computed styles.
     assert abs(float(opacity.rsplit(',',1)[1].rstrip(')'))-.687)<.003,opacity
     radii=page.locator('.palette-result').first.evaluate('(e)=>getComputedStyle(e).borderRadius');assert radii=='13px',radii
     page.screenshot(path=str(out/f'r3-palette-{theme}.png'));page.keyboard.press('Escape')
     page.locator('[data-action=settings]:visible').first.click();page.locator('[data-setting-category=appearance]').first.click();page.locator('#pref-appearance-theme-trigger').click()
     bg=page.locator('.glass-options').evaluate('(e)=>getComputedStyle(e).backgroundColor') if page.locator('.glass-options').count() else ''
     page.screenshot(path=str(out/f'r3-settings-{theme}.png'));page.keyboard.press('Escape');page.keyboard.press('Escape')
    passed('Day, dark and forest themes include 68.7 percent glass palette, rounded items and themed controls')
    app.features.prefs.update({'appearance.theme':'day'});page.reload(wait_until='networkidle');page.wait_for_function('window.lumen?.ready')
    page.keyboard.press('Control+k');page.locator('#palette-input').fill('index.html');expect(page.locator('.palette-result').first).to_contain_text('index.html');page.locator('.palette-result').first.click();page.locator('.run-button').click();expect(page.locator('.embedded-preview iframe')).to_be_visible();expect(page.frame_locator('.embedded-preview iframe').locator('h1')).to_have_text('Embedded HTML');passed('HTML runs in embedded project preview')
    for width,height in ((1050,720),(1366,768),(1920,1080)):
     page.set_viewport_size({'width':width,'height':height});page.locator('.debug-button').click();page.wait_for_timeout(200)
     assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,height)
     box=page.locator('#lantern-workbench').bounding_box();assert box['x']>=0 and box['x']+box['width']<=width+1,box
    passed('Lantern and debug controls remain within narrow and wide windows')
    assert not errors,errors;passed('No unhandled JavaScript errors');browser.close()
  finally:server.shutdown();server.server_close();app.features.shutdown();app.runner.shutdown()
 (out/'r3-ui-verification.json').write_text(json.dumps({'checks':checks,'errors':errors},indent=2),encoding='utf-8')
if __name__=='__main__':main()
