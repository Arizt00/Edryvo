import test from 'node:test';
import assert from 'node:assert/strict';
import {OrderedTerminalInput} from '../web/src/terminal-input.js';

test('rapid typing and terminal control replies retain their original order',async()=>{
  let active=0,max=0;const received=[];
  const input=new OrderedTerminalInput(async data=>{active++;max=Math.max(max,active);await new Promise(r=>setTimeout(r,data==='W'?15:1));received.push(data);active--;});
  const text='Write-Output ("lumen-" + "pty-052")\r\x1b[1;1R';
  await Promise.all([...text].map(c=>input.write(c)));assert.equal(received.join(''),text);assert.equal(max,1);
});
test('batching respects the backend limit and drops queued writes on transport failure',async()=>{
  let release;const gate=new Promise(r=>release=r),chunks=[];
  const input=new OrderedTerminalInput(async data=>{chunks.push(data);if(chunks.length===1)await gate;});
  const writes=[input.write('a'),input.write('b'.repeat(40000)),input.write('c'.repeat(40000))];release();await Promise.all(writes);
  assert.ok(chunks.every(x=>x.length<=65536));assert.equal(chunks.join(''),'a'+'b'.repeat(40000)+'c'.repeat(40000));
  const sent=[];const failing=new OrderedTerminalInput(async x=>{sent.push(x);throw Error('network');});
  const result=await Promise.allSettled([failing.write('a'),failing.write('b'),failing.write('\r')]);
  assert.deepEqual(sent,['a']);assert.ok(result.every(x=>x.status==='rejected'));
});
