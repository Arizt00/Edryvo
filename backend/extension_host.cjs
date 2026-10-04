// Preview extensions run in separate killable Node processes, not a security sandbox.
const readline=require('node:readline'),Module=require('node:module'),{pathToFileURL}=require('node:url');
const createAPI=require('./extension_api.cjs'),write=process.stdout.write.bind(process.stdout);
console.log=console.info=(...args)=>process.stderr.write(args.map(String).join(' ')+'\n');
// Helpers launched by extensions must never create incidental CMD windows.
const cp=require('node:child_process');
for(const name of ['spawn','spawnSync','execFile','execFileSync']){const original=cp[name];cp[name]=function(command,args,options,...rest){if(!Array.isArray(args)){rest=[options,...rest];options=args;args=[];}if(typeof options==='function'){rest.unshift(options);options={};}return original.call(this,command,args,{...options,windowsHide:true},...rest.filter(x=>x!==undefined));};}
const commands=new Map(),providers=[],tokens=[];let active={path:'',text:'',language:'plaintext'},effects=[],bridge,loaded=false;
const disposable=fn=>({dispose:fn||(()=>{})});
const registerCommand=(id,fn,title=id)=>{commands.set(id,{fn,title});return disposable(()=>commands.delete(id));};
const register=(kind,language,fn,extra={})=>{const p={kind,language,fn,...extra};providers.push(p);return disposable(()=>{const i=providers.indexOf(p);if(i>=0)providers.splice(i,1);});};
const api={registerCommand,registerCompletionProvider:(l,f)=>register('completion',l,f),registerDefinitionProvider:(l,f)=>register('definition',l,f),registerInlayHintsProvider:(l,f)=>register('inlay',l,f),registerDiagnosticsProvider:(l,f)=>register('diagnostics',l,f),registerTokens:(language,rules)=>tokens.push({language,rules}),getDocument:()=>({...active}),notify:message=>effects.push({message:String(message)})};
const original=Module._load;Module._load=function(id,...args){return id==='vscode'?bridge.vscode:id==='lumen'?api:original.call(this,id,...args);};
async function request(message){
  if(message.method==='activate'){
    bridge=createAPI({...api,register,effect:e=>effects.push(e),commandIds:()=>[...commands.keys()],execute:async(id,args)=>{if(commands.has(id))return commands.get(id).fn(...args);if(['setContext','workbench.action.reloadWindow'].includes(id))return;throw Error('El comando '+id+' no está disponible en Lumen.');}},{...message,id:message.extensionId});
    const extension=await import(pathToFileURL(message.entry).href),target=extension.default||extension;
    if(typeof target.activate!=='function')throw Error('La extensión no exporta activate().');
    await target.activate(bridge.context,api);loaded=true;
    const manifest=message.manifest;
    for(const command of manifest.contributes?.commands||[])if(commands.has(command.command))commands.get(command.command).title=command.title;
    const capabilities=providers.map(({kind,language,legend,triggers})=>({kind,language,legend,triggers}));
    if(bridge.diagnosticCollections.size)for(const language of manifest.contributes?.languages||[])capabilities.push({kind:'diagnostics',language:language.id});
    return {commands:[...commands].map(([id,c])=>({id,title:c.title})),providers:capabilities,tokens,views:bridge.treeViews.snapshot()};
  }
  if(!loaded)throw Error('Extensión no activada.');
  effects=[];active=message.document||active;bridge.syncDocument(active);
  if(message.method==='willSave')return bridge.willSave(message.reason);
  if(message.method==='didSave'){bridge.didSave();return {ok:true};}
  if(message.method==='virtual')return {text:await bridge.readVirtual(message.uri)};
  if(message.method==='tree')return message.view?bridge.treeViews.children(message.view,message.element):{views:bridge.treeViews.snapshot()};
  if(message.method==='command'){
    const c=commands.get(message.command);if(!c)throw Error('Comando no registrado.');
    return {result:await c.fn(...(c.fn.vscodeCommand?[]:[{...active}]),...bridge.treeViews.arguments(message.arguments||[])),effects};
  }
  if(message.method==='provide'){
    const result=[];
    for(const p of providers.filter(p=>p.kind===message.kind&&(p.language===active.language||p.language==='*'))){
      const value=await p.fn({...active,position:message.position,range:message.range,newName:message.newName});
      result.push(...(Array.isArray(value)?value:(value?.items||value?.hints||(value?[value]:[]))));
    }
    if(message.kind==='diagnostics')result.push(...bridge.getDiagnostics().map(d=>({line:d.range.start.line+1,column:d.range.start.character+1,endLine:d.range.end.line+1,endColumn:d.range.end.character+1,message:d.message,severity:['error','warning','info','hint'][d.severity||0]})));
    return {items:result};
  }
  throw Error('Método no disponible en la API preview.');
}
let queue=Promise.resolve();
readline.createInterface({input:process.stdin}).on('line',line=>{
  queue=queue.then(async()=>{let m;try{m=JSON.parse(line);const result=await request(m);const text=JSON.stringify({id:m.id,result},(_,v)=>v instanceof Uint32Array?[...v]:v);if(Buffer.byteLength(text)>2000000)throw Error('Respuesta de extensión demasiado grande.');write(text+'\n');}catch(error){write(JSON.stringify({id:m?.id,error:error.message})+'\n');}});
});
