import test from 'node:test';
import assert from 'node:assert/strict';
import {requestsLiveEdit} from '../web/src/ai-intent.js';
import {themePalette,applyShellTheme} from '../web/src/extension-theme.js';
import {createRequire} from 'node:module';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
const require=createRequire(import.meta.url),createAPI=require('../backend/extension_api.cjs');
test('Only explicit writing requests propose live editing',()=>{
  for(const text of ['Escribe el código en vivo','Por favor modifica este archivo','Puedes crear código de cero','Reescribe el archivo abierto','Analiza y modifica el código en tiempo real'])assert.equal(requestsLiveEdit(text),true,text);
  for(const text of ['Explica el código','Analiza por qué falla','Depura este archivo','¿Qué cambiarías?','No escribas código','Explícame cómo modificar el archivo','Explica: "reescribe el archivo"','```\nEscribe el código en vivo\n```','Revisa y no modifiques el código'])assert.equal(requestsLiveEdit(text),false,text);
});
test('External theme maps the shell and terminal, rejects CSS payloads and clears cleanly',()=>{
  const theme={id:'qa:ocean',uiTheme:'vs-dark',data:{colors:{'editor.background':'#102030','editor.foreground':'#f0f1f2','terminal.foreground':'#abcdef','sideBar.background':'#182838','focusBorder':'url(https://bad.example)','input.background':'#abc'},tokenColors:[{scope:'keyword',settings:{foreground:'#eeccaa'}}]}};
  const {palette,colors}=themePalette(theme);assert.equal(palette.surface,'#182838');assert.equal(palette.field,'#aabbcc');assert.equal(palette['terminal-text'],'#abcdef');assert.equal(palette['syntax-keyword'],'#eeccaa');assert.equal(colors.focusBorder,undefined);
  const props=new Map(),root={dataset:{},style:{setProperty:(k,v)=>props.set(k,v),removeProperty:k=>props.delete(k)}};
  applyShellTheme(theme,root);assert.equal(root.dataset.theme,'dark');assert.equal(props.get('--editor'),'#102030');applyShellTheme(null,root);assert.equal(props.size,0);assert.equal(root.dataset.extensionTheme,undefined);
});
test('Will-save edits wait asynchronously and did-save fires after persistence',async()=>{
  const folder=mkdtempSync(path.join(tmpdir(),'lumen-save-event-'));
  try{
    const api=createAPI({registerCommand(){},register(){},notify(){},effect(){}},{storage:folder,workspace:folder,root:folder,manifest:{}}),v=api.vscode;
    api.syncDocument({path:'demo.py',text:'print("áéíóú ñ")\n',dirty:true});let saved=0;
    const formatter=v.workspace.onWillSaveTextDocument(e=>{assert.equal(e.reason,v.TextDocumentSaveReason.Manual);assert.equal(e.document.isDirty,true);e.waitUntil(Promise.resolve([v.TextEdit.insert(new v.Position(0,0),'# formatted\n')]));});
    v.workspace.onDidSaveTextDocument(d=>{saved++;assert.equal(d.isDirty,false);});
    const result=await api.willSave(1);assert.equal(result.edits[0].newText,'# formatted\n');assert.equal(saved,0);api.didSave();assert.equal(saved,1);
    formatter.dispose();let wait;const sub=v.workspace.onWillSaveTextDocument(e=>{wait=e.waitUntil;});await api.willSave(2);assert.throws(()=>wait(Promise.resolve([])),/durante/);sub.dispose();
  }finally{rmSync(folder,{recursive:true,force:true});}
});
