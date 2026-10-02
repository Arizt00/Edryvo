import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const css=readFileSync(new URL('../web/atelier.css',import.meta.url),'utf8');
function luminance(hex){const c=[1,3,5].map(n=>parseInt(hex.slice(n,n+2),16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return c[0]*.2126+c[1]*.7152+c[2]*.0722;}
function ratio(a,b){const v=[luminance(a),luminance(b)].sort((a,b)=>a-b);return (v[1]+.05)/(v[0]+.05);}
const blocks=[...css.matchAll(/:root(?:\[data-theme="(?:dark|forest)"\])?\s*\{([^}]+)\}/g)].slice(0,3);
for(const [i,block] of blocks.entries())test(`Theme ${['day','dark','forest'][i]}: specified primary text and syntax pairs >= 4.5:1`,()=>{
  const t=Object.fromEntries([...block[1].matchAll(/--([a-z-]+):(#\w{6})/g)].map(m=>[m[1],m[2]]));
  for(const [fg,bg] of [['text','surface'],['secondary','surface'],['muted','surface'],['muted','bg'],['accent','selected'],...Object.keys(t).filter(k=>k.startsWith('syntax-')).map(k=>[k,'editor'])]){
    assert.ok(ratio(t[fg],t[bg])>=4.5,`${fg} on ${bg}: ${ratio(t[fg],t[bg])}`);
  }
});
