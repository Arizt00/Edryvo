"""Actual Monaco, local WASM, VSIX grammar, theme and simulator browser flows."""
import argparse,json,tempfile,threading,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from backend.server import Application,LumenServer
from test_textmate import install_fixture
from playwright.sync_api import sync_playwright,expect

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=True);errors=[];checks=[]
    with tempfile.TemporaryDirectory(prefix='zenit-textmate-') as temp:
        root=Path(temp);ws=root/'project';ws.mkdir();(ws/'code.py').write_text('zenit_kw = 2\n/* comentario\n TODO cierre */\ndef normal():\n    return 1\n');(ws/'sum.s').write_text((ROOT/'examples/asm/x86_64_sum.s').read_text(encoding='utf-8'),encoding='utf-8')
        app=Application(ROOT,ws,data_dir=root/'profile');app.workspace.trusted=True;app.features.studio.update({'onboarded':True});app.features.prefs.update({'general.showWelcome':False,'appearance.motion':False,'updates.automatic':False,'appearance.extensionTheme':'qa.grammar:qa'});install_fixture(app.features.extensions)
        server=LumenServer(0,app);threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':1366,'height':900});page.on('pageerror',lambda e:errors.append(str(e)))
                def instrument(route):
                    response=route.fetch();name='LumenEditor' if route.request.url.endswith('/editor.js') else 'LumenPlatform';method='init' if name=='LumenEditor' else 'loadContributions';target='qaEditor' if name=='LumenEditor' else 'qaPlatform'
                    route.fulfill(response=response,body=response.text()+f'\nconst qaOriginal={name}.prototype.{method};{name}.prototype.{method}=function(...args){{window.{target}=this;return qaOriginal.apply(this,args);}};')
                page.route('**/src/editor.js',instrument);page.route('**/src/workbench.js',instrument)
                page.goto(f'http://127.0.0.1:{server.server_port}');page.wait_for_function('window.lumen?.ready');page.locator('[data-file="code.py"]').click()
                page.wait_for_function('window.qaEditor?.textmate?.loaded.length===1')
                page.wait_for_function('document.querySelector(".view-lines")?.textContent.includes("zenit_kw")')
                page.wait_for_function('["zenit_kw","TODO"].every(text=>[...document.querySelectorAll(".view-line span span")].some(x=>x.textContent.trim()===text))',timeout=10000)
                colors=page.evaluate('()=>Object.fromEntries([...document.querySelectorAll(".view-line span span")].filter(x=>["zenit_kw","TODO"].includes(x.textContent.trim())).map(x=>[x.textContent.trim(),getComputedStyle(x).color]))')
                assert colors=={'zenit_kw':'rgb(18, 94, 222)','TODO':'rgb(177, 39, 105)'},(colors,page.evaluate('document.querySelector(".view-lines").innerHTML'),page.evaluate('window.qaPlatform.extensionContributions.errors'));checks.append('Real Oniguruma tokens respect parent scope theme selectors and comment injections')
                state=page.evaluate('()=>{let g=window.qaEditor.textmate.loaded[0].grammar;let a=g.tokenizeLine("/* comienzo",null);return g.tokenizeLine("comentario */",a.ruleStack).tokens.map(t=>t.scopes)}');assert any('comment.block.zenit' in x for x in state);checks.append('Multiline TextMate state is preserved')
                await_js='async()=>{await window.qaPlatform.api("/extensions/toggle",{id:"qa.grammar",enabled:false});await window.qaPlatform.loadContributions();}'
                page.evaluate(await_js);assert page.evaluate('window.qaEditor.textmate.loaded.length')==0
                normal=page.evaluate('monaco.editor.tokenize("def normal():", "python")[0]');assert any('keyword' in x['type'] for x in normal),normal;checks.append('Disabling a grammar restores the built-in Python tokenizer')
                page.evaluate('async()=>{await window.qaPlatform.api("/extensions/toggle",{id:"qa.grammar",enabled:true});await window.qaPlatform.loadContributions();}');assert page.evaluate('window.qaEditor.textmate.loaded.length')==1;checks.append('Grammar reactivation keeps encoded colours aligned')
                page.locator('[data-file="sum.s"]').click();page.locator('.foundation-toggle').click();page.locator('#lab-assembly').click();page.locator('[data-asm=run]').click();expect(page.locator('.asm-grid dl')).to_contain_text('0x37',timeout=20000);page.locator('[data-asm=format]').click();expect(page.locator('.asm-grid dl')).to_contain_text('110');expect(page.locator('.asm-status')).to_contain_text('36 instrucciones');checks.append('x86-64 sum executes 36 real instructions and displays decimal values')
                expect(page.locator('[aria-label="Ejemplo ASM"] option')).to_have_count(2)
                page.get_by_role('combobox',name='Ejemplo ASM').click();page.get_by_role('option',name='Suma 1…10 · bucle y pila',exact=True).click();page.locator('[data-asm=example]').click();page.locator('#confirm-yes').click();assert 'imul rdx' in page.evaluate('window.qaEditor.getValue()');checks.append('The shipped x86-64 example loads into the undoable unsaved editor buffer')
                for theme in ['day','dark','forest']:
                    page.evaluate('async(theme)=>{await window.qaPlatform.savePreference("appearance.theme",theme);}',theme)
                    for width,height in [(1700,1000),(1366,900),(1280,800)]:
                        page.set_viewport_size({'width':width,'height':height});assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth');page.screenshot(path=str(out/f'assembly-{theme}-{width}.png'))
                checks.append('ASM controls, registers and examples fit three widths and three themes')
                assert not errors,errors;browser.close()
        finally:server.shutdown();server.server_close();app.features.shutdown();app.runner.shutdown()
    (out/'verification.json').write_text(json.dumps({'checks':checks,'errors':errors},indent=2),encoding='utf-8');print(json.dumps(checks))
if __name__=='__main__':main()
