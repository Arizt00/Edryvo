"""Windows/Edge integration: real server, disposable workspace, no external AI/SDK calls.

Run explicitly: python tests/test_ui052.py --output <directory>
Software WebGL2 makes the shader check reproducible on headless build machines.
"""
from pathlib import Path
import argparse
import json
import shutil
import sys
import tempfile
import threading
import time
import zipfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.server import Application, LumenServer
from playwright.sync_api import sync_playwright, expect

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True);checks=[];errors=[]
    def passed(name): checks.append(name); print('PASS',name,flush=True)
    with tempfile.TemporaryDirectory(prefix='lumen-ui-052-') as tmp:
        base=Path(tmp);ws=base/'MyProject';shutil.copytree(ROOT/'workspace/MyProject',ws)
        (ws/'debug_demo.py').write_text('value = 2\nvalue += 3\nprint("lumen-debug", value)\n',encoding='utf-8')
        app=Application(ROOT,ws,data_dir=base/'profile');server=LumenServer(0,app)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(channel='msedge',headless=True,args=['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist'])
                page=browser.new_page(viewport={'width':1672,'height':941},device_scale_factor=1)
                page.on('pageerror',lambda e:errors.append(str(e)+' '+(e.stack or '')))
                page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
                page.goto(f'http://127.0.0.1:{server.server_port}',wait_until='networkidle')
                page.wait_for_function('window.lumen?.ready')
                expect(page.locator('#onboarding')).to_be_visible()
                page.screenshot(path=str(args.output/'lumen-0.5.2-primer-inicio.png'))
                page.locator('#onboard-next').click();page.locator('#onboard-name').fill('Lumen QA');page.locator('#onboard-next').click();page.locator('#onboard-next').click()
                expect(page.locator('#home-name')).to_have_text('Lumen QA')
                assert app.features.studio.export()['onboarded']
                assert app.features.prefs.get('editor.fontSize')==14
                passed('First launch saves profile, layout and preferences')
                page.wait_for_function('document.querySelector(".home-hero canvas")?.dataset.engine==="WebGL2" && document.querySelector(".home-hero .gpu-ready")')
                assert page.evaluate('getComputedStyle(document.querySelector("#workspace")).opacity')=='0'
                scenes=page.evaluate('BABYLON.Engine.Instances.map(e=>({api:e.webGLVersion,meshes:e.scenes.map(s=>s.meshes.length)}))')
                assert any(9 in e['meshes'] for e in scenes),scenes
                a=page.locator('.home-hero canvas').screenshot();page.wait_for_timeout(400);b=page.locator('.home-hero canvas').screenshot();assert a!=b
                passed('WebGL2 renders animated Fresnel sphere, crystals and ribbon; home conceals editor')
                page.locator('[data-studio=profile]').click();page.locator('#profile-picture').set_input_files(str(ROOT/'web/assets/landscape-day.png'))
                expect(page.locator('.profile-file-state')).to_have_text('landscape-day.png')
                page.locator('#profile-form button.primary-button').click();expect(page.locator('.profile-photo img')).to_be_visible()
                assert app.features.studio.export()['avatar'].startswith('data:image/webp;base64,')
                passed('Profile picture upload is resized and persisted')
                page.locator('.home-enter').click();page.locator('.new-tab').click();page.locator('#new-file-name').fill('qa/new-script.py');page.locator('#new-file-form button[type=submit]').click()
                page.wait_for_function('window.lumen.activeFile==="qa/new-script.py"')
                page.locator('.monaco-editor textarea').focus();page.keyboard.insert_text('print("lumen-run-052")\n');page.keyboard.press('Control+s')
                expect(page.locator('.file-tab.active')).not_to_contain_text('●')
                page.wait_for_timeout(300);assert (ws/'qa/new-script.py').read_text(encoding='utf-8')=='print("lumen-run-052")\n'
                passed('Create, edit and save nested Python file through Monaco')
                page.locator('.run-button').click();page.locator('#confirm-yes').click()
                expect(page.locator('#terminal-scroll')).to_contain_text('lumen-run-052',timeout=15000)
                expect(page.locator('#terminal-scroll')).to_contain_text('Process exited with code 0',timeout=15000)
                passed('Run executes real Python and returns successful exit status')
                page.locator('.rail-item[data-view=search]').click();page.locator('#studio-search').fill('lumen-run-052')
                expect(page.locator('.search-hit')).to_have_count(1);expect(page.locator('.search-hit')).to_contain_text('new-script.py')
                page.locator('#search-extension').fill('*.cs');expect(page.locator('.search-hit')).to_have_count(0)
                page.locator('#search-extension').fill('');page.locator('[data-search-mode=files]').click();page.locator('#studio-search').fill('debug_demo');expect(page.locator('.search-hit')).to_have_count(1)
                page.locator('.search-hit').click();page.wait_for_function('window.lumen.activeFile==="debug_demo.py"')
                passed('Search content, extension filter and filename navigation')
                page.keyboard.press('Control+k');page.locator('#palette-input').fill('Camera.cs');page.keyboard.press('Enter');page.wait_for_function('window.lumen.activeFile.endsWith("Camera.cs")')
                passed('Command palette opens files using keyboard')
                page.locator('.rail-settings').click()
                for category in ['general','appearance','editor','files','terminal','extensions','security','ai','development','hardware','keys']:
                    loc=page.locator(f'.settings-navigation [data-setting-category="{category}"]')
                    assert loc.count()==1,category;loc.click();expect(page.locator('#settings-content')).to_be_visible()
                page.locator('.settings-navigation [data-setting-category=editor]').click();page.locator('#pref-editor-fontSize').fill('15');page.locator('#pref-editor-fontSize').press('Tab')
                page.wait_for_timeout(250);assert app.features.prefs.get('editor.fontSize')==15
                page.locator('.settings-navigation [data-setting-category=general]').click();page.screenshot(path=str(args.output/'lumen-0.5.2-ajustes.png'))
                page.keyboard.press('Escape');passed('Settings categories and persistent editor preferences')
                page.locator('.rail-item[data-action=extensions]').click();page.locator('[data-platform=extension-import]').first.click()
                fixture=next((ROOT/'examples/extensions').glob('*.vsix'));page.locator('#extension-local-path').fill(str(fixture));page.locator('#extension-import-form button').click();page.locator('#confirm-extension-install').click()
                expect(page.locator('.extension-card')).to_have_count(1)
                eid=app.features.extensions.list()[0]['id'];page.locator('[data-extension-toggle]').click();expect(page.locator('.extension-card')).to_contain_text('Inactiva');page.locator('[data-extension-toggle]').click();expect(page.locator('.extension-card')).to_contain_text('Activa')
                page.locator('[data-platform=extension-export]').click()
                with page.expect_download() as download:page.locator('[data-save-vsix]').click()
                saved=base/'exported.vsix';download.value.save_as(str(saved))
                with zipfile.ZipFile(saved) as z:assert 'extension/package.json' in z.namelist()
                page.screenshot(path=str(args.output/'lumen-0.5.2-extensiones.png'))
                page.locator('[data-extension-remove]').click();page.locator('#confirm-yes').click();expect(page.locator('.extension-card')).to_have_count(0)
                assert not app.features.extensions.list();passed('VSIX inspect/install/toggle/export/uninstall without running extension executables')
                page.locator('.rail-item[data-view=run]').click();page.locator('#debug-file-trigger').click();page.get_by_role('option',name='debug_demo.py',exact=True).click();page.locator('#debug-breakpoints').fill('3');page.locator('#debug-start').click()
                expect(page.locator('#debug-state')).to_contain_text('línea 1');page.locator('[data-debug=next]').click();expect(page.locator('#debug-state')).to_contain_text('línea 2');expect(page.locator('#debug-variables')).to_contain_text('2')
                page.locator('[data-debug=continue]').click();expect(page.locator('#debug-state')).to_contain_text('línea 3');expect(page.locator('#debug-variables')).to_contain_text('5');page.screenshot(path=str(args.output/'lumen-0.5.2-depuracion.png'))
                page.locator('[data-debug=continue]').click();expect(page.locator('#debug-output')).to_contain_text('lumen-debug 5');expect(page.locator('#debug-state')).to_contain_text('Ejecución finalizada')
                passed('Debugger pauses, steps, inspects locals, reaches breakpoint and returns stdout')
                page.locator('.rail-item[data-view=explorer]').click()
                page.keyboard.press('Control+Alt+t');page.locator('[data-open-terminal=powershell]').click()
                expect(page.locator('.pty-session .xterm')).to_be_visible()
                session=app.features.terminals.get(app.features.terminals.list()[0]['id'])
                deadline=time.monotonic()+15
                while 'MyProject>' not in session.read(0)['data'] and time.monotonic()<deadline:page.wait_for_timeout(100)
                assert 'MyProject>' in session.read(0)['data'],session.read(0)
                page.locator('.pty-session .xterm-helper-textarea').focus();page.keyboard.type("Write-Output ('lumen-' + 'pty-052')");page.keyboard.press('Enter')
                deadline=time.monotonic()+10
                while 'lumen-pty-052' not in session.read(0)['data'] and time.monotonic()<deadline:page.wait_for_timeout(100)
                assert 'lumen-pty-052' in session.read(0)['data'],session.read(0)
                page.locator('[data-pty-close]').click();page.locator('#confirm-yes').click();expect(page.locator('.pty-session')).to_have_count(0);passed('Windows ConPTY interactive PowerShell input/output and close')
                for width,height in [(1920,1080),(1672,941),(1366,768),(1050,680)]:
                    page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(300)
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,height,'horizontal overflow')
                    bounds=page.evaluate('Array.from(document.querySelectorAll("#editor-panel,.topbar,.statusbar")).map(e=>{let r=e.getBoundingClientRect();return {x:r.x,y:r.y,right:r.right,bottom:r.bottom}})')
                    assert all(r['x']>=0 and r['right']<=width+1 and r['y']>=0 and r['bottom']<=height+1 for r in bounds),(width,height,bounds)
                    page.screenshot(path=str(args.output/f'lumen-0.5.2-editor-{width}.png'))
                passed('Main layout within viewport at 1050, 1366, 1672 and 1920 px')
                page.set_viewport_size({'width':1672,'height':941});page.locator('.brand').click();page.wait_for_timeout(400);page.screenshot(path=str(args.output/'lumen-0.5.2-inicio.png'))
                page.reload(wait_until='networkidle');page.wait_for_function('window.lumen?.ready');expect(page.locator('#onboarding')).to_have_count(0);expect(page.locator('#home-name')).to_have_text('Lumen QA');passed('Reload restores profile and does not repeat first launch')
                page.goto(f'http://127.0.0.1:{server.server_port}/setup.html');page.wait_for_timeout(500);page.screenshot(path=str(args.output/'lumen-0.5.2-instalador.png'))
                page.locator('#setup-next').click();page.locator('#setup-next').click();expect(page.locator('.package-option')).to_have_count(12);page.locator('#setup-next').click();expect(page.locator('#setup-next')).to_be_disabled();passed('Installer preview separates language, component and location steps, including ASM and mobile tools')
                assert not errors,errors;passed('No uncaught JavaScript errors or browser console errors')
                browser.close()
        finally:
            server.shutdown();server.server_close();app.features.shutdown();app.runner.shutdown()
    (args.output/'ui-verification-0.5.2.json').write_text(json.dumps({'checks':checks,'errors':errors,'renderer':'WebGL2 via Edge SwiftShader (test only)'},indent=2),encoding='utf-8')
    print(f'{len(checks)} integration scenarios passed')
if __name__=='__main__':main()
