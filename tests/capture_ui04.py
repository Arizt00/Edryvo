#!/usr/bin/env python3
"""Stable actual UI captures, isolated example project; no external AI/catalog calls."""
import argparse,json,shutil,sys,tempfile,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.server import Application,LumenServer
from ui_harness import prepare

def main():
 p=argparse.ArgumentParser();p.add_argument('--transport',choices=['direct','bridge'],default='direct');p.add_argument('--chromium');p.add_argument('--output',type=Path,default=ROOT/'reports/capture04');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 from playwright.sync_api import sync_playwright,expect
 errors=[];captures=[]
 with tempfile.TemporaryDirectory(prefix='lumen04-capture-') as td:
  td=Path(td);ws=td/'MyProject';shutil.copytree(ROOT/'workspace/MyProject',ws,ignore=shutil.ignore_patterns('.lumen'));app=Application(ROOT,ws,data_dir=td/'data');app.features.prefs.update({'extensions.network':False})
  for f in (ROOT/'examples/extensions').glob('*.vsix'):
   inspection=app.features.extensions.inspect_local(str(f));app.features.extensions.install(inspection['ticket'],True)
  server=LumenServer(0,app);threading.Thread(target=server.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{server.server_port}'
  try:
   with sync_playwright() as pw:
    opts={'headless':True,'args':['--no-sandbox','--disable-dev-shm-usage']}
    if a.chromium:opts['executable_path']=a.chromium
    b=pw.chromium.launch(**opts);pg=b.new_page(viewport={'width':1648,'height':928});pg.set_default_timeout(8000);pg.on('pageerror',lambda e:errors.append(str(e)))
    try:
     if a.transport=='bridge':prepare(pg,base)
     else:pg.goto(base)
     pg.wait_for_function('window.lumen?.platformReady');pg.wait_for_timeout(700)
     def capture(name):
      pg.mouse.move(2,2);pg.wait_for_timeout(750);pg.screenshot(path=str(a.output/(name+'.png')));captures.append(name);print('CAPTURE',name,flush=True)
     capture('dia')
     for key,name in [('2','oscuro'),('3','bosque')]:pg.keyboard.press('Control+Alt+'+key);capture(name)
     pg.keyboard.press('Control+b');pg.keyboard.press('Control+Alt+b');capture('compacto');pg.keyboard.press('Control+b');pg.keyboard.press('Control+Alt+b')
     pg.keyboard.press('Control+Alt+f');capture('concentracion');pg.keyboard.press('Control+Alt+f')
     pg.keyboard.press('Control+Alt+1');pg.keyboard.press('Control+Alt+e');expect(pg.locator('.extension-card')).to_have_count(2);capture('extensiones')
     pg.keyboard.press('Control+,');pg.locator('.settings-navigation [data-setting-category="appearance"]').click();pg.locator('#settings-content').evaluate('(e)=>e.scrollTop=0');capture('ajustes')
     pg.locator('.settings-navigation [data-setting-category="ai"]').click();pg.locator('.provider-grid').scroll_into_view_if_needed();capture('proveedores')
     pg.keyboard.press('Escape');pg.keyboard.press('Control+Alt+t');expect(pg.locator('.terminal-profile-list')).to_be_visible();capture('perfiles-terminal')
     pg.locator('[data-open-terminal="bash"]').click();pg.locator('#confirm-yes').click();expect(pg.locator('.pty-basic-input input')).to_be_visible()
     pg.locator('.pty-basic-input input').fill('printf "Lumen Studio | Bash interactivo\\n"; printf "Python: "; python3 --version; printf "Sistema: "; uname -sm');pg.locator('.pty-basic-input input').press('Enter');expect(pg.locator('.pty-basic-output')).to_contain_text('Linux');capture('terminal')
     pg.keyboard.press('Control+,');pg.locator('.settings-navigation [data-setting-category="development"]').click();pg.locator('[data-platform="tools"]').first.click();expect(pg.locator('.tool-grid')).to_be_visible();capture('herramientas')
     pg.keyboard.press('Control+,');pg.locator('.settings-navigation [data-setting-category="hardware"]').click();pg.locator('#pref-hardware-enabled').check();pg.wait_for_timeout(700);pg.locator('.settings-navigation [data-setting-category="general"]').click();pg.locator('.settings-navigation [data-setting-category="hardware"]').click();expect(pg.locator('#settings-hardware-state')).to_contain_text('RAM');capture('hardware')
     assert errors==[],errors
     (a.output/'CAPTURE04_RESULTS.json').write_text(json.dumps({'transport':a.transport,'captures':captures,'errors':errors,'size':[1648,928],'editor':'base','pearl':'CSS fallback','terminal':'actual Bash PTY, base renderer','extensions':'two actual local sample VSIX packages','hardware':'actual Linux host readings, not user hardware','externalAI':'Not connected; no provider inference','notes':'Application screenshots, no compositing. Dependency engines and native window not exercised.'},ensure_ascii=False,indent=2))
    except Exception:pg.screenshot(path=str(a.output/'FAILURE.png'));raise
    finally:b.close()
  finally:app.features.shutdown();app.runner.shutdown();server.shutdown();server.server_close()
if __name__=='__main__':main()
