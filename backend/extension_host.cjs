// Preview extensions run in separate killable Node processes, not a security sandbox.
const readline=require('node:readline'),Module=require('node:module'),{pathToFileURL}=require('node:url');
const createAPI=require('./extension_api.cjs'),write=process.stdout.write.bind(process.stdout);
console.log=console.info=(...args)=>process.stderr.write(args.map(String).join(' ')+'\n');
// Helpers launched by extensions must never create incidental CMD windows.
const cp=require('node:child_process');
for(const name of ['spawn','spawnSync','execFile','execFileSync']){const original=cp[name];cp[name]=function(command,args,options,...rest){if(!Array.isArray(args)){rest=[options,...rest];options=args;args=[];}if(typeof options==='function'){rest.unshift(options);options={};}return original.call(this,command,args,{...options,windowsHide:true},...rest.filter(x=>x!==undefined));};}
const commands=new Map(),providers=[],tokens=[],actions=new Map();let actionSequence=0;let active={path:'',text:'',language:'plaintext'},effects=[],bridge,loaded=false;
const pendingServices=new Map();let serviceSequence=0;
function service(method,params={}){const id=++serviceSequence;return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{pendingServices.delete(id);reject(Error('El servicio '+method+' no respondió.'));},45000);pendingServices.set(id,{resolve,reject,timer});write(JSON.stringify({type:'service',id,method,params})+'\n');});}
const disposable=fn=>({dispose:fn||(()=>{})});
const registerCommand=(id,fn,title=id)=>{commands.set(id,{fn,title});return disposable(()=>commands.delete(id));};
const register=(kind,language,fn,extra={})=>{const p={kind,language,fn,...extra};providers.push(p);return disposable(()=>{const i=providers.indexOf(p);if(i>=0)providers.splice(i,1);});};
const api={registerCommand,registerCompletionProvider:(l,f)=>register('completion',l,f),registerDefinitionProvider:(l,f)=>register('definition',l,f),registerInlayHintsProvider:(l,f)=>register('inlay',l,f),registerDiagnosticsProvider:(l,f)=>register('diagnostics',l,f),registerTokens:(language,rules)=>tokens.push({language,rules}),getDocument:()=>({...active}),notify:message=>effects.push({message:String(message)})};
const extensionStates=new Map(),bridges=new Map(),path=require('node:path');
const {AsyncLocalStorage}=require('node:async_hooks'),extensionScope=new AsyncLocalStorage();
function owner(parent){const file=parent?.filename?.toLowerCase();if(file)for(const [root,b] of bridges)if(file.startsWith(root+path.sep))return b;return extensionScope.getStore()||bridge;}
const original=Module._load;Module._load=function(id,parent,...args){return id==='vscode'?owner(parent).vscode:id==='lumen'?api:original.call(this,id,parent,...args);};
async function request(message){
  if(message.method==='activate'){
    const authorised=[...(message.dependencies||[]),{id:message.extensionId,root:message.root,manifest:message.manifest,entry:message.entry}];
    const activateExtension=async id=>{
      const key=id.toLowerCase(),record=extensionStates.get(key);
      if(record?.active)return record.exports;
      const item=authorised.find(x=>x.id.toLowerCase()===key);if(!item)throw Error('Dependencia no autorizada: '+id);
      if(record?.activating)throw Error('Activación circular: '+id);
      extensionStates.set(key,{activating:true});
      const b=createAPI({...api,register,service,extensionState:id=>extensionStates.get(id.toLowerCase()),activateExtension,effect:e=>effects.push(e),commandIds:()=>[...commands.keys()],execute:async(id,args)=>{if(commands.has(id))return commands.get(id).fn(...args);if(id==='setContext')return service('context.set',{key:args[0],value:args[1]});if(id==='workbench.action.tasks.runTask')return b.services.runTask(args[0]);return service('command.execute',{id,args});}},{...message,id:item.id,root:item.root,manifest:item.manifest,storage:path.join(path.dirname(message.storage),item.id)});
      bridges.set(path.resolve(item.root).toLowerCase(),b);if(key===message.extensionId.toLowerCase())bridge=b;
      const declared=item.manifest.lumen?.main||item.manifest.main;
      let entry=item.entry||path.resolve(item.root,declared||'');
      if(declared&&!require('node:fs').existsSync(entry)&&require('node:fs').existsSync(entry+'.js'))entry+='.js';
      if(declared||item.entry){
        const relative=path.relative(item.root,entry);if(relative.startsWith('..')||path.isAbsolute(relative))throw Error('main fuera de la extensión: '+item.id);
        const value=await extensionScope.run(b,async()=>{const extension=await import(pathToFileURL(entry).href),target=extension.default||extension;if(typeof target.activate!=='function')throw Error('La extensión no exporta activate(): '+item.id);return target.activate(b.context,api);});
        extensionStates.set(key,{active:true,exports:value});
      }else extensionStates.set(key,{active:true,exports:undefined});
      for(const command of item.manifest.contributes?.commands||[])if(commands.has(command.command))commands.get(command.command).title=command.title;
      return extensionStates.get(key).exports;
    };
    for(const item of authorised)await activateExtension(item.id);loaded=true;
    const manifest=message.manifest;
    for(const command of manifest.contributes?.commands||[])if(commands.has(command.command))commands.get(command.command).title=command.title;
    const capabilities=providers.map(({kind,language,legend,triggers})=>({kind,language,legend,triggers}));
    for(const item of authorised){const b=bridges.get(path.resolve(item.root).toLowerCase());if(b.diagnosticCollections.size)for(const language of item.manifest.contributes?.languages||[])capabilities.push({kind:'diagnostics',language:language.id});}
    return {commands:[...commands].map(([id,c])=>({id,title:c.title})),providers:capabilities,tokens,views:[...bridges.values()].flatMap(b=>b.treeViews.snapshot()),fileDecorations:[...bridges.values()].some(b=>b.hasFileDecorations()),unsupportedApis:[...new Set([...bridges.values()].flatMap(b=>[...b.unsupportedApis]))],dependencies:authorised.slice(0,-1).map(x=>x.id)};
  }
  if(!loaded)throw Error('Extensión no activada.');
  if(message.method==='webviewMessage'){for(const b of bridges.values()){const result=await b.services.message(message.panel,message.message);if(result.delivered)return result;}return {delivered:false};}
  if(message.method==='webviewDispose'){for(const b of bridges.values())b.services.disposePanel(message.panel);return {ok:true};}
  effects=[];active=message.document||active;for(const b of bridges.values())b.syncDocument(active);
  if(message.method==='willSave'){const edits=[];for(const b of bridges.values())edits.push(...(await b.willSave(message.reason)).edits);return {edits};}
  if(message.method==='didSave'){for(const b of bridges.values())b.didSave();return {ok:true};}
  if(message.method==='virtual'){for(const b of bridges.values())if(b.hasVirtual(message.uri))return {text:await b.readVirtual(message.uri)};throw Error('Documento virtual no registrado.');}
  if(message.method==='decorations'){if(bridges.size===1)return bridge.fileDecorations(message.paths,message.revision);const items=[];let revision=0;for(const b of bridges.values()){const r=await b.fileDecorations(message.paths);items.push(...r.items||[]);revision+=r.revision||0;}return {items,revision};}
  if(message.method==='tree'){const b=[...bridges.values()].find(x=>x.treeViews.snapshot().some(v=>v.id===message.view));if(message.view&&!b)throw Error('Vista de extensión no registrada: '+message.view);return message.view?b.treeViews.children(message.view,message.element):{views:[...bridges.values()].flatMap(x=>x.treeViews.snapshot())};}
  if(message.method==='command'){
    const c=commands.get(message.command);if(!c)throw Error('Comando no registrado.');
    const args=(message.arguments||[]).map(value=>{const ref=value?.$lumenTreeElement;if(!ref)return value;const b=[...bridges.values()].find(x=>x.treeViews.snapshot().some(v=>v.id===ref.view));if(!b)throw Error('Vista de argumento no registrada.');return b.treeViews.arguments([value])[0];});
    return {result:await c.fn(...(c.fn.vscodeCommand?[]:[{...active}]),...args),effects};
  }
  if(message.method==='resolveAction'){
    const cached=actions.get(message.action);if(!cached)throw Error('La corrección caducó. Solicita de nuevo las acciones.');
    if(cached.path!==active.path||cached.text!==active.text)throw Error('El archivo cambió. Solicita de nuevo las acciones.');
    return {action:cached.provider.resolver?await cached.provider.resolver(cached.item)||cached.item:cached.item};
  }
  if(message.method==='provide'){
    const result=[];
    for(const p of providers.filter(p=>p.kind===message.kind&&(p.language===active.language||p.language==='*'))){
      const value=await p.fn({...active,position:message.position,range:message.range,newName:message.newName,context:message.context,options:message.options,character:message.character,positions:message.positions,color:message.color});
      const items=Array.isArray(value)?value:(value?.items||value?.hints||(value?[value]:[]));
      if(message.kind==='actions')for(const item of items){const key=String(++actionSequence);actions.set(key,{provider:p,item,path:active.path,text:active.text});if(actions.size>256)actions.delete(actions.keys().next().value);result.push({...item,_lumenAction:key});}
      else result.push(...items);
    }
    if(message.kind==='diagnostics')for(const b of bridges.values())result.push(...b.getDiagnostics().map(d=>({line:d.range.start.line+1,column:d.range.start.character+1,endLine:d.range.end.line+1,endColumn:d.range.end.character+1,message:d.message,severity:['error','warning','info','hint'][d.severity||0]})));
    return {items:result};
  }
  throw Error('Método no disponible en la API preview.');
}
let queue=Promise.resolve();
readline.createInterface({input:process.stdin}).on('line',line=>{
  let message;try{message=JSON.parse(line);}catch{return;}
  if(message.type==='serviceResult'){const p=pendingServices.get(message.id);if(p){pendingServices.delete(message.id);clearTimeout(p.timer);message.error?p.reject(Error(message.error)):p.resolve(message.result);}return;}
  if(message.type==='serviceEvent'){for(const b of bridges.values())b.services?.event(message.name,message.value);return;}
  queue=queue.then(async()=>{let m;try{m=JSON.parse(line);const result=await request(m);const text=JSON.stringify({id:m.id,result},(_,v)=>v instanceof Uint32Array?[...v]:v);if(Buffer.byteLength(text)>2000000)throw Error('Respuesta de extensión demasiado grande.');write(text+'\n');}catch(error){write(JSON.stringify({id:m?.id,error:error.message})+'\n');}});
});
