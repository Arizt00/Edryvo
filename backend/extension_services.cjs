// Stateful IDE services. A result is returned only after the backend accepts it.
const path=require('node:path'),crypto=require('node:crypto');
module.exports=function install(v,host,options,event,makeDocument,documents){
  const call=(method,params)=>{if(!host.service)throw Error('Servicios del IDE no conectados.');return host.service(method,params);};
  const terminals=new Map(),executions=new Map(),panels=new Map(),taskProviders=new Map(),debugProviders=new Map(),factories=new Map(),sessions=new Map(),trackers=new Map(),inline=new Map(),contexts=new Map();let activeTerminal;
  const folder=v.workspace.workspaceFolders[0],uid=()=>crypto.randomUUID(),token={isCancellationRequested:false,onCancellationRequested:event('serviceCancellation').event};
  const terminal=(opts={},shellPath,shellArgs)=>{
    if(typeof opts==='string')opts={name:opts,shellPath,shellArgs};
    const id=uid(),t={_id:id,name:opts.name||'Terminal',creationOptions:opts,state:{isInteractedWith:false},exitStatus:undefined};
    const ready=call('terminal.create',{id,options:{...opts,pty:!!opts.pty}}).then(info=>{t._pid=info.pid;event('terminalOpen').fire(t);if(opts.pty)opts.pty.open(info.dimensions);return info;});
    t.processId=ready.then(info=>info.pid);t._ready=ready;
    const invoke=(method,params={})=>ready.then(()=>call(method,{id,...params})).catch(e=>host.notify(e.message));
    t.sendText=(text,addNewLine=true)=>{t.state.isInteractedWith=true;invoke('terminal.write',{text:String(text)+(addNewLine?'\r':'')});};
    t.show=(preserveFocus=false)=>{activeTerminal=t;invoke('terminal.show',{preserveFocus});event('activeTerminal').fire(t);};
    t.hide=()=>invoke('terminal.hide');t.dispose=()=>invoke('terminal.close');terminals.set(id,t);
    if(opts.pty){opts.pty.onDidWrite(text=>invoke('terminal.append',{text}));opts.pty.onDidClose?.(code=>invoke('terminal.finish',{code}));opts.pty.onDidChangeName?.(name=>{t.name=name;invoke('terminal.name',{name});});}
    return t;
  };
  Object.assign(v.window,{createTerminal:terminal,onDidOpenTerminal:event('terminalOpen').event,onDidCloseTerminal:event('terminalClose').event,onDidChangeActiveTerminal:event('activeTerminal').event,onDidChangeTerminalState:event('terminalState').event,onDidChangeTerminalDimensions:event('terminalDimensions').event});
  Object.defineProperties(v.window,{terminals:{get:()=>[...terminals.values()]},activeTerminal:{get:()=>activeTerminal}});
  v.TaskScope={Global:1,Workspace:2};v.TaskGroup=class{constructor(id,label){Object.assign(this,{id,label,isDefault:false});}};
  for(const [key,id] of Object.entries({Clean:'clean',Build:'build',Rebuild:'rebuild',Test:'test'}))v.TaskGroup[key]=new v.TaskGroup(id,key);
  v.ProcessExecution=class{constructor(process,args=[],options={}){if(!Array.isArray(args)){options=args;args=[];}Object.assign(this,{process,args,options});}};
  v.ShellExecution=class{constructor(command,args,options){if(Array.isArray(args))Object.assign(this,{command,args,options:options||{}});else Object.assign(this,{commandLine:command,options:args||{}});}};
  v.CustomExecution=class{constructor(callback){this.callback=callback;}};
  v.Task=class{constructor(definition,scope,name,source,execution,problemMatchers=[]){Object.assign(this,{definition,scope,name,source,execution,problemMatchers,isBackground:false});}};
  Object.assign(v.tasks,{
    registerTaskProvider(type,provider){taskProviders.set(type,provider);return new v.Disposable(()=>taskProviders.delete(type));},
    async fetchTasks(filter={}){const list=[];for(const [type,p] of taskProviders)if(!filter.type||filter.type===type)list.push(...await p.provideTasks(token)||[]);const file=path.join(options.workspace,'.vscode/tasks.json');if(require('node:fs').existsSync(file)){const config=jsonc(require('node:fs').readFileSync(file,'utf8'));for(const raw of config.tasks||[]){const platform=process.platform==='win32'?'windows':process.platform==='darwin'?'osx':'linux',item={...raw,...raw[platform]};if(filter.type&&item.type!==filter.type)continue;const opts={...config.options,...item.options};let execution;if(item.type==='shell')execution=new v.ShellExecution(item.command,item.args||[],opts);else if(item.type==='process')execution=new v.ProcessExecution(item.command,item.args||[],opts);let task=new v.Task(item,folder,item.label||item.type,'Workspace',execution,item.problemMatcher||[]);Object.assign(task,{isBackground:!!item.isBackground,presentationOptions:item.presentation,group:item.group,runOptions:item.runOptions});if(!execution&&taskProviders.get(item.type)?.resolveTask)task=await taskProviders.get(item.type).resolveTask(task,token)||task;list.push(task);}}return list;},
    async executeTask(task){
      const p=taskProviders.get(task.definition?.type);if(!task.execution&&p?.resolveTask)task=await p.resolveTask(task,token)||task;
      if(!task.execution)throw Error('La tarea no tiene ejecución resuelta.');
      const id=uid(),execution={task,_id:id,terminate:()=>call('task.terminate',{id}).catch(e=>host.notify(e.message))};executions.set(id,execution);
      execution._events=[];
      try{
        if(task.execution instanceof v.CustomExecution){const pty=await task.execution.callback(task.definition),t=terminal({name:task.name,pty});await t._ready;execution._terminal=t._id;await call('task.custom',{id,terminal:t._id});}
        else await call('task.execute',{id,task:{name:task.name,definition:task.definition,execution:variables(task.execution),problemMatchers:task.problemMatchers,presentationOptions:task.presentationOptions,isBackground:task.isBackground}});
        event('taskStart').fire({execution});const queued=execution._events;delete execution._events;for(const [name,value] of queued)serviceEvent(name,value);return execution;
      }catch(error){executions.delete(id);throw error;}
    },onDidStartTaskProcess:event('taskProcessStart').event
  });
  Object.defineProperty(v.tasks,'taskExecutions',{get:()=>[...executions.values()]});
  v.window.showQuickPick=async(items,opts={})=>{items=await items;const indices=await call('window.pick',{items:items.map(x=>typeof x==='string'?{label:x}:x),options:opts});return indices==null?undefined:opts.canPickMany?indices.map(i=>items[i]):items[indices];};
  async function runTask(filter){const tasks=await v.tasks.fetchTasks(typeof filter==='object'?filter:{});let task=typeof filter==='string'?tasks.find(x=>x.name===filter||x.definition?.label===filter):undefined;if(!task){const picked=await v.window.showQuickPick(tasks.map((x,i)=>({label:x.name,description:x.source,index:i})),{title:'Ejecutar tarea',placeHolder:'Elige una tarea de tus extensiones'});task=picked&&tasks[picked.index];}return task?await v.tasks.executeTask(task):undefined;}
  function panel(viewType,title,column,opts={},id=uid()){
    let html='',disposed=false;const receive=new v.EventEmitter(),didDispose=new v.EventEmitter(),viewState=new v.EventEmitter();
    const p={_id:id,viewType,title,viewColumn:typeof column==='object'?column.viewColumn:column,active:true,visible:true,options:opts};
    const ready=call('webview.create',{id,viewType,title,column:p.viewColumn,options:opts});
    const update=data=>ready.then(()=>call('webview.update',{id,...data})).catch(e=>host.notify(e.message));
    const webview={cspSource:'blob: data:',onDidReceiveMessage:receive.event,
      asWebviewUri(uri){return v.Uri.parse('zenit-resource://'+id+'/'+encodeURIComponent(uri.fsPath));},
      async postMessage(message){await ready;return call('webview.post',{id,message});}
    };
    Object.defineProperty(webview,'html',{get:()=>html,set:value=>{html=String(value);update({html});}});
    Object.defineProperty(webview,'options',{get:()=>opts,set:value=>{opts=value;update({options:value});}});
    Object.defineProperty(p,'title',{get:()=>title,set:value=>{title=String(value);update({title});}});
    Object.assign(p,{webview,onDidDispose:didDispose.event,onDidChangeViewState:viewState.event,reveal(c=p.viewColumn,preserveFocus=false){p.visible=true;p.viewColumn=c;update({visible:true,column:c,preserveFocus,revealSequence:Date.now()});},dispose(){if(disposed)return;disposed=true;p.visible=p.active=false;update({disposed:true});panels.delete(id);didDispose.fire();receive.dispose();didDispose.dispose();viewState.dispose();},_receive:receive,_state:viewState});
    panels.set(id,p);return p;
  }
  v.ViewColumn={Active:-1,Beside:-2,One:1,Two:2,Three:3,Four:4,Five:5,Nine:9};
  v.window.createWebviewPanel=panel;
  v.window.registerWebviewViewProvider=(id,provider,opts={})=>{const p=panel(id,id,1,opts);p.show=p.reveal;p.onDidChangeVisibility=p.onDidChangeViewState;Promise.resolve(provider.resolveWebviewView(p,{state:undefined},token)).catch(e=>host.notify(e.message));return new v.Disposable(()=>p.dispose());};
  v.window.registerWebviewPanelSerializer=(id,serializer)=>{contexts.set('serializer:'+id,serializer);return new v.Disposable(()=>contexts.delete('serializer:'+id));};
  v.DebugAdapterServer=class{constructor(port,host='127.0.0.1'){Object.assign(this,{port,host});}};
  v.DebugAdapterNamedPipeServer=class{constructor(path){this.path=path;}};
  v.DebugAdapterInlineImplementation=class{constructor(implementation){this.implementation=implementation;}};
  v.SourceBreakpoint=class{constructor(location,enabled=true,condition,hitCondition,logMessage){Object.assign(this,{id:uid(),location,enabled,condition,hitCondition,logMessage});}};
  v.FunctionBreakpoint=class{constructor(functionName,enabled=true,condition,hitCondition,logMessage){Object.assign(this,{id:uid(),functionName,enabled,condition,hitCondition,logMessage});}};
  const breakpoints=[];
  Object.assign(v.debug,{
    registerDebugConfigurationProvider(type,p){debugProviders.set(type,p);return new v.Disposable(()=>debugProviders.delete(type));},
    registerDebugAdapterDescriptorFactory(type,p){factories.set(type,p);return new v.Disposable(()=>factories.delete(type));},
    registerDebugAdapterTrackerFactory(type,p){trackers.set(type,p);return new v.Disposable(()=>trackers.delete(type));},
    get breakpoints(){return breakpoints;},addBreakpoints(values){breakpoints.push(...values);event('breakpoints').fire({added:values,removed:[],changed:[]});syncBreakpoints();},removeBreakpoints(values){for(const bp of values){const i=breakpoints.findIndex(x=>x.id===bp.id);if(i>=0)breakpoints.splice(i,1);}event('breakpoints').fire({added:[],removed:values,changed:[]});syncBreakpoints();},onDidChangeBreakpoints:event('breakpoints').event,
    async startDebugging(scope,configuration,opts={}){
      if(typeof configuration==='string')configuration=configurationForName(configuration);
      if(!configuration?.type)throw Error('La configuración de depuración requiere type.');
      const p=debugProviders.get(configuration.type);if(p?.resolveDebugConfiguration)configuration=await p.resolveDebugConfiguration(folder,configuration,token);if(!configuration)return false;
      configuration=variables(configuration);if(p?.resolveDebugConfigurationWithSubstitutedVariables)configuration=await p.resolveDebugConfigurationWithSubstitutedVariables(folder,configuration,token);if(!configuration)return false;
      const id=uid(),session={id,type:configuration.type,name:configuration.name||configuration.type,configuration,workspaceFolder:folder,parentSession:opts.parentSession,customRequest:(command,args)=>call('debug.request',{id,command,args})};
      const contribution=(options.manifest.contributes?.debuggers||[]).find(x=>x.type===configuration.type),platform=process.platform==='win32'?'windows':process.platform==='darwin'?'osx':'linux',entry={...contribution,...contribution?.[platform]};
      let executable=entry.program?new v.DebugAdapterExecutable(entry.runtime||path.resolve(options.root,entry.program),entry.runtime?[path.resolve(options.root,entry.program),...entry.args||[]]:entry.args||[],{}):undefined;
      let descriptor=factories.has(configuration.type)?await factories.get(configuration.type).createDebugAdapterDescriptor(session,executable):executable;
      if(!descriptor)throw Error('La extensión no proporcionó un adaptador de depuración.');
      let wire=descriptor;
      if(descriptor instanceof v.DebugAdapterInlineImplementation){inline.set(id,descriptor.implementation);descriptor.implementation.onDidSendMessage(message=>call('debug.message',{id,message}).catch(e=>host.notify(e.message)));wire={inline:true};}
      session._tracker=await (trackers.get(configuration.type)||trackers.get('*'))?.createDebugAdapterTracker(session);session._tracker?.onWillStartSession?.();sessions.set(id,session);
      try{await call('debug.start',{id,configuration,descriptor:wire,breakpoints});event('debugStart').fire(session);event('activeDebug').fire(session);return true;}
      catch(error){sessions.delete(id);inline.get(id)?.dispose();inline.delete(id);session._tracker?.onError?.(error);throw error;}
    },stopDebugging:async session=>call('debug.stop',{id:session?.id||[...sessions.keys()].at(-1)}),onDidChangeActiveDebugSession:event('activeDebug').event,onDidReceiveDebugSessionCustomEvent:event('debugCustom').event
  });
  Object.defineProperty(v.debug,'activeDebugSession',{get:()=>[...sessions.values()].at(-1)});
  function syncBreakpoints(){for(const id of sessions.keys())call('debug.breakpoints',{id,breakpoints}).catch(e=>host.notify(e.message));}
  function variables(value){if(typeof value==='string')return value.replace(/\$\{workspaceFolder\}/g,options.workspace).replace(/\$\{file\}/g,v.window.activeTextEditor?.document.fileName||'').replace(/\$\{env:([^}]+)\}/g,(_,key)=>process.env[key]||'');if(Array.isArray(value))return value.map(variables);if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).map(([key,x])=>[key,variables(x)]));return value;}
  function configurationForName(name){const fs=require('node:fs');const values=jsonc(fs.readFileSync(path.join(options.workspace,'.vscode/launch.json'),'utf8'));return values.configurations.find(c=>c.name===name);}
  function jsonc(text){
    let clean='',quote=false,escaped=false;
    for(let i=0;i<text.length;i++){
      const ch=text[i],next=text[i+1];
      if(quote){clean+=ch;if(escaped)escaped=false;else if(ch==='\\')escaped=true;else if(ch==='"')quote=false;continue;}
      if(ch==='"'){quote=true;clean+=ch;}
      else if(ch==='/'&&next==='/'){while(i<text.length&&text[i]!=='\n')i++;clean+='\n';}
      else if(ch==='/'&&next==='*'){i+=2;while(i<text.length&&!(text[i]==='*'&&text[i+1]==='/'))i++;if(i>=text.length)throw Error('Comentario JSONC sin cerrar.');i++;clean+=' ';}
      else clean+=ch;
    }
    let result='';quote=false;escaped=false;
    for(let i=0;i<clean.length;i++){
      const ch=clean[i];
      if(quote){result+=ch;if(escaped)escaped=false;else if(ch==='\\')escaped=true;else if(ch==='"')quote=false;continue;}
      if(ch==='"')quote=true;
      if(ch===','){let j=i+1;while(j<clean.length&&/\s/.test(clean[j]))j++;if(['}',']'].includes(clean[j]))continue;}
      result+=ch;
    }
    return JSON.parse(result);
  }
  function serviceEvent(name,value){
      const execution=executions.get(value?.id);
      if(name.startsWith('task.')&&execution?._events){execution._events.push([name,value]);return;}
      dispatch(name,value);
  }
  function dispatch(name,value){
      const t=terminals.get(value?.id),execution=executions.get(value?.id),session=sessions.get(value?.id);
      if(name==='terminal.close'&&t){t.exitStatus={code:value.code,reason:value.reason||1};t.creationOptions.pty?.close?.();terminals.delete(value.id);event('terminalClose').fire(t);if(activeTerminal===t){activeTerminal=undefined;event('activeTerminal').fire(undefined);}}
      if(name==='terminal.input'&&t)t.creationOptions.pty?.handleInput?.(value.text);
      if(name==='terminal.dimensions'&&t){t.creationOptions.pty?.setDimensions?.(value.dimensions);event('terminalDimensions').fire({terminal:t,dimensions:value.dimensions});}
      if(name==='task.processStart'&&execution)event('taskProcessStart').fire({execution,processId:value.pid});
      if(name==='task.end'&&execution){if(!(execution.task.execution instanceof v.CustomExecution))event('taskProcessEnd').fire({execution,exitCode:value.code});event('taskEnd').fire({execution});executions.delete(value.id);}
      if(name==='debug.send'&&session){session._tracker?.onWillReceiveMessage?.(value.message);inline.get(value.id)?.handleMessage(value.message);}
      if(name==='debug.event'&&session){session._tracker?.onDidSendMessage?.(value.message);event('debugCustom').fire({session,event:value.message.event,body:value.message.body});}
      if(name==='debug.stop'&&session){session._tracker?.onWillStopSession?.();inline.get(value.id)?.dispose();inline.delete(value.id);sessions.delete(value.id);event('debugStop').fire(session);event('activeDebug').fire(v.debug.activeDebugSession);}
  }
  return {
    runTask,
    async message(id,message){const p=panels.get(id);if(!p)return {delivered:false};p._receive.fire(message);return {delivered:true};},disposePanel(id){panels.get(id)?.dispose();return {ok:true};},
    event:serviceEvent
  };
};
