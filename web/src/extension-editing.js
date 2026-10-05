/** Translate VS Code editing providers to Monaco, preserving buffer revisions. */
export function editingProvider(ext,p,{m,ed,call,mr,relativeUri,host}){
  const pos=p=>({line:p.lineNumber-1,character:p.column-1});
  const range=r=>({start:{line:r.startLineNumber-1,character:r.startColumn-1},end:{line:r.endLineNumber-1,character:r.endColumn-1}});
  const textEdits=items=>items.map(e=>({range:mr(e.range),text:e.newText}));
  const checked=async(model,kind,extra={})=>{
    const version=model.getVersionId(),items=await call(ext,kind,model,extra);
    return model.isDisposed()||model.getVersionId()!==version?[]:items;
  };
  const workspaceEdit=async(edit,source,version)=>{
    const edits=[];
    for(const c of edit?.changes||[]){
      const path=relativeUri(c.uri);let record=ed.models.get(path);
      if(!record){const item=await host.api('/file?path='+encodeURIComponent(path));ed.open(item,{activate:false});record=ed.models.get(path);host.refreshFileViews?.();}
      const model=record.model;
      for(const e of c.edits){const r=mr(e.range);if(typeof e.newText!=='string'||!m.Range.equalsRange(r,model.validateRange(r)))throw Error('La extensión devolvió una edición inválida.');edits.push({resource:model.uri,versionId:model.getVersionId(),textEdit:{range:r,text:e.newText}});}
    }
    if(source.isDisposed()||source.getVersionId()!==version)throw Error('El archivo cambió. Solicita de nuevo las acciones.');
    return {edits};
  };
  const convertAction=async(a,model,version)=>({title:a.title,kind:typeof a.kind==='string'?a.kind:a.kind?.value,isPreferred:a.isPreferred,disabled:a.disabled?.reason,
    edit:a.edit?await workspaceEdit(a.edit,model,version):undefined,
    command:a.command?{id:'lumen.extension.command',title:a.title,arguments:[ext.id+':'+(typeof a.command==='string'?a.command:a.command.command),a.arguments||a.command.arguments||[]]}:undefined,
    _lumenAction:a._lumenAction,_model:model,_version:version});
  if(p.kind==='actions')return m.languages.registerCodeActionProvider(p.language,{
    provideCodeActions:async(model,r,context)=>{
      const version=model.getVersionId(),diagnostics=(context.markers||[]).map(d=>({range:range(d),message:d.message,severity:({8:0,4:1,2:2,1:3})[d.severity],code:d.code,source:d.source}));
      const items=await checked(model,'actions',{range:range(r),context:{diagnostics,only:context.only,triggerKind:context.trigger===m.languages.CodeActionTriggerType.Auto?2:1}});
      return {actions:await Promise.all(items.map(a=>convertAction(a,model,version))),dispose(){}};
    },
    resolveCodeAction:async action=>{
      if(!action._lumenAction)return action;
      if(action._model.isDisposed()||action._model.getVersionId()!==action._version)throw Error('El archivo cambió. Solicita de nuevo las acciones.');
      const data=await host.platform.api('/extensions/runtime/request',{id:ext.id,method:'resolveAction',action:action._lumenAction,document:{path:ed.pathFor(action._model),text:action._model.getValue(),language:p.language}});
      return convertAction(data.action,action._model,action._version);
    }
  });
  if(p.kind==='rangeFormat')return m.languages.registerDocumentRangeFormattingEditProvider(p.language,{provideDocumentRangeFormattingEdits:async(model,r,options)=>textEdits(await checked(model,'rangeFormat',{range:range(r),options}))});
  if(p.kind==='onTypeFormat')return m.languages.registerOnTypeFormattingEditProvider(p.language,{autoFormatTriggerCharacters:p.triggers,provideOnTypeFormattingEdits:async(model,position,character,options)=>textEdits(await checked(model,'onTypeFormat',{position:pos(position),character,options}))});
  if(p.kind==='highlights')return m.languages.registerDocumentHighlightProvider(p.language,{provideDocumentHighlights:async(model,position)=>(await checked(model,'highlights',{position:pos(position)})).map(h=>({range:mr(h.range),kind:(h.kind??0)+1}))});
  if(p.kind==='selection')return m.languages.registerSelectionRangeProvider(p.language,{provideSelectionRanges:async(model,positions)=>(await checked(model,'selection',{positions:positions.map(pos)})).map(s=>{const ranges=[];for(let current=s;current;current=current.parent)ranges.push({range:mr(current.range)});return ranges;})});
  if(p.kind==='colors')return m.languages.registerColorProvider(p.language,{
    provideDocumentColors:async model=>(await checked(model,'colors')).map(c=>({color:c.color,range:mr(c.range)})),
    provideColorPresentations:async(model,c)=>(await checked(model,'colorPresentation',{range:range(c.range),color:c.color})).map(c=>({...c,textEdit:c.textEdit?textEdits([c.textEdit])[0]:undefined,additionalTextEdits:c.additionalTextEdits?textEdits(c.additionalTextEdits):undefined}))
  });
  return null;
}
