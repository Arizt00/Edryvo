#!/usr/bin/env python3
"""0.4 UI flows against a real isolated backend. Bridge is not a CSP/E2E test."""
from __future__ import annotations
import argparse
import time
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.server import Application,LumenServer
from backend.preferences import atomic_json
from ui_harness import prepare

def main():
    p=argparse.ArgumentParser();p.add_argument('--transport',choices=['direct','bridge'],default='direct');p.add_argument('--chromium');p.add_argument('--output',type=Path,default=ROOT/'reports/platform04');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    from playwright.sync_api import sync_playwright,expect
    checks=[];errors=[]
    def passed(msg):checks.append(msg);print(time.strftime('%H:%M:%S'),'PASS',msg,flush=True)
    with tempfile.TemporaryDirectory(prefix='lumen04-ui-') as temp:
        temp=Path(temp);ws=temp/'MyProject';shutil.copytree(ROOT/'workspace/MyProject',ws,ignore=shutil.ignore_patterns('.lumen'));data=temp/'data'
        app=Application(ROOT,ws,data_dir=data);server=LumenServer(0,app);threading.Thread(target=server.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{server.server_port}'
        atomic_json(data/'instance.json',{'url':base,'pid':os.getpid()})
        try:
            with sync_playwright() as pw:
                opts={'headless':True,'args':['--no-sandbox','--disable-dev-shm-usage']}
                if a.chromium:opts['executable_path']=a.chromium
                b=pw.chromium.launch(**opts);pg=b.new_page(viewport={'width':1648,'height':928});pg.set_default_timeout(7000);pg.on('pageerror',lambda error:errors.append(str(error)))
                try:
                    if a.transport=='bridge':prepare(pg,base)
                    else:pg.goto(base)
                    pg.wait_for_function('window.lumen?.platformReady');passed('Startup: 0.4 UI connected to actual Python platform routes')
                    assert pg.evaluate('lumen.editorKind')=='base';assert not app.workspace.trusted
                    for key,theme in [('1','day'),('2','dark'),('3','forest')]:
                        pg.keyboard.press('Control+Alt+'+key);pg.wait_for_function(f'lumen.theme==="{theme}"');pg.wait_for_timeout(300);pg.screenshot(path=str(a.output/(theme+'.png')))
                    passed('Three shared themes render with actual platform controls')
                    pg.keyboard.press('Control+Alt+1');pg.keyboard.press('Control+b');pg.wait_for_timeout(260);before=pg.evaluate('lumen.layout')
                    pg.keyboard.press('Control+Alt+f');pg.wait_for_function('lumen.layout.preset==="focus"');pg.screenshot(path=str(a.output/'focus.png'))
                    pg.keyboard.press('Control+Alt+f');pg.wait_for_function('lumen.layout.preset!=="focus"');assert pg.evaluate('lumen.layout')==before
                    passed('Repeated focus shortcut restores full previous layout including collapse')
                    env={**os.environ,'LUMEN_DATA_DIR':str(data)}
                    for expected in (True,False):
                        subprocess.run([sys.executable,str(ROOT/'lumen.py'),'focus'],env=env,check=True,capture_output=True)
                        pg.wait_for_function(f'(lumen.layout.preset==="focus") === {str(expected).lower()}')
                    passed('External CLI focus command toggles through real authenticated loopback API')
                    pg.keyboard.press('Control+b');pg.wait_for_timeout(260)
                    pg.locator('#terminal-input').fill('lumen focus');pg.locator('#terminal-input').press('Enter');pg.wait_for_function('lumen.layout.preset==="focus"')
                    subprocess.run([sys.executable,str(ROOT/'lumen.py'),'focus'],env=env,check=True,capture_output=True)
                    pg.wait_for_function('lumen.layout.preset!=="focus"')
                    assert pg.evaluate('lumen.layout.preset')!='focus';passed('Lumen command console recognizes the same focus toggle')
                    pg.keyboard.press('Control+,');expect(pg.locator('#settings-content')).to_be_visible()
                    pg.keyboard.press('Control+Alt+f');pg.wait_for_function('lumen.layout.preset==="focus" && lumen.platformPage===null');pg.keyboard.press('Control+Alt+f');pg.wait_for_function('lumen.layout.preset!=="focus"');pg.keyboard.press('Control+,');expect(pg.locator('#settings-content')).to_be_visible();passed('Focus invoked from settings closes the auxiliary page and restores the editor workspace')
                    pg.select_option('#pref-general-locale','en');pg.wait_for_function('document.documentElement.lang==="en"');expect(pg.locator('.platform-title')).to_contain_text('Settings')
                    pg.select_option('#pref-general-locale','es');pg.wait_for_function('document.documentElement.lang==="es"');assert app.features.prefs.get('general.locale')=='es'
                    passed('Language switch updates shell and settings; preferences reach disk')
                    for category in ('general','appearance','editor','files','terminal','extensions','security','ai','development','hardware','keys'):
                        pg.locator('.settings-navigation [data-setting-category="'+category+'"]').click();expect(pg.locator('#settings-content')).not_to_be_empty();assert pg.evaluate('document.documentElement.scrollWidth===innerWidth')
                    passed('All eleven settings categories render without page overflow')
                    pg.locator('.settings-navigation [data-setting-category="editor"]').click();pg.locator('#pref-editor-fontSize').fill('15');pg.locator('#pref-editor-fontSize').press('Tab');pg.wait_for_function('getComputedStyle(document.querySelector(".code-input")).fontSize==="15px"');pg.locator('#pref-editor-fontSize').fill('13');pg.locator('#pref-editor-fontSize').press('Tab')
                    pg.locator('#pref-editor-minimap').uncheck();pg.wait_for_timeout(180);assert not pg.locator('.code-minimap').is_visible();pg.locator('#pref-editor-minimap').check()
                    assert pg.locator('#pref-editor-wordWrap').is_disabled();passed('Editor settings apply; Monaco-only features are explicitly unavailable in base editor')
                    pg.locator('.settings-navigation [data-setting-category="appearance"]').click();pg.locator('#pref-appearance-motion').uncheck();pg.wait_for_function('!lumen.motionEnabled');pg.locator('#pref-appearance-motion').check();pg.wait_for_function('lumen.motionEnabled');pg.screenshot(path=str(a.output/'settings-appearance.png'))
                    passed('Animation preference changes the actual motion controller')
                    pg.locator('.settings-navigation [data-setting-category="ai"]').click()
                    for provider in ('openai','anthropic','gemini','copilot','ollama'):
                        pg.locator('[data-provider="'+provider+'"]').click();expect(pg.locator('[data-provider="'+provider+'"]')).to_have_class('provider-card selected')
                    pg.locator('[data-provider="openai"]').click();pg.locator('#provider-key').fill('TEST_ONLY_UI_SECRET_12345');pg.locator('#provider-credential-form button[type=submit]').click();pg.wait_for_timeout(250)
                    assert app.features.ai.vault.get('openai')[0]=='TEST_ONLY_UI_SECRET_12345';assert pg.locator('#provider-key').input_value()==''
                    assert 'TEST_ONLY_UI_SECRET' not in pg.locator('#platform-page').inner_text();assert 'TEST_ONLY_UI_SECRET' not in (data/'settings.json').read_text()
                    passed('Five provider cards; credential field clears and secret stays out of persisted settings')
                    pg.locator('#provider-forget-key').click();pg.wait_for_timeout(200);pg.screenshot(path=str(a.output/'settings-ai.png'))
                    pg.locator('#provider-fetch-models').click();expect(pg.locator('#toasts')).to_contain_text('desactivada');passed('Cloud-disabled request fails explicitly instead of pretending a model is connected')
                    pg.locator('.settings-navigation [data-setting-category="extensions"]').click();pg.locator('#pref-extensions-network').uncheck();pg.wait_for_timeout(150)
                    pg.keyboard.press('Control+Alt+e');pg.wait_for_function('lumen.platformPage==="extensions"');pg.locator('[data-extension-mode="browse"]').first.click();expect(pg.locator('#extension-results')).to_contain_text('catálogo no está disponible')
                    passed('Marketplace honors its network setting and offers local import on failure')
                    pg.locator('[data-extension-mode="installed"]').click()
                    for file in sorted((ROOT/'examples/extensions').glob('*.vsix')):
                        pg.locator('.extension-hero-actions [data-platform="extension-import"]').click();pg.locator('#extension-local-path').fill(str(file));pg.locator('#extension-import-form button').click();expect(pg.locator('#modal-title')).to_contain_text('Revisión');expect(pg.locator('.hash-line code')).to_have_text(__import__('hashlib').sha256(file.read_bytes()).hexdigest());pg.locator('#confirm-extension-install').click();pg.wait_for_timeout(300)
                    expect(pg.locator('.extension-card')).to_have_count(2);pg.wait_for_timeout(400);expect(pg.locator('#platform-page')).to_be_visible();pg.screenshot(path=str(a.output/'extensions.png'))
                    passed('Actual local VSIX inspection, SHA-256 review, installation and contribution loading')
                    pg.locator('[data-extension-toggle="lumen.starter-snippets"]').click();pg.wait_for_timeout(160);assert len(app.features.extensions.contributions()['snippets'])==0
                    pg.locator('[data-extension-toggle="lumen.starter-snippets"]').click();pg.wait_for_timeout(160);assert len(app.features.extensions.contributions()['snippets'])==2
                    passed('Disabling and enabling extensions changes actual contributed snippets')
                    pg.keyboard.press('Escape');pg.keyboard.press('Control+Alt+t');expect(pg.locator('.terminal-profile-list')).to_be_visible();pg.locator('[data-open-terminal="bash"]').click();expect(pg.locator('#confirm-yes')).to_be_visible();pg.locator('#confirm-yes').click();expect(pg.locator('.pty-basic-input input')).to_be_visible()
                    pg.locator('.pty-basic-input input').fill('export LUMEN_UI_VAR=56823; printf "UI_%s\\n" "$LUMEN_UI_VAR"');pg.locator('.pty-basic-input input').press('Enter');expect(pg.locator('.pty-basic-output')).to_contain_text('UI_56823')
                    pg.locator('.pty-basic-input input').fill('printf "PERSIST_%s\\n" "$LUMEN_UI_VAR"');pg.locator('.pty-basic-input input').press('Enter');expect(pg.locator('.pty-basic-output')).to_contain_text('PERSIST_56823');pg.screenshot(path=str(a.output/'terminal.png'))
                    passed('Interactive Bash PTY preserves shell state between submissions')
                    pg.keyboard.press('Control+j');pg.keyboard.press('Control+j');expect(pg.locator('.pty-basic-output')).to_contain_text('PERSIST_56823')
                    pg.locator('.pty-basic-input input').fill('sleep 20');pg.locator('.pty-basic-input input').press('Enter');pg.wait_for_timeout(200);pg.locator('.pty-interrupt').click();pg.locator('.pty-basic-input input').fill('echo UI_INTERRUPT_OK');pg.locator('.pty-basic-input input').press('Enter');expect(pg.locator('.pty-basic-output')).to_contain_text('UI_INTERRUPT_OK')
                    passed('Terminal survives panel visibility changes and accepts interrupt input')
                    pg.locator('.pty-tab-close').click();pg.locator('#confirm-yes').click();pg.wait_for_timeout(150);assert all(x.closed for x in app.features.terminals.sessions.values());passed('Terminal close confirmation terminates the actual session')
                    pg.keyboard.press('Control+,');pg.locator('.settings-navigation [data-setting-category="development"]').click();pg.screenshot(path=str(a.output/'settings-development.png'))
                    pg.locator('[data-platform="tools"]').first.click();expect(pg.locator('.tools-content')).to_be_visible();expect(pg.locator('.tool-sections')).to_contain_text('CMake');pg.screenshot(path=str(a.output/'tools.png'))
                    passed('Development settings and tool inventory use detected executable paths')
                    pg.keyboard.press('Control+,');pg.locator('.settings-navigation [data-setting-category="hardware"]').click();pg.locator('#pref-hardware-enabled').check();pg.wait_for_timeout(1000)
                    pg.locator('.settings-navigation [data-setting-category="general"]').click();pg.locator('.settings-navigation [data-setting-category="hardware"]').click();expect(pg.locator('#settings-hardware-state')).to_contain_text('RAM');assert app.features.hardware.sample()['enabled'];pg.screenshot(path=str(a.output/'hardware.png'))
                    passed('Hardware monitoring opt-in uses real operating-system readings')
                    for width,height in ((1024,768),(1366,768),(1920,1080)):
                        pg.set_viewport_size({'width':width,'height':height});pg.wait_for_timeout(180);assert pg.evaluate('document.documentElement.scrollWidth===innerWidth')
                    passed('Settings page remains contained at 1024, 1366 and 1920 px')
                    pg.set_viewport_size({'width':1648,'height':928});pg.keyboard.press('Escape');pg.keyboard.press('Control+Alt+3');pg.wait_for_timeout(250);pg.screenshot(path=str(a.output/'forest-final.png'))
                    pg.keyboard.press('Control+Alt+1');pg.keyboard.press('Control+,');pg.locator('.settings-navigation [data-setting-category="appearance"]').click();pg.screenshot(path=str(a.output/'day-settings-final.png'))
                    assert errors==[],errors;passed('No unhandled JavaScript errors across 0.4 platform flows')
                    (a.output/'UI04_RESULTS.json').write_text(json.dumps({'transport':a.transport,'checks':len(checks),'passed':checks,'errors':errors,'editor':'base','graphics':'CSS fallback','terminal':'real POSIX PTY + base viewer','network':'No external provider calls; offline VSIX fixtures'},ensure_ascii=False,indent=2))
                except Exception:
                    pg.screenshot(path=str(a.output/'FAILURE.png'));print('ERRORS',errors);print('PAGE',pg.locator('#platform-page').inner_text()[:1500]);raise
                finally:b.close()
        finally:app.features.shutdown();app.runner.shutdown();server.shutdown();server.server_close()
if __name__=='__main__':main()
