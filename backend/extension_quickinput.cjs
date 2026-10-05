// QuickInput identities stay in the extension process; the UI receives stable keys.
const crypto=require('node:crypto');
module.exports=function(v,call){
  const inputs=new Map(),back={iconPath:new v.ThemeIcon('arrow-left'),tooltip:'Atrás'};
  v.QuickInputButtons={Back:back};v.QuickPickItemKind={Default:0,Separator:-1};v.InputBoxValidationSeverity={Info:1,Warning:2,Error:3};
  function create(kind){
    const id=crypto.randomUUID(),events={},keys=new WeakMap(),objects=new Map();let disposed=false,visible=false,scheduled=false,queue=Promise.resolve(),ack=0;
    const state={title:'',step:undefined,totalSteps:undefined,value:'',placeholder:'',enabled:true,busy:false,ignoreFocusOut:false,buttons:[],items:[],activeItems:[],selectedItems:[],canSelectMany:false,matchOnLabel:true,matchOnDescription:false,matchOnDetail:false,keepScrollPosition:false,password:false,prompt:'',validationMessage:undefined,valueSelection:undefined};
    const emitter=name=>events[name]||(events[name]=new v.EventEmitter());
    const key=object=>{if(!keys.has(object)){const value=crypto.randomUUID();keys.set(object,value);objects.set(value,object);}return keys.get(object);};
    const button=b=>({key:key(b),back:b===back,tooltip:b.tooltip||'',icon:b.iconPath?.id||'ellipsis'});
    const snapshot=()=>({...state,id,kind,visible,ack,buttons:state.buttons.map(button),items:state.items.map(item=>({key:key(item),label:item.label,description:item.description,detail:item.detail,kind:item.kind,alwaysShow:item.alwaysShow,buttons:(item.buttons||[]).map(button)})),activeItems:state.activeItems.map(key),selectedItems:state.selectedItems.map(key)});
    const publish=()=>{if(disposed||scheduled)return;scheduled=true;queueMicrotask(()=>{scheduled=false;if(disposed)return;const data=snapshot();queue=queue.then(()=>call('quickinput.update',data)).catch(error=>{console.error(error.message);if(visible){visible=false;emitter('hide').fire();}});});};
    const input={_id:id,show(){if(disposed)throw Error('QuickInput cerrado.');visible=true;publish();},hide(){if(!visible||disposed)return;visible=false;publish();emitter('hide').fire();},dispose(){if(disposed)return;const wasVisible=visible;visible=false;disposed=true;inputs.delete(id);queue=queue.then(()=>call('quickinput.dispose',{id})).catch(error=>console.error(error.message));if(wasVisible)emitter('hide').fire();Object.values(events).forEach(x=>x.dispose());}};
    const names={onDidAccept:'accept',onDidChangeValue:'value',onDidHide:'hide',onDidTriggerButton:'button',onDidChangeActive:'active',onDidChangeSelection:'selection',onDidTriggerItemButton:'itemButton'};
    for(const [name,e] of Object.entries(names))input[name]=emitter(e).event;
    for(const name of Object.keys(state))Object.defineProperty(input,name,{enumerable:true,get:()=>state[name],set:value=>{if(name==='value'){value=String(value??'');if(state.value===value)return;state.value=value;publish();emitter('value').fire(value);return;}state[name]=value;publish();}});
    inputs.set(id,{input,state,receive(data){
      if(disposed||!visible)return;
      ack=Math.max(ack,data.sequence||0);
      if(data.type==='hide'){input.hide();return;}
      if(!state.enabled)return;
      if(data.type==='value')input.value=data.value;
      if(data.type==='active'){state.activeItems=(data.keys||[]).map(x=>objects.get(x)).filter(x=>state.items.includes(x)&&x.kind!==-1);emitter('active').fire(state.activeItems);}
      if(data.type==='selection'){state.selectedItems=(data.keys||[]).map(x=>objects.get(x)).filter(x=>state.items.includes(x)&&x.kind!==-1);if(!state.canSelectMany)state.selectedItems=state.selectedItems.slice(0,1);emitter('selection').fire(state.selectedItems);}
      if(data.type==='accept'&&!(kind==='input'&&(typeof state.validationMessage==='string'||state.validationMessage?.severity===3)&&state.validationMessage)){emitter('accept').fire();}
      if(data.type==='button'){const b=objects.get(data.key);if(state.buttons.includes(b))emitter('button').fire(b);}
      if(data.type==='itemButton'){const item=objects.get(data.item),b=objects.get(data.key);if(state.items.includes(item)&&item.buttons?.includes(b))emitter('itemButton').fire({item,button:b});}
      publish();
    }});return input;
  }
  v.window.createQuickPick=()=>create('pick');v.window.createInputBox=()=>create('input');
  const canceled=(input,token,finish)=>{if(token?.isCancellationRequested){finish(undefined);return true;}return token?.onCancellationRequested(()=>{input.hide();finish(undefined);});};
  v.window.showInputBox=(options={},token)=>new Promise((resolve,reject)=>{
    const input=create('input');let done=false,version=0,subscription;
    const finish=value=>{if(done)return;done=true;subscription?.dispose?.();input.dispose();resolve(value);};
    for(const name of ['title','prompt','password','ignoreFocusOut','value','valueSelection'])if(name in options)input[name]=options[name];input.placeholder=options.placeHolder||'';
    const validate=async value=>{const request=++version;input.busy=true;try{const message=await options.validateInput?.(value);if(!done&&request===version){input.validationMessage=message||undefined;input.busy=false;}}catch(error){if(!done){done=true;subscription?.dispose?.();input.dispose();reject(error);}}};
    input.onDidChangeValue(value=>validate(value));input.onDidAccept(()=>{if(!input.busy)finish(input.value);});input.onDidHide(()=>finish(undefined));
    subscription=canceled(input,token,finish);if(done)return;validate(input.value);input.show();
  });
  v.window.showQuickPick=async(items,options={},token)=>{
    items=await items;if(token?.isCancellationRequested)return undefined;
    const original=items,normalized=items.map(item=>typeof item==='string'?{label:item}:item),input=create('pick');
    return new Promise(resolve=>{let done=false,subscription;const finish=value=>{if(done)return;done=true;subscription?.dispose?.();input.dispose();resolve(value);};
      input.items=normalized;input.canSelectMany=!!options.canPickMany;input.selectedItems=options.canPickMany?normalized.filter(x=>x.picked):[];
      for(const name of ['title','ignoreFocusOut','matchOnDescription','matchOnDetail'])if(name in options)input[name]=options[name];input.placeholder=options.placeHolder||'';
      input.onDidChangeActive(active=>{if(active[0])options.onDidSelectItem?.(original[normalized.indexOf(active[0])]);});
      input.onDidAccept(()=>{const selected=input.selectedItems.map(x=>original[normalized.indexOf(x)]);finish(options.canPickMany?selected:selected[0]);});input.onDidHide(()=>finish(undefined));
      subscription=canceled(input,token,finish);if(!done)input.show();
    });
  };
  return data=>inputs.get(data.id)?.receive(data);
};
