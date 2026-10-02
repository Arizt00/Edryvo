#!/usr/bin/env python3
"""Capture the actual Lumen UI and optional interaction video.

The bridge transport is labelled QA-only; it is not a browser-network test.
This script only works in a temporary copy of the bundled example project.
"""
from __future__ import annotations
import argparse
import json
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.server import Application,LumenServer
from ui_harness import prepare


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--transport',choices=['direct','bridge'],default='direct')
    parser.add_argument('--chromium')
    parser.add_argument('--output',type=Path,default=ROOT/'reports/capture')
    parser.add_argument('--video',action='store_true')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    from playwright.sync_api import sync_playwright
    errors=[]
    with tempfile.TemporaryDirectory(prefix='lumen-capture-') as temporary:
        project=Path(temporary)/'MyProject'
        shutil.copytree(ROOT/'workspace/MyProject',project,ignore=shutil.ignore_patterns('.lumen'))
        app=Application(ROOT,project,data_dir=Path(temporary)/'data');server=LumenServer(0,app)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as playwright:
                options={'headless':True,'args':['--no-sandbox','--disable-dev-shm-usage']}
                if args.chromium:options['executable_path']=args.chromium
                browser=playwright.chromium.launch(**options)
                context_options={'viewport':{'width':1648,'height':928},'device_scale_factor':1}
                if args.video:
                    context_options.update(record_video_dir=str(args.output/'raw_video'),record_video_size={'width':1648,'height':928})
                context=browser.new_context(**context_options)
                page=context.new_page();start=time.monotonic()
                page.set_default_timeout(7000);page.on('pageerror',lambda e:errors.append(str(e)))
                if args.transport=='bridge':prepare(page,base)
                else:page.goto(base)
                page.wait_for_function('window.lumen?.platformReady',timeout=20000)
                page.wait_for_timeout(450)
                ready=time.monotonic()-start
                def settle(ms=800):
                    page.mouse.move(5,5);page.wait_for_timeout(ms)
                def capture(name):
                    settle(350);page.screenshot(path=str(args.output/(name+'.png')))
                def close_modal():
                    page.locator('#modal [data-action="close-modal"]').last.click();settle()
                settle(1000);capture('dia')
                page.keyboard.press('Control+Alt+2');settle(1600);capture('oscuro')
                page.keyboard.press('Control+Alt+3');settle(1600);capture('bosque')
                page.locator('[data-collapse-panel="project"]').click();settle(900);capture('izquierdo-contraido')
                page.locator('[data-dock-expand="left"]').click();settle(700)
                page.locator('[data-collapse-panel="assistant"]').click();settle(900);capture('derecho-contraido')
                page.keyboard.press('Control+b');settle(700)
                page.locator('[data-action="toggle-rail"]').click();settle(1100);capture('compacto')
                page.locator('[data-action="toggle-rail"]').click();settle(400)
                page.locator('[data-dock-expand="left"]').click();settle(500)
                page.locator('[data-dock-expand="right"]').click();settle(800)
                page.locator('#layout-trigger').click();settle(900);capture('organizar')
                page.locator('[data-layout-preset="grouped"]').click();settle(600);close_modal()
                page.locator('#editor-panel').click(position={'x':450,'y':82});settle(700);capture('agrupado')
                page.locator('[data-dock-tab="console"]').click();settle(1500)
                page.locator('[data-dock-tab="assistant"]').click();settle(700)
                tab=page.locator('[data-dock-tab="console"]');r=tab.bounding_box()
                page.mouse.move(r['x']+r['width']/2,r['y']+r['height']/2);page.mouse.down()
                page.mouse.move(r['x']+r['width']/2-20,r['y']+32,steps=10)
                page.wait_for_timeout(500)
                target=page.locator('[data-drop-side="bottom"]').bounding_box()
                page.mouse.move(target['x']+target['width']/2,target['y']+target['height']/2,steps=45)
                page.wait_for_timeout(650);page.screenshot(path=str(args.output/'acoplar.png'))
                page.mouse.up();settle(1300)
                page.keyboard.press('Control+Alt+f');settle(1600);capture('enfoque')
                page.keyboard.press('Control+Alt+f');settle(800)
                page.keyboard.press('Control+Alt+1');settle(1600)
                # Leave the UI exactly in its normal arrangement.
                page.locator('#layout-trigger').click();settle(300)
                page.locator('#layout-reset-all').click();close_modal();settle(1500)
                assert not errors,errors
                video=page.video
                context.close()
                data={'transport':args.transport,'unhandled_errors':errors,'ready_after_seconds':round(ready,3),
                      'capture':'Actual UI, built-in editor and CSS pearl; not Monaco/Babylon/pywebview execution'}
                if args.video:data['raw_video']=str(video.path())
                browser.close()
                (args.output/'capture.json').write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
                print(json.dumps(data,ensure_ascii=False),flush=True)
        finally:
            app.features.shutdown();app.runner.shutdown();server.shutdown();server.server_close()

if __name__=='__main__':main()
