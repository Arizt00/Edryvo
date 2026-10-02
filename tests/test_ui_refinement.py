#!/usr/bin/env python3
"""Lumen 0.3 carried-forward UI regression, with direct or explicitly labelled bridge transport.

The bridge exercises the owned UI against a real temporary Python workspace,
not HTTP module loading, native localStorage durability or pywebview.
"""
from __future__ import annotations
import argparse
import json
import shutil
import sys
import tempfile
import threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.server import Application,LumenServer
from ui_harness import prepare


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--transport',choices=['direct','bridge'],default='direct')
    parser.add_argument('--chromium')
    parser.add_argument('--output',type=Path,default=ROOT/'reports/refinement')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    from playwright.sync_api import sync_playwright,expect
    checks=[];errors=[]
    def passed(text): checks.append(text);print('PASS',text,flush=True)
    with tempfile.TemporaryDirectory(prefix='lumen-ui-v2-') as temporary:
        project=Path(temporary)/'MyProject';shutil.copytree(ROOT/'workspace/MyProject',project,ignore=shutil.ignore_patterns('.lumen'))
        app=Application(ROOT,project,data_dir=Path(temporary)/"settings");server=LumenServer(0,app)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as playwright:
                opts={'headless':True,'args':['--no-sandbox','--disable-dev-shm-usage']}
                if args.chromium:opts['executable_path']=args.chromium
                browser=playwright.chromium.launch(**opts)
                context=browser.new_context(viewport={'width':1648,'height':928},device_scale_factor=1)
                page=context.new_page();page.set_default_timeout(7000)
                page.on('pageerror',lambda e:errors.append(str(e)))
                if args.transport=='bridge':prepare(page,base)
                else:page.goto(base)
                page.wait_for_function('window.lumen?.platformReady',timeout=20000)
                expect(page.locator('.window-controls,.traffic,[data-icon="more"]')).to_have_count(0)
                expect(page.locator('#native-window-actions')).not_to_be_visible()
                passed('No traffic-light buttons, overflow ellipses or fake browser window controls')
                for key,name in [('1','day'),('2','dark'),('3','forest')]:
                    page.keyboard.press('Control+Alt+'+key);page.wait_for_timeout(350)
                    page.mouse.move(2,2)
                    page.screenshot(path=str(args.output/(name+'.png')))
                    assert page.evaluate('document.documentElement.scrollWidth===innerWidth')
                passed('Day, dark and forest preserve the reference arrangement without viewport overflow')
                assert page.evaluate('document.querySelector(".global-search").getBoundingClientRect().right < document.querySelector(".top-actions").getBoundingClientRect().left')
                passed('Top search and action groups do not overlap at reference resolution')
                page.locator('#ai-input').fill('BORRADOR_PRESERVADO_02')
                page.locator('#terminal-input').fill('help');page.locator('#terminal-input').press('Enter')
                expect(page.locator('#terminal-log')).to_contain_text('local command console')
                log_before=page.locator('#terminal-log').text_content()
                page.locator('#layout-trigger').click()
                expect(page.locator('#modal-title')).to_contain_text('Cada panel')
                page.locator('[data-layout-preset="grouped"]').click()
                page.locator('#modal [data-action="close-modal"]').last.click()
                page.wait_for_timeout(300)
                expect(page.locator('.dock-slot[data-dock-side="right"] .dock-tab')).to_have_count(2)
                expect(page.locator('.dock-slot[data-dock-side="bottom"]')).not_to_be_visible()
                expect(page.locator('#assistant-panel')).to_be_visible()
                expect(page.locator('#ai-input')).to_have_value('BORRADOR_PRESERVADO_02')
                passed('Grouped preset combines Assistant and Console into real right-side tabs')
                page.locator('.dock-slot[data-dock-side="right"] .dock-group-actions [data-action="ai-settings"]').click()
                expect(page.locator('#settings-content .provider-grid')).to_be_visible()
                page.keyboard.press('Escape')
                expect(page.locator('#ai-input')).to_have_value('BORRADOR_PRESERVADO_02')
                passed('Grouped assistant retains its working model-connection control')
                page.locator('[data-dock-tab="console"]').click()
                expect(page.locator('#terminal-panel')).to_be_visible()
                assert page.locator('#terminal-log').text_content()==log_before
                expect(page.locator('#assistant-panel')).not_to_be_visible()
                passed('Dock tab switch preserves console output and assistant draft without cloning panes')
                page.locator('[data-dock-tab="console"]').focus();page.keyboard.press('ArrowLeft')
                expect(page.locator('[data-dock-tab="assistant"]')).to_be_focused()
                expect(page.locator('#assistant-panel')).to_be_visible()
                passed('Grouped tabs have roving focus and arrow-key activation')
                page.mouse.move(2,2);page.wait_for_timeout(300);page.screenshot(path=str(args.output/'grouped.png'))
                page.locator('#layout-trigger').click()
                page.locator('#place-assistant').select_option('bottom')
                page.locator('#place-console').select_option('bottom')
                page.locator('#modal [data-action="close-modal"]').last.click();page.wait_for_timeout(300)
                expect(page.locator('.dock-slot[data-dock-side="bottom"] .dock-tab')).to_have_count(2)
                expect(page.locator('.dock-slot[data-dock-side="right"]')).not_to_be_visible()
                passed('Placement selectors move and group panes, with no mouse-drag requirement')
                # Move a grouped tab back to the right with actual pointer events.
                tab=page.locator('[data-dock-tab="assistant"]');r=tab.bounding_box()
                page.mouse.move(r['x']+r['width']/2,r['y']+r['height']/2);page.mouse.down()
                page.mouse.move(r['x']+r['width']/2+14,r['y']-10,steps=3)
                expect(page.locator('.dock-targets')).to_be_visible()
                target=page.locator('[data-drop-side="right"]').bounding_box()
                page.mouse.move(target['x']+target['width']/2,target['y']+target['height']/2,steps=15)
                expect(page.locator('[data-drop-side="right"]')).to_have_class('dock-target dock-target-right target-active')
                page.screenshot(path=str(args.output/'docking-guides.png'))
                page.mouse.up();page.wait_for_timeout(300)
                assert page.evaluate('lumen.layout.groups.right.includes("assistant")')
                expect(page.locator('.dock-targets')).not_to_be_visible()
                expect(page.locator('#ai-input')).to_have_value('BORRADOR_PRESERVADO_02')
                passed('Pointer drag separates a grouped pane; live docking guides disappear on release')
                # Drag header, then cancel. The DOM and state must remain unchanged.
                before=page.evaluate('JSON.stringify(lumen.layout)')
                r=page.locator('.assistant-heading h2').bounding_box()
                page.mouse.move(r['x']+20,r['y']+8);page.mouse.down();page.mouse.move(r['x']-70,r['y']+90,steps=5)
                expect(page.locator('.dock-targets')).to_be_visible();page.keyboard.press('Escape');page.mouse.up()
                expect(page.locator('.dock-targets')).not_to_be_visible()
                assert page.evaluate('JSON.stringify(lumen.layout)')==before
                passed('Escape cancels an in-progress panel drag without changing the layout')
                page.keyboard.press('Control+Alt+f');page.wait_for_timeout(300)
                expect(page.locator('#project-panel')).not_to_be_visible();expect(page.locator('#assistant-panel')).not_to_be_visible();expect(page.locator('#terminal-panel')).not_to_be_visible()
                page.wait_for_function('document.querySelector("#editor-panel").getBoundingClientRect().width>1450')
                page.screenshot(path=str(args.output/'focus.png'))
                page.keyboard.press('Control+Alt+f');page.wait_for_timeout(300)
                assert page.evaluate('JSON.stringify(lumen.layout)')==before
                passed('Focus shortcut expands the editor and restores the exact previous grouping')
                handle=page.locator('#tree-resizer');handle.focus();width=page.locator('.dock-slot[data-dock-side="left"]').bounding_box()['width']
                page.keyboard.press('ArrowRight');page.keyboard.press('Shift+ArrowRight')
                new_width=page.locator('.dock-slot[data-dock-side="left"]').bounding_box()['width']
                assert new_width>=width+39
                assert handle.get_attribute('aria-valuenow')==str(round(new_width))
                passed('Keyboard resizing supports 10/30 px steps and updates separator ARIA values')
                # File tab navigation / keyboard reorder retains model values.
                first=page.locator('.file-tab').first;path=first.get_attribute('data-tab');first.focus()
                page.keyboard.press('Alt+Shift+ArrowRight')
                assert page.locator('.file-tab').nth(1).get_attribute('data-tab')==path
                page.keyboard.press('ArrowRight')
                assert page.evaluate('lumen.activeFile').endswith('Camera.cs')
                passed('File tabs reorder by keyboard and remain navigable with arrow keys')
                # Actual tab drag. Drop before the first file tab.
                source=page.locator('.file-tab').last;target=page.locator('.file-tab').first
                source_path=source.get_attribute('data-tab')
                source.drag_to(target,target_position={'x':3,'y':18})
                assert page.locator('.file-tab').first.get_attribute('data-tab')==source_path
                passed('File tab drag-and-drop reorders the real open-document collection')
                page.keyboard.press('Control+,');page.locator('[data-setting-category="appearance"]').click()
                page.locator('#pref-appearance-density').select_option('compact')
                assert page.evaluate('document.documentElement.dataset.density')=='compact'
                page.locator('#pref-appearance-motion').uncheck()
                assert page.evaluate('lumen.motionEnabled') is False
                page.keyboard.press('Escape');page.keyboard.press('Control+Alt+f');page.keyboard.press('Control+Alt+f')
                assert page.evaluate('document.getAnimations().filter(a=>a.playState==="running").length')==0
                passed('Interface density persists, and user-disabled motion creates no running animations')
                page.keyboard.press('Control+,');page.locator('[data-setting-category="appearance"]').click();page.locator('#pref-appearance-motion').check();page.locator('#pref-appearance-density').select_option('comfortable');page.keyboard.press('Escape')
                page.emulate_media(reduced_motion='reduce');page.wait_for_timeout(50)
                assert page.evaluate('lumen.motionEnabled') is False
                page.keyboard.press('Control+Alt+1');page.keyboard.press('Control+Alt+f');page.keyboard.press('Control+Alt+f')
                assert page.evaluate('document.getAnimations().filter(a=>a.playState==="running").length')==0
                passed('System reduced-motion preference overrides application motion in real time')
                page.emulate_media(reduced_motion='no-preference')
                # Rapid changes should never duplicate IDs or retain animation loops.
                for _ in range(10):page.keyboard.press('Control+Alt+f')
                page.wait_for_timeout(400)
                assert page.evaluate('document.getAnimations().filter(a=>a.playState==="running").length')==0
                assert page.evaluate('(()=>{const ids=[...document.querySelectorAll("[id]")].map(el=>el.id);return new Set(ids).size===ids.length})()')
                passed('Rapid layout changes settle without running animations or duplicated DOM IDs')
                # Snapshot the layout through the real browser API, then use a fresh document.
                saved=page.evaluate('({layout:localStorage.getItem("lumen.layout.v3"),theme:localStorage.getItem("lumen.theme"),settings:localStorage.getItem("lumen.settings")})')
                state=page.evaluate('lumen.layout')
                restored=context.new_page();restored.on('pageerror',lambda e:errors.append(str(e)))
                if args.transport=='bridge':prepare(restored,base,{'lumen.layout.v3':saved['layout'],'lumen.theme':saved['theme'],'lumen.settings':saved['settings']})
                else:restored.goto(base)
                restored.wait_for_function('window.lumen?.platformReady',timeout=20000)
                assert restored.evaluate('lumen.layout')==state
                passed('Layout and sizes round-trip to a fresh document (injected storage in bridge mode)')
                restored.keyboard.press('Control+Alt+f')
                focus_data=restored.evaluate('localStorage.getItem("lumen.layout.v3")')
                if args.transport=='bridge':
                    restored.close();restored=context.new_page();prepare(restored,base,{'lumen.layout.v3':focus_data})
                else:restored.reload()
                restored.wait_for_function('window.lumen?.platformReady',timeout=20000)
                assert restored.evaluate('lumen.layout.preset')=='focus'
                restored.keyboard.press('Control+Alt+f');restored.wait_for_timeout(300)
                expect(restored.locator('#project-panel')).to_be_visible()
                assert restored.evaluate('lumen.layout.preset')=='studio'
                passed('Saved focus layout exits safely after fresh document initialization')
                restored.close()
                page.keyboard.press('Control+Alt+l');page.locator('#layout-reset-all').click();page.locator('#modal [data-action="close-modal"]').last.click()
                page.wait_for_timeout(300)
                assert page.evaluate('lumen.layout.preset')=='studio'
                passed('One-click reset recovers the original Lumen arrangement')
                for width,height in [(1920,1080),(1366,768),(1100,768),(1024,768)]:
                    page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(300)
                    assert page.evaluate('document.documentElement.scrollWidth===innerWidth')
                    r=page.locator('#editor-panel').bounding_box();assert r['width']>240
                    assert page.evaluate('document.querySelector(".global-search").getBoundingClientRect().right < document.querySelector(".top-actions").getBoundingClientRect().left')
                    page.screenshot(path=str(args.output/f'responsive-{width}.png'))
                passed('1920, 1366, 1100 and 1024 px layouts: no page overflow or header collisions')
                page.locator('.rail-item[data-action="toggle-ai"]').click();page.wait_for_timeout(300)
                expect(page.locator('.dock-slot.is-overlay')).to_be_visible()
                expect(page.locator('#assistant-panel')).to_be_visible();page.keyboard.press('Escape')
                expect(page.locator('.dock-slot.is-overlay')).not_to_be_visible()
                passed('Small desktop widths use an assistant drawer that closes with Escape')
                page.set_viewport_size({'width':1648,'height':928});page.wait_for_timeout(300)
                assert errors==[],errors
                passed('Zero unhandled JavaScript errors across the refinement suite')
                result={'transport':args.transport,'checks':len(checks),'passed':checks,'errors':errors,
                  'limitations':['Built-in editor tested; Monaco not executed','CSS pearl shown; Babylon engine not loaded','Native desktop host not executed','Bridge does not verify HTTP module loading or native localStorage durability']}
                (args.output/'results.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
                context.close();browser.close()
                print(json.dumps({'checks':len(checks),'errors':errors,'transport':args.transport}),flush=True)
        except Exception:
            try:
                print('FAILURE_LAYOUT',page.evaluate('({layout:lumen.layout,box:document.querySelector("#editor-panel").getBoundingClientRect().toJSON(),grid:getComputedStyle(document.querySelector(".workspace")).gridTemplateColumns})'),flush=True)
                page.screenshot(path=str(args.output/'failure.png'))
            except Exception:pass
            raise
        finally:
            app.features.shutdown();app.runner.shutdown();server.shutdown();server.server_close()

if __name__=='__main__':main()
