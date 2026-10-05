"""R4 catalog geometry, shadow menus and real reviewed dependency installation.

Only the registry boundary uses local VSIX fixtures. Extraction, HTTP routes,
installation, persistence and the browser UI run through the actual services.
"""
import argparse,json,sys,tempfile,threading,time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.server import Application,LumenServer
from tests.test_extension_install_plan import package
from tests.test_extension_editors import install as install_editor_plugin
from playwright.sync_api import sync_playwright,expect


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=True)
    checks=[];errors=[]
    def passed(name):checks.append(name);print('PASS',name,flush=True)
    with tempfile.TemporaryDirectory(prefix='zenit-r4-ui-') as tmp:
        base=Path(tmp);ws=base/'ws';ws.mkdir();(ws/'main.js').write_text('const respuesta = 42;\nconsole.log(respuesta);\n',encoding='utf-8')
        app=Application(ROOT,ws,data_dir=base/'profile');app.workspace.trusted=True
        app.features.studio.update({'onboarded':True});app.features.prefs.update({'general.showWelcome':False,'appearance.theme':'dark','appearance.motion':False,'updates.automatic':False,'extensions.checkUpdatesOnOpen':False})
        store=app.features.extensions;install_editor_plugin(app)
        root=base/'root.vsix';root.write_bytes(package('root',['qa.child'],['qa.optional']))
        child=base/'child.vsix';child.write_bytes(package('child',['qa.shared']))
        shared=base/'shared.vsix';shared.write_bytes(package('shared'));optional=base/'optional.vsix';optional.write_bytes(package('optional'))
        files={'qa.child':child,'qa.shared':shared,'qa.optional':optional}
        def remote(eid,version='latest',progress=lambda **kw:None,cancelled=lambda:False):
            source=files[eid];size=source.stat().st_size
            progress(phase='download',received=0,total=0);time.sleep(.55)
            for received in [size//3,2*size//3,size]:
                if cancelled():raise InterruptedError('Revisión cancelada.')
                progress(phase='download',received=received,total=size);time.sleep(.45)
            return store.inspect_file(source,'Open VSX',progress,cancelled)
        server=LumenServer(0,app);threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with patch.object(store,'inspect_remote',side_effect=remote),sync_playwright() as pw:
                browser=pw.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':1500,'height':950});page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}');page.wait_for_function('window.lumen?.ready && window.lumen?.platformReady')
                page.locator('[data-file="main.js"]').first.click();editor=page.locator('.monaco-editor').first
                page.wait_for_function('document.hasFocus()');page.wait_for_timeout(1800)
                def views():return app.features.extension_runtime.request(app.workspace,{'id':'qa.editor-state','method':'command','command':'qa.views'})['result']
                initial=views();assert initial['views'] and initial['views'][0]['ranges'],initial
                page.evaluate("monaco.editor.getEditors().find(e=>e.getModel()).setSelection(new monaco.Selection(1,7,1,16))");page.wait_for_timeout(650);assert views()['views'][0]['anchor']['character']==6
                page.evaluate("const e=monaco.editor.getEditors().find(e=>e.getModel());e.getModel().setValue(Array.from({length:200},(_,i)=>'const dato'+i+' = '+i+';').join('\\n'));e.revealLineInCenter(100)")
                page.wait_for_timeout(1800);scrolled=views();assert scrolled['views'][0]['ranges'][0]['start']>40,scrolled
                assert (ws/'main.js').read_text(encoding='utf-8').startswith('const respuesta = 42;')
                passed('Real Monaco scroll and selection changes reach the Node extension without saving the edited buffer')
                editor.click(button='right',position={'x':240,'y':50});menu=page.locator('.monaco-menu .monaco-action-bar.vertical').first;expect(menu).to_be_visible()
                bounds=menu.bounding_box();assert bounds['height']<650 and bounds['y']>=0 and bounds['y']+bounds['height']<=950,(bounds)
                rows=menu.locator('.action-menu-item').filter(has_not=page.locator('.separator'))
                first=rows.first.bounding_box();assert first['height']<=30,first
                expect(menu.get_by_text('Guardar archivo',exact=True)).to_be_visible();expect(menu.get_by_text('Paleta de comandos',exact=True)).to_be_visible()
                page.screenshot(path=str(out/'editor-menu-dark.png'));page.keyboard.press('Escape');passed('Shadow-root context menu is compact, themed, within the viewport and retains editor commands')
                page.locator('[data-action="extensions"]').click();page.locator('[data-platform="extension-import"]').click();page.locator('#extension-local-path').fill(str(root));page.get_by_role('button',name='Inspeccionar',exact=True).click();expect(page.locator('#extension-prepare-plan')).to_be_visible()
                page.locator('#extension-prepare-plan').click();expect(page.locator('#extension-review-percent')).to_have_text('—');expect(page.locator('#extension-review-bar')).not_to_have_attribute('value','0')
                expect(page.locator('#extension-review-percent')).to_have_text('33%',timeout=8000);bar=page.locator('#extension-review-bar');assert float(bar.get_attribute('max'))==child.stat().st_size;assert float(bar.get_attribute('value'))==child.stat().st_size//3
                page.screenshot(path=str(out/'download-dark.png'));expect(page.locator('.extension-plan-packages')).to_be_visible(timeout=12000)
                assert len(store.list())==1;expect(page.locator('.extension-plan-packages details')).to_have_count(3);expect(page.locator('.extension-plan-packages')).not_to_contain_text('qa.optional')
                page.locator('.extension-plan-packages summary').first.click();expect(page.locator('.extension-plan-packages details').first).to_contain_text('SHA-256');page.screenshot(path=str(out/'install-plan-dark.png'))
                page.locator('#confirm-extension-install').click();expect(page.locator('#modal-backdrop')).to_have_class('modal-backdrop hidden');expect(page.locator('.extension-card')).to_have_count(4)
                assert set(store.installed)=={'qa.editor-state','qa.shared','qa.child','qa.root'};assert set(type(store)(store.prefs).installed)==set(store.installed)
                passed('Required dependency plan shows real sizes and licenses and installs persisted VSIX packages together')
                for theme in ['day','forest','dark']:
                    app.features.prefs.update({'appearance.theme':theme});page.reload();page.wait_for_function('window.lumen?.ready && window.lumen?.platformReady');page.locator('[data-action="extensions"]').click();expect(page.locator('.extension-card')).to_have_count(4)
                    for width,height in [(1500,950),(1366,768),(1100,720)]:
                        page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(120)
                        card=page.locator('.extension-card').first.bounding_box();hero=page.locator('.extension-hero').bounding_box();toolbar=page.locator('.extension-toolbar').bounding_box();summary=page.locator('.extension-catalog-summary').bounding_box()
                        assert max(abs(hero['x']-card['x']),abs(toolbar['x']-card['x']),abs(summary['x']-card['x']))<2,(hero,toolbar,summary,card)
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                        for button in page.locator('.extension-card').first.locator('button').all():
                            b=button.bounding_box();assert b['x']>=card['x'] and b['x']+b['width']<=card['x']+card['width']+1,(b,card)
                    page.set_viewport_size({'width':1500,'height':950});page.screenshot(path=str(out/f'catalog-{theme}.png'))
                passed('Catalog, search, counts and cards share an inset without overflow in three themes and three widths')
                assert not errors,errors;browser.close()
        finally:server.shutdown();server.server_close();app.features.shutdown();app.runner.shutdown()
    (out/'verification.json').write_text(json.dumps({'checks':checks,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
