#!/usr/bin/env python3
"""UI + real backend, with an EXPLICITLY MOCKED OpenAI SSE connection.
No external provider is called. Not an inference-quality/authentication test.
"""
from __future__ import annotations
import argparse, json, shutil, sys, tempfile, threading, time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.server import Application,LumenServer
from ui_harness import prepare

class MockSSE:
    def __init__(self, slow=False):self.closed=False;self.slow=slow
    def __enter__(self):return self
    def __exit__(self,*_):self.close()
    def close(self):self.closed=True
    def __iter__(self):
        chunks=['Contrato de prueba, no inferencia real.\n', '```csharp\n', '// Propuesta controlada\n', 'int value = 7;\n', '```']
        if self.slow:chunks=['Fragmento de prueba. ']*100
        for chunk in chunks:
            time.sleep(.15)
            if self.closed:return
            yield ('data: '+json.dumps({'type':'response.output_text.delta','delta':chunk})+'\n').encode()
        yield b'data: [DONE]\n'

def main():
    p=argparse.ArgumentParser();p.add_argument('--transport',choices=['direct','bridge'],default='direct');p.add_argument('--chromium');p.add_argument('--output',type=Path,default=ROOT/'reports/ai-contract');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    from playwright.sync_api import sync_playwright,expect
    checks=[];errors=[];requests=[]
    def passed(s):checks.append(s);print('PASS',s,flush=True)
    with tempfile.TemporaryDirectory(prefix='lumen-ai-contract-') as td:
        td=Path(td);ws=td/'project';shutil.copytree(ROOT/'workspace/MyProject',ws,ignore=shutil.ignore_patterns('.lumen'));app=Application(ROOT,ws,data_dir=td/'data')
        app.features.prefs.update({'security.cloudAI':True,'ai.provider':'openai','ai.model':'qa-contract-mock','ai.context':'file'})
        app.features.ai.vault.set('openai','TEST_ONLY_NOT_A_REAL_CREDENTIAL')
        server=LumenServer(0,app);threading.Thread(target=server.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{server.server_port}'
        slow=[False]
        def connection(provider,payload=None,path='',timeout=25):
            requests.append({'provider':provider,'payload':payload,'path':path});return MockSSE(slow[0])
        try:
            with patch.object(app.features.ai,'_connection',side_effect=connection),sync_playwright() as pw:
                opts={'headless':True,'args':['--no-sandbox','--disable-dev-shm-usage']}
                if a.chromium:opts['executable_path']=a.chromium
                b=pw.chromium.launch(**opts);pg=b.new_page(viewport={'width':1648,'height':928});pg.set_default_timeout(7000);pg.on('pageerror',lambda e:errors.append(str(e)))
                try:
                    if a.transport=='bridge':prepare(pg,base)
                    else:pg.goto(base)
                    pg.wait_for_function('window.lumen?.platformReady');editor=pg.locator('.code-input');original=editor.input_value();path=pg.evaluate('lumen.activeFile');disk=(ws/path).read_text()
                    pg.locator('#ai-input').fill('Revisa este archivo de prueba.');pg.locator('.send-button').click();expect(pg.locator('#confirm-yes')).to_be_visible();pg.locator('#modal [data-action="close-modal"]').last.click();pg.wait_for_timeout(200);assert not requests
                    passed('Cancel consent: no provider request and no buffer change')
                    pg.locator('.send-button').click();pg.locator('#confirm-yes').click();expect(pg.locator('.ai-stream')).to_contain_text('Contrato');expect(pg.locator('.review-code-button')).to_be_visible();assert editor.input_value()==original;assert (ws/path).read_text()==disk
                    assert requests[0]['provider']=='openai';assert requests[0]['path']=='/v1/responses';assert any(isinstance(message.get('content'),str) and original in message['content'] for message in requests[0]['payload']['input'])
                    passed('Explicitly mocked SSE traverses actual router and UI; proposal never applies automatically')
                    pg.locator('.review-code-button').click();expect(pg.locator('.code-review-grid')).to_be_visible();pg.locator('#review-replace').click();expect(editor).to_have_value('// Propuesta controlada\nint value = 7;\n');assert (ws/path).read_text()==disk
                    editor.focus();pg.keyboard.press('Control+z');expect(editor).to_have_value(original)
                    passed('Review replaces only buffer, disk stays unchanged and editor undo restores original')
                    editor.fill(original+'\n// local edit');pg.locator('.review-code-button').click();expect(pg.locator('#toasts')).to_contain_text('cambió');assert not pg.locator('.code-review-grid').is_visible();assert (ws/path).read_text()==disk
                    passed('Stale AI proposal is rejected after user edits the buffer')
                    editor.fill(original);slow[0]=True;pg.locator('#ai-input').fill('Petición lenta de prueba.');pg.locator('.send-button').click();pg.locator('#confirm-yes').click();expect(pg.locator('#ai-cancel-generation')).to_be_visible();pg.locator('#ai-cancel-generation').click();expect(pg.locator('.send-button')).to_be_enabled();expect(pg.locator('#chat-messages')).to_contain_text('cancelada');assert any(j.cancelled.is_set() for j in app.features.ai.jobs.values())
                    passed('Cancellation reaches mock transport and restores input without modifying a file')
                    pg.locator('[data-action="new-chat"]').last.click();pg.wait_for_timeout(250);assert app.features.ai.history=={};assert (ws/path).read_text()==disk;assert errors==[],errors
                    passed('New conversation clears backend history; no unhandled JavaScript errors')
                    (a.output/'AI_UI_CONTRACT_RESULTS.json').write_text(json.dumps({'checks':len(checks),'passed':checks,'errors':errors,'transport':a.transport,'providerConnection':'EXPLICIT MOCK; no network calls, live inference or paid account','scope':'Actual UI, router, buffer review, conflict check, undo and cancellation'},ensure_ascii=False,indent=2))
                except Exception:pg.screenshot(path=str(a.output/'FAILURE.png'));raise
                finally:b.close()
        finally:app.features.shutdown();app.runner.shutdown();server.shutdown();server.server_close()
if __name__=='__main__':main()
