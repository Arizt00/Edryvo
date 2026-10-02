"""Real panel ownership, drag, recovery and viewport checks on disposable data."""
from pathlib import Path
import argparse,json,sys,tempfile,threading
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.server import Application,LumenServer
from playwright.sync_api import sync_playwright,expect

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);out=p.parse_args().output;out.mkdir(parents=True,exist_ok=True)
 checks=[];errors=[]
 def passed(s):checks.append(s);print('PASS',s,flush=True)
 with tempfile.TemporaryDirectory(prefix='lumen-floating-') as temp:
  base=Path(temp);ws=base/'project';ws.mkdir();(ws/'hello.py').write_text('print(42)\n',encoding='utf-8')
  app=Application(ROOT,ws,data_dir=base/'profile');app.features.studio.update({'onboarded':True});app.features.prefs.update({'general.showWelcome':False,'files.autoSave':False})
  server=LumenServer(0,app);threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='msedge',headless=True,args=['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist'])
    page=browser.new_page(viewport={'width':1672,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(f'http://127.0.0.1:{server.server_port}',wait_until='networkidle');page.wait_for_function('window.lumen?.ready')
    if page.locator('.home-enter').is_visible():page.locator('.home-enter').click()
    def layout():return page.evaluate('window.lumen.layout')
    def organize():
     page.keyboard.press('Control+k');page.locator('#palette-input').fill('Organizar y agrupar paneles');page.locator('.palette-result').first.click()
    assert page.locator('.terminal-tab.active').evaluate('(e)=>getComputedStyle(e).backgroundColor')=='rgba(0, 0, 0, 0)'
    orb=page.locator('.assistant-hero .melody-art').bounding_box();hero=page.locator('.assistant-hero').bounding_box();assert orb['width']<=191 and orb['y']>=hero['y']+11
    panel=page.locator('#dock-right').bounding_box();editor=page.locator('#editor-panel').bounding_box();assert panel['y']>=editor['y']+15
    passed('Terminal has no purple tile; Melody is smaller and separated from the controls')
    page.locator('#ai-input').fill('Borrador que debe conservarse');page.evaluate('window.inputOwner=document.querySelector("#ai-input")')
    page.locator('[data-panel-float=assistant]').click();frame=page.locator('[data-floating-panel=assistant]');expect(frame).to_be_visible();page.wait_for_timeout(300)
    assert 'assistant' in layout()['floating'];assert not page.locator('#dock-right').is_visible();assert page.evaluate('window.inputOwner===document.querySelector("#ai-input")')
    expect(page.locator('#ai-input')).to_have_value('Borrador que debe conservarse');passed('Floating assistant retains the same live DOM and draft, releasing its dock')
    rect=frame.bounding_box();head=frame.locator('.floating-title').bounding_box();page.mouse.move(head['x']+70,head['y']+18);page.mouse.down();page.mouse.move(head['x']+110,head['y']+90,steps=12);page.mouse.up();page.wait_for_timeout(250)
    moved=frame.bounding_box();assert abs(rect['x']-moved['x'])>20 and abs(rect['y']-moved['y'])>40
    page.locator('[data-floating-resize=assistant]').focus();width=layout()['floating']['assistant']['width'];page.keyboard.press('ArrowRight');assert layout()['floating']['assistant']['width']==width+10
    passed('Floating frame can be dragged and resized with keyboard controls')
    old=layout()['floating']['assistant'];head=frame.locator('.floating-title').bounding_box();page.mouse.move(head['x']+60,head['y']+18);page.mouse.down();page.mouse.move(head['x']+95,head['y']+55,steps=8);page.keyboard.press('Escape');page.mouse.up();assert layout()['floating']['assistant']==old
    passed('Escape cancels dragging and restores the original geometry')
    frame.locator('.floating-title [data-dock-hide=assistant]').click();expect(frame).to_be_hidden();organize();page.locator('[data-visible-panel=assistant]').check();page.get_by_role('button',name='Listo',exact=True).click();expect(frame).to_be_visible();expect(page.locator('#ai-input')).to_have_value('Borrador que debe conservarse')
    frame.locator('[data-float-side=right]').click();expect(page.locator('#dock-right #assistant-panel')).to_be_visible();assert 'assistant' not in layout()['floating'];assert page.evaluate('window.inputOwner===document.querySelector("#ai-input")');passed('Close, reopen and redock preserve the same assistant session')
    page.locator('[data-panel-float=console]').click();expect(page.locator('[data-floating-panel=console]')).to_be_visible();page.locator('#terminal-input').fill('echo draft');page.keyboard.press('Control+j');expect(page.locator('[data-floating-panel=console]')).to_be_hidden();page.keyboard.press('Control+j');expect(page.locator('[data-floating-panel=console]')).to_be_visible();expect(page.locator('#terminal-input')).to_have_value('echo draft');passed('Ctrl+J hides and recovers the floating terminal without losing its input')
    head=page.locator('#sidebar-title').bounding_box();area=page.locator('#workspace').bounding_box();page.mouse.move(head['x']+20,head['y']+10);page.mouse.down();page.mouse.move(area['x']+area['width']*.51,area['y']+150,steps=16);page.mouse.up();expect(page.locator('[data-floating-panel=project]')).to_be_visible();passed('Dragging a docked heading into the workspace detaches a real floating panel');page.locator('[data-floating-panel=project] .floating-title [data-dock-hide=project]').click();page.locator('.rail-item[data-view=explorer]').click();expect(page.locator('[data-floating-panel=project]')).to_be_visible();passed('Explorer navigation recovers a closed floating project panel')
    for width,height in ((1050,720),(1920,1080)):
     page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(300);area=page.locator('#workspace').bounding_box()
     for floating in page.locator('.floating-panel:visible').all():
      r=floating.bounding_box();assert r['x']>=area['x'] and r['y']>=area['y'] and r['x']+r['width']<=area['x']+area['width']+1 and r['y']+r['height']<=area['y']+area['height']+1,(r,area)
    passed('Floating panels remain reachable when the window becomes smaller')
    page.screenshot(path=str(out/'r5-floating-panels.png'));page.wait_for_timeout(500);before=layout()['floating'];page.reload(wait_until='networkidle');page.wait_for_function('window.lumen?.ready');assert layout()['floating']==before
    passed('Floating positions persist after reopening the interface');assert not errors,errors;passed('No uncaught JavaScript errors');browser.close()
  finally:
   server.shutdown();server.server_close();app.features.shutdown();app.runner.shutdown();(out/'r5-floating-verification.json').write_text(json.dumps({'checks':checks,'errors':errors},indent=2),encoding='utf-8')
if __name__=='__main__':main()
