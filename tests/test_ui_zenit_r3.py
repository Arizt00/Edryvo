"""Actual extension QuickInput and installer UI in Edge and the Python/Node host."""
import argparse,concurrent.futures,io,json,sys,tempfile,threading,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.server import Application,LumenServer
from tests.test_extension_quickinput import install_plugin
from playwright.sync_api import sync_playwright,expect

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=True);checks=[];errors=[]
 def passed(name):checks.append(name);print('PASS',name,flush=True)
 with tempfile.TemporaryDirectory(prefix='zenit-r3-ui-') as temp:
  base=Path(temp);ws=base/'ws';ws.mkdir();(ws/'main.py').write_text('print("Hola ñ")\n',encoding='utf-8')
  app=Application(ROOT,ws,data_dir=base/'profile');app.workspace.trusted=True;app.features.studio.update({'onboarded':True});app.features.prefs.update({'general.showWelcome':False,'appearance.theme':'dark','appearance.motion':False,'updates.automatic':False,'extensions.checkUpdatesOnOpen':False});install_plugin(app)
  raw=io.BytesIO()
  with zipfile.ZipFile(raw,'w',compression=zipfile.ZIP_DEFLATED) as z:
   z.writestr('extension/package.json',json.dumps({'publisher':'qa','name':'review','displayName':'Herramientas de proyecto','description':'Paquete real de revisión, con dependencias e icono propio.','version':'1.0.0','license':'MIT','icon':'icon.svg','extensionDependencies':['qa.quickinput','qa.missing'],'extensionPack':['qa.optional']}));z.writestr('extension/icon.svg','<svg xmlns="http://www.w3.org/2000/svg"><path fill="#8877ff" d="M0 0h40v40H0z"/></svg>');z.writestr('extension/payload.txt','x'*20000)
  package=base/'review.vsix';package.write_bytes(raw.getvalue())
  runtime=app.features.extension_runtime
  def call(name):return runtime.request(app.workspace,{'id':'qa.quickinput','method':'command','command':name}).get('result')
  server=LumenServer(0,app);threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   with sync_playwright() as pw,concurrent.futures.ThreadPoolExecutor() as pool:
    browser=pw.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':1500,'height':950});page.on('pageerror',lambda e:errors.append(str(e)));page.goto(f'http://127.0.0.1:{server.server_port}');page.wait_for_function('window.lumen?.ready && window.lumen?.platformReady')
    future=pool.submit(call,'qa.pick');expect(page.locator('.zenit-quickinput')).to_be_visible(timeout=12000);page.get_by_role('button',name='Atrás',exact=True).click();expect(page.locator('#zenit-quick-title')).to_have_text('Paso anterior');page.get_by_role('button',name='Actualizar opción').click();expect(page.get_by_role('option')).to_contain_text('Actualizada ñ');page.locator('.zenit-quick-field input').fill('nuevo');expect(page.get_by_role('option')).to_contain_text('nuevo ñ');page.screenshot(path=str(out/'quickinput-dark.png'));page.keyboard.press('Enter');result=future.result(10);assert result['tag']==42 and result['backPressed']==1 and result['itemPressed']==1;expect(page.locator('.zenit-quickinput')).to_have_count(0);passed('Dynamic QuickPick, Back and item buttons reach the real extension objects')
    future=pool.submit(call,'qa.input');expect(page.locator('.zenit-quickinput')).to_be_visible();expect(page.locator('.zenit-quick-validation')).to_contain_text('tres letras');page.keyboard.press('Enter');page.wait_for_timeout(100);assert not future.done();page.locator('.zenit-quick-field input').fill('creación');expect(page.locator('.zenit-quick-validation')).to_be_empty();page.keyboard.press('Enter');assert future.result(10)=='creación';passed('InputBox validation blocks invalid acceptance and preserves accented input')
    future=pool.submit(call,'qa.multi');expect(page.locator('.zenit-quickinput')).to_be_visible();expect(page.get_by_role('option',name='Python')).to_have_attribute('aria-selected','true');page.get_by_role('option',name='Rust').click();page.get_by_role('button',name='Aceptar',exact=True).click();assert [x['label'] for x in future.result(10)]==['Python','Rust'];passed('Multiple selection preserves initial picks and excludes separators')
    future=pool.submit(call,'qa.input');expect(page.locator('.zenit-quickinput')).to_be_visible();expect(page.locator('#zenit-quick-title')).to_have_text('Nombre del proyecto');page.keyboard.press('Escape');assert future.result(10) is None;passed('Escape cancels and removes the extension input')
    future=pool.submit(call,'qa.reshow');expect(page.locator('#zenit-quick-title')).to_have_text('Primer paso');page.keyboard.press('Escape');expect(page.locator('#zenit-quick-title')).to_have_text('Segundo paso');page.keyboard.press('Escape');assert future.result(10) is None;passed('An extension can reuse its original input after hiding it')
    page.locator('[data-file="main.py"]').first.click();page.locator('.monaco-editor textarea').first.focus();page.keyboard.press('F1');expect(page.locator('.quick-input-widget')).to_be_visible();style=page.locator('.quick-input-widget .monaco-inputbox input').evaluate('(e)=>({bg:getComputedStyle(e).backgroundColor,outline:getComputedStyle(e).outlineStyle})');assert style['bg']=='rgba(0, 0, 0, 0)' and style['outline']=='none',style;bounds=page.locator('.quick-input-widget').bounding_box();editor=page.locator('.monaco-editor').first.bounding_box();assert bounds['width']>=400 and bounds['x']>=editor['x'] and bounds['x']+bounds['width']<=editor['x']+editor['width']+1,(bounds,editor);page.screenshot(path=str(out/'command-palette-dark.png'));page.keyboard.press('Escape');passed('Monaco command palette has a themed rounded field without a square focus border')
    page.locator('[data-action="extensions"]').click();expect(page.locator('#extension-results')).to_be_visible();page.locator('[data-platform="extension-import"]').click();page.locator('#extension-local-path').fill(str(package));page.get_by_role('button',name='Inspeccionar',exact=True).click();expect(page.locator('#confirm-extension-install')).to_be_visible(timeout=15000);expect(page.locator('.extension-install-facts')).to_contain_text('KiB');expect(page.locator('.extension-dependency-review')).to_contain_text('No instalada');expect(page.locator('.extension-review-heading img')).to_be_visible();page.screenshot(path=str(out/'installer-dark.png'));page.locator('#confirm-extension-install').click();expect(page.locator('#modal-backdrop')).to_have_class('modal-backdrop hidden');expect(page.locator('.extension-card').filter(has_text='Herramientas de proyecto')).to_be_visible();assert 'qa.review' in app.features.extensions.installed;passed('Installer shows actual sizes, icons and dependency status and installs a real VSIX')
    for theme in ['day','forest','dark']:
     app.features.prefs.update({'appearance.theme':theme});page.reload();page.wait_for_function('window.lumen?.ready && window.lumen?.platformReady');page.locator('[data-action="extensions"]').click();expect(page.locator('#extension-results')).to_be_visible()
     for width,height in [(1500,950),(1366,768),(1100,720)]:
      page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(150)
      assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
      a=page.locator('.dock-slot:has(#assistant-panel)').bounding_box();ed=page.locator('#editor-panel').bounding_box();assert abs(a['y']-ed['y'])<2 and abs(a['height']-ed['height'])<2,(a,ed)
     page.screenshot(path=str(out/f'panels-{theme}.png'))
    passed('Opaque themed panels retain alignment at three widths in all three built-in themes')
    assert not errors,errors;browser.close()
  finally:server.shutdown();server.server_close();app.features.shutdown();app.runner.shutdown()
 (out/'verification.json').write_text(json.dumps({'checks':checks,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
