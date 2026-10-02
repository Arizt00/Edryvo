#!/usr/bin/env python3
"""Lumen 0.3 collapse, vectors and UI regression on a disposable workspace.

Bridge mode uses inlined owned UI and a real loopback backend. Browser network,
CSP, optional vendors and storage durability are NOT tested in this mode.
"""
from __future__ import annotations
import argparse,json,shutil,sys,tempfile,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.server import Application,LumenServer
from ui_harness import prepare

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--transport',choices=['direct','bridge'],default='direct')
    parser.add_argument('--chromium')
    parser.add_argument('--output',type=Path,default=ROOT/'reports/ui03')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    from playwright.sync_api import sync_playwright,expect
    checks=[];errors=[]
    def passed(text):checks.append(text);print('PASS',text,flush=True)
    with tempfile.TemporaryDirectory(prefix='lumen-ui03-') as temp:
        workspace=Path(temp)/'MyProject';shutil.copytree(ROOT/'workspace/MyProject',workspace,ignore=shutil.ignore_patterns('.lumen'))
        (workspace/'ScrollQA').mkdir()
        for i in range(50):(workspace/'ScrollQA'/f'file_{i:02}.txt').write_text('Disposable test document\n')
        app=Application(ROOT,workspace,data_dir=Path(temp)/"settings");server=LumenServer(0,app)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as p:
                opts={'headless':True,'args':['--no-sandbox','--disable-dev-shm-usage']}
                if args.chromium:opts['executable_path']=args.chromium
                browser=p.chromium.launch(**opts);context=browser.new_context(viewport={'width':1648,'height':928},device_scale_factor=1)
                page=context.new_page();page.set_default_timeout(6000);page.on('pageerror',lambda e:errors.append(str(e)))
                def load(target,storage=None):
                    if args.transport=='bridge':prepare(target,base,storage)
                    else:
                        if storage:target.add_init_script('Object.entries('+json.dumps(storage)+').forEach(([k,v])=>localStorage.setItem(k,v));')
                        target.goto(base)
                    target.wait_for_function('window.lumen?.platformReady',timeout=20000)
                def settle():page.mouse.move(3,3);page.wait_for_timeout(350)
                def capture(name):settle();page.screenshot(path=str(args.output/(name+'.png')))
                def reset():
                    page.locator('#layout-trigger').click();page.locator('#layout-reset-all').click();page.keyboard.press('Escape');settle()
                load(page);settle()
                assert page.evaluate('lumen.layout.version')==3
                passed('v3 boots with original pane positions and all existing document tabs')
                assert page.locator('svg.icon[data-glyph]').count()>90
                assert page.evaluate('Array.from(document.querySelectorAll("svg.icon")).every(s=>s.getAttribute("viewBox")==="0 0 24 24" && s.getAttribute("aria-hidden")==="true")')
                passed('UI renders the local SVG family on a consistent 24-unit grid')
                assert page.locator('.traffic,[data-icon="more"],.window-controls').count()==0
                assert page.evaluate('Array.from(document.querySelectorAll("[aria-controls]")).every(e=>document.getElementById(e.getAttribute("aria-controls")))')
                passed('No ornamental window controls or ellipsis menus; all ARIA controls resolve')
                # Capture references before adding state used for preservation checks.
                for key,name in [('1','dia'),('2','oscuro'),('3','bosque')]:
                    page.keyboard.press('Control+Alt+'+key);capture(name)
                passed('All three themes render with the new icons and surface hierarchy')
                page.locator('#ai-input').fill('DRAFT_LUMEN_03')
                page.locator('.code-input').evaluate('e=>e.setSelectionRange(12,23)')
                page.evaluate('window.__nodes={ai:document.getElementById("ai-input"),code:document.querySelector(".code-input"),project:document.getElementById("project-panel")};')
                baseline=page.locator('#editor-panel').bounding_box()['width']
                page.locator('[data-dir="ScrollQA"]').click()
                page.locator('#sidebar-content').evaluate('e=>e.scrollTop=250')
                scroll=page.locator('#sidebar-content').evaluate('e=>e.scrollTop')
                assert scroll>100
                page.locator('[data-collapse-panel="project"]').click();settle()
                expect(page.locator('#project-panel')).not_to_be_visible()
                assert 42<=page.locator('#dock-left').bounding_box()['width']<=45
                assert page.locator('#editor-panel').bounding_box()['width']>baseline+240
                expect(page.locator('[data-toggle-side="left"]')).to_have_attribute('aria-expanded','false')
                assert page.locator('#dock-content-left').evaluate('e=>e.inert')
                passed('Left header contracts to 44 px, releases editor width and marks content inert')
                capture('izquierdo-contraido')
                page.locator('[data-dock-restore="project"]').click();settle()
                assert page.locator('#sidebar-content').evaluate('e=>e.scrollTop')==scroll
                assert page.evaluate('document.getElementById("project-panel")===window.__nodes.project')
                expect(page.locator('#ai-input')).to_have_value('DRAFT_LUMEN_03')
                passed('Expand preserves live DOM, explorer scroll and assistant draft')
                page.locator('#ai-input').focus();page.locator('#ai-input').evaluate('e=>e.setSelectionRange(3,8)')
                page.keyboard.press('Control+Alt+b');settle()
                expect(page.locator('#assistant-panel')).not_to_be_visible()
                expect(page.locator('[data-dock-expand="right"]')).to_be_focused()
                assert page.locator('#dock-content-right').evaluate('e=>e.inert')
                assert page.locator('#editor-panel').bounding_box()['width']>baseline+360
                passed('Right shortcut contracts assistant without discarding its focused textarea')
                capture('derecho-contraido')
                page.locator('[data-dock-expand="right"]').press('Enter');settle()
                expect(page.locator('#ai-input')).to_be_focused()
                assert page.locator('#ai-input').evaluate('e=>[e.selectionStart,e.selectionEnd]')==[3,8]
                assert page.evaluate('document.getElementById("ai-input")===window.__nodes.ai')
                passed('Keyboard expansion restores the actual textarea, focus and selection')
                page.locator('#tree-resizer').focus()
                for _ in range(3):page.keyboard.press('Shift+ArrowRight')
                width=page.locator('#dock-left').bounding_box()['width'];state=page.evaluate('lumen.layout.sizes.left')
                page.keyboard.press('Control+b');settle();page.keyboard.press('Control+b');settle()
                assert abs(page.locator('#dock-left').bounding_box()['width']-width)<1
                assert page.evaluate('lumen.layout.sizes.left')==state
                passed('A resized dock restores its exact requested width after contraction')
                # Grouped content: collapse the dock, not individual panes.
                page.locator('#layout-trigger').click();page.locator('[data-layout-preset="grouped"]').click();page.keyboard.press('Escape');settle()
                log=page.locator('#terminal-log').text_content()
                page.locator('[data-dock-collapse="right"]').click();settle()
                assert page.locator('#dock-right .collapsed-tool').count()==2
                assert page.evaluate('lumen.layout.groups.right')==['assistant','console']
                passed('Grouped dock contracts to both tool icons while retaining tab membership')
                page.locator('[data-dock-restore="console"]').click();settle()
                expect(page.locator('#terminal-panel')).to_be_visible()
                assert page.evaluate('lumen.layout.active.right')=='console'
                assert page.locator('#terminal-log').text_content()==log
                passed('A collapsed group can reopen directly on Console with unchanged output')
                page.locator('[data-dock-tab="assistant"]').click();settle()
                expect(page.locator('#ai-input')).to_have_value('DRAFT_LUMEN_03')
                passed('Assistant draft survives grouping, contraction and sibling tab restoration')
                page.keyboard.press('Control+b');page.keyboard.press('Control+Alt+b');settle()
                previous=page.evaluate('lumen.layout')
                page.keyboard.press('Control+Alt+f');settle();page.keyboard.press('Control+Alt+f');settle()
                assert page.evaluate('lumen.layout')==previous
                passed('Focus mode restores prior contracted groups instead of reopening everything')
                page.locator('[data-action="toggle-rail"]').click();settle()
                assert page.evaluate('lumen.layout.railCompact') is True
                assert page.locator('.activity-rail').bounding_box()['width']==48
                expect(page.locator('.inspiration-card')).not_to_be_visible()
                expect(page.locator('[data-action="toggle-rail"]')).to_have_attribute('aria-expanded','false')
                assert page.locator('.rail-item').count()==6
                passed('Compact activity rail keeps six working tools in 48 px, without labels')
                capture('compacto')
                page.locator('.rail-item[data-view="explorer"]').click();settle()
                expect(page.locator('#project-panel')).to_be_visible()
                passed('Activity icons recover contracted panels without relying on hover')
                page.locator('#layout-trigger').click();page.locator('#place-console').select_option('right');page.keyboard.press('Escape');settle()
                assert 'right' not in page.evaluate('lumen.layout.collapsed')
                passed('Moving a pane into a collapsed destination expands that destination')
                # Rapid interruptible motion with stable objects / widths.
                for i in range(21):page.keyboard.press('Control+Alt+b')
                settle()
                assert page.evaluate('document.getAnimations().filter(a=>a.playState==="running").length')==0
                assert page.evaluate('document.querySelector(".workspace").classList.contains("layout-animating")') is False
                assert page.evaluate('document.getElementById("ai-input")===window.__nodes.ai')
                passed('21 rapid toggles settle without pending animations or replacement textarea nodes')
                before=page.evaluate('lumen.layout')
                storage=page.evaluate('({"lumen.layout.v3":localStorage.getItem("lumen.layout.v3")})')
                restored=context.new_page();restored.on('pageerror',lambda e:errors.append(str(e)));load(restored,storage)
                assert restored.evaluate('lumen.layout')==before;restored.close()
                passed('v3 serializes collapsed sides, navigation mode and grouping to a fresh document')
                migrated=context.new_page();migrated.on('pageerror',lambda e:errors.append(str(e)))
                old={'version':2,'preset':'custom','groups':{'left':['project'],'right':['assistant','console'],'bottom':[]},'active':{'left':'project','right':'console','bottom':None},'hidden':[],'sizes':{'left':370,'right':403}}
                load(migrated,{'lumen.layout.v3':'','lumen.layout.v2':json.dumps(old)})
                assert migrated.evaluate('lumen.layout.version')==3
                assert migrated.evaluate('lumen.layout.sizes.right')==403
                assert migrated.evaluate('lumen.layout.active.right')=='console'
                assert migrated.evaluate('lumen.layout.collapsed')==[]
                migrated.close()
                passed('Stored v2 layouts migrate without losing sizes, grouping or active tools')
                page.emulate_media(reduced_motion='reduce')
                for _ in range(6):page.keyboard.press('Control+Alt+b')
                assert page.evaluate('lumen.motionEnabled') is False
                assert page.evaluate('document.getAnimations().filter(a=>a.playState==="running").length')==0
                passed('Reduced-motion setting eliminates side-dock animation immediately')
                page.emulate_media(reduced_motion='no-preference');reset()
                if page.evaluate('lumen.layout.railCompact'):page.keyboard.press('Control+Alt+n');settle()
                for w,h in [(3840,2160),(1920,1080),(1366,768),(1100,768),(900,700),(768,700)]:
                    page.set_viewport_size({'width':w,'height':h});settle()
                    assert page.evaluate('document.documentElement.scrollWidth===innerWidth'),w
                    assert page.locator('#editor-panel').bounding_box()['width']>=200,w
                    assert page.evaluate('document.querySelector(".global-search").getBoundingClientRect().right<=document.querySelector(".top-actions").getBoundingClientRect().left'),w
                    if w in [1366,768]:page.screenshot(path=str(args.output/f'ancho-{w}.png'))
                passed('768 to 3840 px viewports have usable editor width and no header overlap')
                page.locator('[data-toggle-side="right"]').click();settle()
                expect(page.locator('.dock-slot.is-overlay')).to_be_visible()
                page.keyboard.press('Escape');settle()
                expect(page.locator('.dock-slot.is-overlay')).not_to_be_visible()
                passed('Small-screen right control opens a drawer that Escape dismisses')
                page.set_viewport_size({'width':1648,'height':928});settle()
                assert page.evaluate('(()=>{const ids=[...document.querySelectorAll("[id]")].map(e=>e.id);return new Set(ids).size===ids.length})()')
                assert not errors,errors
                passed('No duplicate DOM ids or unhandled JavaScript errors in the new suite')
                result={'transport':args.transport,'checks':len(checks),'passed':checks,'errors':errors,'limits':['Owned UI + real backend via bridge','Built-in editor and CSS pearl only','No native desktop / real durable localStorage claim']}
                (args.output/'results.json').write_text(json.dumps(result,indent=2,ensure_ascii=False))
                context.close();browser.close();print(json.dumps({'checks':len(checks),'errors':errors}),flush=True)
        finally:app.features.shutdown();app.runner.shutdown();server.shutdown();server.server_close()
if __name__=='__main__':main()
