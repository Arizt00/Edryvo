import test from 'node:test';
import assert from 'node:assert/strict';
import {parseCSV,numericSummary,contrast,cssColors} from '../web/src/workspace-data.js';
import {dropSide,outsideViewport} from '../web/src/document-drag.js';
import {createRequire} from 'node:module';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
const createAPI=createRequire(import.meta.url)('../backend/extension_api.cjs');
test('CSV tools preserve quoted separators, unicode and embedded newlines; summary ignores empty values',()=>{
 const table=parseCSV('\ufeffname,value\r\n"á,ñ",10\r\n"two\nlines",20\r\n"quote ""inside""",\r\n');
 assert.deepEqual(table.header,['name','value']);assert.deepEqual(table.rows,[['á,ñ','10'],['two\nlines','20'],['quote "inside"','']]);assert.deepEqual(numericSummary(table.rows,1),{count:2,min:10,max:20,mean:15});assert.throws(()=>parseCSV('"unfinished'),/cerrar/);
});
test('Design tools calculate contrast and preserve distinct CSS colors',()=>{assert.equal(contrast('#000','#fff'),21);assert.equal(contrast('#aaaaaa','#aaaaaa'),1);assert.deepEqual(cssColors('color:#ABC; background:#aabbcc; border:#ABC'),['#abc','#aabbcc']);});
test('File drops choose five destinations and outside monitors allow negative coordinates',()=>{
 const rect={left:100,top:50,width:1000,height:600};for(const [x,y,side] of [[600,60,'top'],[600,630,'bottom'],[110,350,'left'],[1050,350,'right'],[600,350,'center']])assert.equal(dropSide(x,y,rect),side);assert(outsideViewport(-200,10,1200,800));assert(outsideViewport(1300,10,1200,800));assert(!outsideViewport(500,10,1200,800));
});
test('Tree providers preserve object identity and methods when a node executes its command',async()=>{
 const folder=mkdtempSync(path.join(tmpdir(),'lumen-r8-tree-'));
 try{const commands=new Map(),api=createAPI({registerCommand(id,fn){commands.set(id,fn);return {dispose(){}};},register(){},notify(){},effect(){}},{storage:folder,workspace:folder,root:folder,manifest:{}}),v=api.vscode;
 class Node{constructor(name){this.name=name;}value(){return this.name.toUpperCase();}}const node=new Node('árbol'),changed=new v.EventEmitter();let counter=0;
 v.window.registerTreeDataProvider('qa.tree',{onDidChangeTreeData:changed.event,getChildren:parent=>parent?[]:[node],getTreeItem:n=>({label:n.name,command:{command:'qa.select',arguments:[n]}})});
 v.commands.registerCommand('qa.select',n=>{counter++;return n.value();});const tree=await api.treeViews.children('qa.tree');assert.equal(tree.items[0].label,'árbol');const args=api.treeViews.arguments(tree.items[0].command.arguments);assert.equal(await commands.get('qa.select')(...args),'ÁRBOL');assert.equal(counter,1);changed.fire();assert.equal(api.treeViews.snapshot()[0].revision,1);
 }finally{rmSync(folder,{recursive:true,force:true});}
});
test('Semantic range tokens and workspace rename edits survive serialization',()=>{
 const folder=mkdtempSync(path.join(tmpdir(),'lumen-r8-semantic-'));
 try{const api=createAPI({registerCommand(){},register(){},notify(){},effect(){}},{storage:folder,workspace:folder,root:folder,manifest:{}}),v=api.vscode,b=new v.SemanticTokensBuilder(new v.SemanticTokensLegend(['variable'],['readonly']));b.push(new v.Range(2,3,2,7),'variable',['readonly']);assert.deepEqual([...b.build().data],[2,3,4,0,1]);const edits=new v.WorkspaceEdit();edits.replace(v.Uri.file(path.join(folder,'a.py')),new v.Range(0,0,0,3),'new');assert.equal(JSON.parse(JSON.stringify(edits)).changes[0].edits[0].newText,'new');
 }finally{rmSync(folder,{recursive:true,force:true});}
});
