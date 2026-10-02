"""Explicit visual/interaction QA using disposable profiles and installations."""
from pathlib import Path
import argparse,json,sys,tempfile,threading
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.server import Application,LumenServer
from backend.uninstall import Uninstaller
from playwright.sync_api import sync_playwright,expect

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=True)
    checks=[];errors=[]
    def passed(s):checks.append(s);print('PASS',s,flush=True)
    with tempfile.TemporaryDirectory(prefix='lumen-visual-r5-') as temp:
        base=Path(temp);ws=base/'Project';ws.mkdir()
        for path,text in {'src/main.js':'function greet(name) { return `Hola, ${name}`; }\nconsole.log(greet("Lumen"));\n','src/model.js':'export const title = "Ideas en movimiento";\n','tests/check.py':'value = 42\nprint(value)\n'}.items():
            f=ws/path;f.parent.mkdir(exist_ok=True);f.write_text(text,encoding='utf-8')
        app=Application(ROOT,ws,data_dir=base/'profile');app.features.studio.update({'onboarded':True,'displayName':'Lumen'});app.features.prefs.update({'files.autoSave':False})
        server=LumenServer(0,app);threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(channel='msedge',headless=True,args=['--use-angle=swiftshader','--enable-unsafe-swiftshader'])
                page=browser.new_page(viewport={'width':1672,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(f'http://127.0.0.1:{server.server_port}',wait_until='networkidle');page.wait_for_function('window.lumen?.ready')
                page.locator('.brand').click();expect(page.locator('#lumen-home')).to_be_visible();assert app.features.studio.export()['recent']==[]
                page.screenshot(path=str(out/'r5-inicio.png'));passed('Fresh local profile has no invented recent files')
                page.locator('.home-enter').click()
                for name in ('main.js','model.js','check.py'):
                    page.keyboard.press('Control+k');page.locator('#palette-input').fill(name);page.locator('.palette-result').first.click()
                for width,height in ((1050,720),(1366,768),(1920,1080)):
                    page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(300)
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    bounds=page.locator('.editor-tabbar').bounding_box()
                    for el in page.locator('.file-tab:visible,.file-group:visible,.editor-tabbar>.icon-button:visible').all():
                        b=el.bounding_box();assert b['y']>=bounds['y'] and b['y']+b['height']<=bounds['y']+bounds['height']+1,(width,b,bounds)
                passed('File chips, groups and tab controls fit at 1050, 1366 and 1920 pixels')
                for width,height in ((1366,768),(1672,1000),(1920,1080)):
                    page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(250)
                    form=page.locator('#ai-form').bounding_box();panel=page.locator('#assistant-panel').bounding_box()
                    assert form and panel and form['y']>=panel['y'] and form['y']+form['height']<=panel['y']+panel['height'],(form,panel)
                    orb=page.locator('.assistant-hero .melody-art').bounding_box();copy=page.locator('.melody-copy').bounding_box()
                    assert orb['y']+orb['height']<=copy['y']+1,(orb,copy)
                passed('Assistant composer stays visible and sphere never overlaps the greeting')
                page.set_viewport_size({'width':1672,'height':1000})
                for key,theme in ((1,'day'),(2,'dark'),(3,'forest')):
                    page.keyboard.press(f'Control+Alt+{key}');page.wait_for_timeout(350)
                    assert page.locator('html').get_attribute('data-theme')==theme
                    page.screenshot(path=str(out/f'r5-editor-{theme}.png'))
                    page.keyboard.press('Control+k');page.locator('#palette-input').fill('model');expect(page.locator('.palette-result').first).to_contain_text('model.js');page.screenshot(path=str(out/f'r5-buscador-{theme}.png'));page.keyboard.press('Escape')
                    page.locator('.rail-settings').click()
                    for category in ('general','appearance','editor','files','terminal','extensions','security','ai','development','hardware','keys'):
                        loc=page.locator(f'.settings-navigation [data-setting-category="{category}"]')
                        assert loc.count()==1,category
                        loc.click();expect(page.locator('#settings-content')).to_be_visible()
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    page.locator('.settings-navigation [data-setting-category=appearance]').click();page.screenshot(path=str(out/f'r5-ajustes-{theme}.png'));page.keyboard.press('Escape')
                passed('Three themes apply to editor, grouped files, live search and settings categories')
                page.emulate_media(reduced_motion='reduce');page.keyboard.press('Control+k');page.wait_for_timeout(250)
                assert page.locator('.command-palette').evaluate('(e)=>e.getAnimations().every(a=>a.playState!=="running")')
                page.keyboard.press('Escape');passed('Popup transitions respect reduced motion')
                # Browser bridge delegates to the real remover on a disposable installation.
                install=base/'installed';(install/'app-0.5.2').mkdir(parents=True);(install/'app-0.5.2/lumen.exe').write_text('fixture')
                (install/'installation.json').write_text(json.dumps({'directory':'app-0.5.2'}));profile=base/'remove-profile';profile.mkdir();(profile/'studio.json').write_text('{}')
                remove=Uninstaller(install,profile,integrate_windows=False)
                page.expose_function('removerInfo',remove.info);page.expose_function('removerStart',remove.start);page.expose_function('removerStatus',remove.status)
                page.add_init_script('window.pywebview={api:{info:()=>window.removerInfo(),start:o=>window.removerStart(o),status:()=>window.removerStatus(),close:()=>{}}};')
                page.set_viewport_size({'width':960,'height':760});page.goto(f'http://127.0.0.1:{server.server_port}/uninstall.html');expect(page.locator('#review')).to_be_visible();page.screenshot(path=str(out/'r5-desinstalador.png'))
                assert not page.locator('#data').is_checked();page.locator('#data').check();page.locator('#review').click();expect(page.locator('#content')).to_contain_text('Se eliminarán los datos locales')
                page.locator('#remove').click();expect(page.locator('#content')).to_contain_text('se ha desinstalado correctamente',timeout=20000)
                assert not install.exists() and not profile.exists();assert ws.exists();passed('Graphical uninstaller review and actual removal leave unrelated projects intact')
                assert not errors,errors;passed('No uncaught JavaScript errors');browser.close()
        finally:
            server.shutdown();server.server_close();app.features.shutdown();app.runner.shutdown();(out/'r5-visual-verification.json').write_text(json.dumps({'checks':checks,'errors':errors},indent=2),encoding='utf-8')
if __name__=='__main__':main()
