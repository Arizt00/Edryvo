// Real TreeDataProvider storage: opaque handles retain the extension's own objects.
module.exports=function createViews(vscode){
  const views=new Map();let next=0;
  function register(id,provider,options={}){
    if(views.has(id))views.get(id).dispose();
    const tree={id,provider,revision:0,elements:new Map(),ids:new Map(),selection:[],visible:true};
    const expand=new vscode.EventEmitter(),collapse=new vscode.EventEmitter(),select=new vscode.EventEmitter(),visibility=new vscode.EventEmitter();
    const subscription=provider.onDidChangeTreeData?.(()=>{tree.revision++;});
    const view={onDidExpandElement:expand.event,onDidCollapseElement:collapse.event,onDidChangeSelection:select.event,onDidChangeVisibility:visibility.event,get selection(){return tree.selection;},get visible(){return tree.visible;},reveal:async element=>{if(!tree.ids.has(element))throw Error('Carga el elemento de la vista antes de revelarlo.');tree.selection=[element];select.fire({selection:tree.selection});},dispose(){subscription?.dispose();expand.dispose();collapse.dispose();select.dispose();visibility.dispose();views.delete(id);}};
    Object.assign(tree,{view,expand,collapse,select,visibility,dispose:view.dispose});views.set(id,tree);return view;
  }
  async function children(id,parent){
    const tree=views.get(id);if(!tree)throw Error('Vista de extensión no registrada: '+id);
    const element=parent?tree.elements.get(parent):undefined;if(parent&&!tree.elements.has(parent))throw Error('El elemento de la vista ya no existe. Actualiza la vista.');
    if(element)tree.expand.fire({element});
    const children=await tree.provider.getChildren(element)||[];if(children.length>5000)throw Error('La vista contiene demasiados elementos.');
    const items=[];
    for(const child of children){const item=await tree.provider.getTreeItem(child);let key=tree.ids.get(child);if(!key){key='tree-'+(++next);tree.ids.set(child,key);tree.elements.set(key,child);}const command=item.command?{...item.command,arguments:(item.command.arguments||[]).map(a=>a===child?{$lumenTreeElement:{view:id,key}}:a)}:undefined;items.push({key,label:typeof item.label==='object'?item.label.label:item.label||item.resourceUri?.fsPath||'',description:item.description===true?item.resourceUri?.fsPath:item.description,tooltip:typeof item.tooltip==='object'?item.tooltip.value:item.tooltip,collapsibleState:item.collapsibleState||0,contextValue:item.contextValue,command});}
    return {items,revision:tree.revision};
  }
  vscode.window.registerTreeDataProvider=(id,p)=>register(id,p);
  vscode.window.createTreeView=(id,options)=>register(id,options.treeDataProvider,options);
  return {snapshot:()=>[...views].map(([id,v])=>({id,revision:v.revision})),children,arguments:values=>values.map(v=>{const ref=v?.$lumenTreeElement;if(!ref)return v;const tree=views.get(ref.view);if(!tree?.elements.has(ref.key))throw Error('Elemento de la vista caducado.');return tree.elements.get(ref.key);})};
};
