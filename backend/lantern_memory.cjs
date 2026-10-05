// Explicit JSON state survives process replacement. Native programs use the same file contract.
const fs = require('node:fs');
const destination = process.env.LUMEN_LANTERN_STATE;
let state = {};
try { if(fs.statSync(destination).size<=1000000)state = JSON.parse(fs.readFileSync(destination, 'utf8')); } catch {}
if(!state||Array.isArray(state)||typeof state!=='object')state={};
globalThis.lanternState = state;
let previous = '';
globalThis.lanternCheckpoint = (force=false) => {
  try {
    const text = JSON.stringify(globalThis.lanternState);
    if (Buffer.byteLength(text) > 1000000 || text === previous) return;
    fs.writeFileSync(destination + '.tmp', text);
    for(let attempt=0;attempt<(force?8:1);attempt++){
      try{fs.renameSync(destination+'.tmp',destination);break;}
      catch(error){if(!force||!['EPERM','EACCES','EBUSY'].includes(error.code)||attempt===7)throw error;Atomics.wait(new Int32Array(new SharedArrayBuffer(4)),0,0,8);}
    }
    previous = text;
  } catch (error) { process.stderr.write('Lantern checkpoint: ' + error.message + '\n'); }
};
setInterval(()=>{globalThis.lanternCheckpoint();if(fs.existsSync(destination+'.reload'))process.exit(0);}, 50).unref();
process.on('exit', ()=>globalThis.lanternCheckpoint(true));

// Explicit values use the same revision-tagged Lens protocol as other adapters.
const lensPath = process.env.LUMEN_LANTERN_LENS;
const lensValues = new Map();
const util = require('node:util');
let lensLast = 0;
const flushLens = (force=false) => {
  if (!lensPath || (!force && Date.now()-lensLast<80)) return;
  lensLast=Date.now();
  try {
    fs.writeFileSync(lensPath+'.tmp',JSON.stringify({generation:process.env.LUMEN_LANTERN_GENERATION,values:[...lensValues.values()]}));
    for(let attempt=0;attempt<(force?8:1);attempt++){
      try{fs.renameSync(lensPath+'.tmp',lensPath);break;}
      catch(error){if(!force||!['EPERM','EACCES','EBUSY'].includes(error.code)||attempt===7)break;Atomics.wait(new Int32Array(new SharedArrayBuffer(4)),0,0,8);}
    }
  } catch {}
};
globalThis.lanternLens = (value,line,label='resultado') => {
  if (!Number.isInteger(line) || line<1) return value;
  const text=util.inspect(value,{depth:2,maxArrayLength:8,maxStringLength:160,customInspect:false,getters:false,breakLength:Infinity});
  lensValues.set(line,{line,label:String(label).slice(0,80),value:text.slice(0,500)});
  if(lensValues.size>200)lensValues.delete(lensValues.keys().next().value);
  flushLens();return value;
};
// Console output retains its original behavior and gains a source-attached Lens.
const originalLog=console.log;
console.log=function(...values){
  const stack=new Error().stack?.split('\n').slice(2)||[];
  const location=stack.map(s=>s.match(/:(\d+):\d+\)?$/)).find(Boolean);
  if(location)globalThis.lanternLens(values.length===1?values[0]:values,Number(location[1]),'console.log');
  return originalLog.apply(this,values);
};
setInterval(()=>flushLens(),100).unref();
process.on('exit',()=>flushLens(true));
