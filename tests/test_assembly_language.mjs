import test from 'node:test';
import assert from 'node:assert/strict';
import {assemblyCompletions} from '../web/src/assembly-language.js';
import {textMateTheme,TextMateState} from '../web/src/textmate.js';
test('CPU suggestions exclude registers from other architectures',()=>{
  for(const [architecture,present,absent] of [['x86','eax','rax'],['x86_64','rax','x0'],['arm','r0','rax'],['arm64','x0','r0'],['riscv64','a0','rax']]){
    const list=assemblyCompletions(architecture),labels=list.map(x=>x.label);assert.ok(labels.includes(present));assert.ok(!labels.includes(absent));assert.ok(list.some(x=>x.kind==='instruction'));assert.ok(list.some(x=>x.kind==='directive'));
  }
});
test('Current buffer labels and 32 bit operands are usable suggestions',()=>{
  const list=assemblyCompletions('x86','loop_here:\n jmp loop_here\n');assert.equal(list.filter(x=>x.label==='loop_here').length,1);assert.match(list.find(x=>x.label==='mov').insertText,/eax/);assert.doesNotMatch(list.find(x=>x.label==='mov').insertText,/rax/);
});
test('TextMate theme preserves parent selectors and explicit empty font styles',()=>{
  const theme=textMateTheme({text:'#202020',editor:'#ffffff',comment:'#334433'},[{scope:'source.python comment',settings:{foreground:'#abcdef',fontStyle:''}}]);assert.deepEqual(theme.settings.at(-1),{scope:'source.python comment',settings:{foreground:'#abcdef',fontStyle:''}});
});
test('TextMate state equality invalidates states when the theme changes',()=>{
  const stack={equals:other=>other===stack},a=new TextMateState(stack,1);assert.equal(a.clone(),a);assert.ok(a.equals(new TextMateState(stack,1)));assert.ok(!a.equals(new TextMateState(stack,2)));
});
