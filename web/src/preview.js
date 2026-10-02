import {icon,escapeHTML as esc} from './icons.js';
import {languageFor} from './editor.js';
const $=s=>document.querySelector(s);

export function installPreview(host){return new Preview(host);}
class Preview{
  constructor(host){
    this.host=host;this.grouped=true;this.group=null;this.providers=[];
    const group=document.createElement('button');group.className='icon-button';group.dataset.action='group-tabs';group.title='Agrupar pestañas por carpeta';group.setAttribute('aria-label',group.title);group.innerHTML=icon('folder');$('.new-tab').after(group);
    this.groups=document.createElement('div');this.groups.className='file-groups';this.groups.setAttribute('aria-label','Grupos de archivos');$('#file-tabs').before(this.groups);
    this.drop=document.createElement('button');this.drop.className='window-drop-target';this.drop.hidden=true;this.drop.innerHTML=icon('plus')+' Soltar en nueva ventana';$('.editor-tabbar').append(this.drop);
    const live=document.createElement('div');live.className='ai-live-control';live.innerHTML='<small>Preguntar no modifica tu archivo.</small><button type="button" id="ai-edit-file" class="secondary-button">Editar archivo…</button>';$('#ai-form').before(live);
    $('#ai-edit-file').onclick=()=>this.safe(()=>host.platform.sendAI($('#ai-input').value,{edit:true}));
    this.context=document.createElement('small');this.context.className='ai-current-document';live.before(this.context);
    const assistantScroll=document.createElement('div');assistantScroll.className='assistant-scroll';$('#assistant-body').prepend(assistantScroll);
    for(const selector of ['#assistant-hero','#ai-actions','.assistant-lantern','#chat-messages']){const item=$(selector);if(item)assistantScroll.append(item);}
    $('#file-tabs').addEventListener('dragstart',e=>{const path=e.target.closest('[data-tab]')?.dataset.tab;if(!path)return;const r=host.editor.models.get(path);this.dragged=path;e.dataTransfer.setData('application/x-lumen-document',JSON.stringify({path,workspace:host.service().workspace,content:r.model?.getValue()??r.value}));this.drop.hidden=false;});
    document.addEventListener('dragend',()=>{this.drop.hidden=true;this.dragged=null;});
    this.drop.ondragover=e=>{e.preventDefault();e.dataTransfer.dropEffect='move';};
    this.drop.ondrop=e=>{e.preventDefault();e.stopPropagation();this.safe(async()=>{const data=JSON.parse(e.dataTransfer.getData('application/x-lumen-document'));await this.newWindow(data.path,data.content);});this.drop.hidden=true;};
    $('#editor-panel').addEventListener('dragover',e=>{if(e.dataTransfer.types.includes('application/x-lumen-document'))e.preventDefault();});
    $('#editor-panel').addEventListener('drop',e=>{if(this.dragged||!e.dataTransfer.types.includes('application/x-lumen-document'))return;e.preventDefault();this.safe(async()=>{const data=JSON.parse(e.dataTransfer.getData('application/x-lumen-document'));if(data.workspace!==host.service().workspace)throw Error('Abre una ventana de este proyecto para recibir sus archivos.');if(host.editor.models.has(data.path)&&host.editor.isDirty(data.path)&&!await host.confirmDialog('Recibir archivo','El búfer de destino tiene cambios. ¿Reemplazarlo por el de la otra ventana?','Reemplazar búfer'))return;await host.openFile(data.path);if(typeof data.content==='string'&&data.content.length<=2_000_000)host.editor.insertText(data.content,true);});});
    $('#file-tabs').addEventListener('contextmenu',e=>{const path=e.target.closest('[data-tab]')?.dataset.tab;if(!path)return;e.preventDefault();
      const paths=[...host.editor.models.keys()],close=async names=>{for(const p of names){await host.closeFile(p);if(host.editor.models.has(p))break;}};
      host.showMenu(e.target.closest('[data-tab]'),[
        {label:'Guardar',icon:'check',shortcut:'Ctrl S',run:()=>host.saveFile(path)},
        {label:'Guardar como…',icon:'file',shortcut:'Ctrl Shift O',run:async()=>{await host.openFile(path);await this.saveAs();}},
        {label:'Mostrar en el explorador',icon:'folder',run:async()=>{await host.openFile(path);host.dock.show('project');host.revealFile(path);}},
        {label:'Copiar ruta relativa',icon:'copy',run:()=>navigator.clipboard.writeText(path)},
        {label:'Copiar ruta',icon:'copy',run:()=>navigator.clipboard.writeText(host.service().workspace.replaceAll('\\','/')+'/'+path)},
        {separator:true},
        {label:'Abrir en otra ventana',icon:'plus',run:()=>this.newWindow(path)},
        {label:this.grouped?'Mostrar pestañas sin grupos':'Agrupar por carpeta',icon:'folder',run:()=>this.toggleGroups()},
        {label:'Ejecutar con Lantern',icon:'play',run:async()=>{await host.openFile(path);await host.studio.lantern.action('start');}},
        {separator:true},
        {label:'Cerrar',icon:'close',run:()=>close([path])},
        {label:'Cerrar los demás',icon:'close',run:()=>close(paths.filter(p=>p!==path))},
        {label:'Cerrar a la derecha',icon:'close',run:()=>close(paths.slice(paths.indexOf(path)+1))},
        {label:'Cerrar guardados',icon:'check',run:()=>close(paths.filter(p=>!host.editor.isDirty(p)))},
        {label:'Cerrar todos',icon:'close',run:()=>close(paths)},
      ],path.split('/').at(-1));});
    document.addEventListener('click',e=>{const exec=e.target.closest('[data-extension-execute]');if(exec)this.safe(()=>this.startExtension(exec.dataset.extensionExecute));});
    this.extensionObserver=new MutationObserver(()=>this.extensionButtons());this.extensionObserver.observe(document.body,{childList:true,subtree:true});
    const load=host.platform.loadContributions.bind(host.platform);host.platform.loadContributions=async(...args)=>{const result=await load(...args);const status=await host.platform.api('/extensions/runtime');this.registerExtensions(status.hosts);return result;};
    this.activeChanged();this.renderGroups();this.languageFeatures();
  }
  safe(fn){return Promise.resolve().then(fn).catch(e=>this.host.notify(e.message,'error',7000));}
  activeChanged(){this.context.textContent='Contexto actual · '+(this.host.editor.current||'Abre un archivo para adjuntarlo');this.host.studio.lantern.follow();this.renderGroups();}
  toggleGroups(){this.grouped=!this.grouped;this.renderGroups();}
  renderGroups(){
    const ed=this.host.editor,sets=new Map();for(const path of ed.models.keys()){const key=path.includes('/')?path.slice(0,path.lastIndexOf('/')):'Proyecto';if(!sets.has(key))sets.set(key,[]);sets.get(key).push(path);}
    const current=ed.current?.includes('/')?ed.current.slice(0,ed.current.lastIndexOf('/')):'Proyecto';
    this.groups.hidden=!this.grouped||ed.models.size<2;
    const signature=JSON.stringify([this.grouped,ed.current,[...ed.models.keys()]]);
    if(signature!==this.groupSignature){this.groupSignature=signature;this.groups.innerHTML=[...sets].map(([name,paths])=>`<button class="file-group ${name===current?'active':''}" data-file-group="${esc(name)}" aria-haspopup="menu">${icon('folder')}<span>${esc(name.split('/').at(-1))}</span><small>${paths.length}</small>${icon('chevron-down')}</button>`).join('');this.groups.querySelectorAll('button').forEach(b=>b.onclick=()=>this.host.showMenu(b,sets.get(b.dataset.fileGroup).map(path=>({label:path.split('/').at(-1)+(ed.isDirty(path)?' •':''),icon:'file',run:()=>this.host.openFile(path)})),b.dataset.fileGroup));}
    $('#file-tabs').classList.toggle('is-grouped',this.grouped&&ed.models.size>1);
  }
  async newWindow(path='',content){
    if(path&&content===undefined){const r=this.host.editor.models.get(path);content=r?.model?.getValue()??r?.value;}
    if(window.pywebview?.api?.new_window)return window.pywebview.api.new_window(path,content??null);
    const url=new URL(location.href);url.searchParams.set('file',path);const opened=window.open(url,'_blank');if(!opened)throw Error('Permite abrir ventanas en el navegador o utiliza Lumen Desktop.');
  }
  async saveAs(){
    const ed=this.host.editor;if(!ed.current)return;
    if(window.pywebview?.api?.save_as){const result=await window.pywebview.api.save_as(ed.current,ed.getValue());if(!result)return;await this.host.refreshTree();if(result.relative){const fresh=await this.host.api('/file?path='+encodeURIComponent(result.relative));const existing=ed.models.get(result.relative);if(existing){existing.model?.setValue(fresh.content);existing.value=fresh.content;ed.markSaved(fresh);}await this.host.openFile(result.relative);}this.host.notify('Archivo guardado en '+result.path);return;}
    this.host.modal('Guardar como',`<form id="save-as-form"><label>Ruta dentro del proyecto<input id="save-as-path" value="${esc(ed.current)}" required></label><div class="modal-actions"><button class="primary-button">Guardar copia</button></div></form>`);
    $('#save-as-form').onsubmit=e=>{e.preventDefault();this.safe(async()=>{const path=$('#save-as-path').value.trim();await this.host.api('/save',{path,content:ed.getValue(),create:true});this.host.closeModal();await this.host.refreshTree();await this.host.openFile(path);});};
  }
  async downloads(){
    this.host.platform.openPage('downloads',`<section class="downloads-page"><span class="eyebrow">HERRAMIENTAS · PREVIEW</span><h1>Espacio para tus compiladores.</h1><p>Hasta 500 GB por archivo. Transferencia directa a disco, pausa y reanudación cuando el servidor lo permite.</p><form id="download-form"><label>URL HTTPS del distribuidor<input id="download-url" type="url" placeholder="https://…" required></label><label>Nombre del archivo<input id="download-name" placeholder="compilador.zip" required></label><label>SHA-256 del distribuidor · opcional<input id="download-sha" pattern="[a-fA-F0-9]{64}" placeholder="Verificación del archivo"></label><button class="primary-button">${icon('download')}Descargar</button></form><p class="muted-copy">Los paquetes se guardan sin ejecutarlos. Después de instalarlos, configura su ruta en Lenguajes y herramientas.</p><small id="download-location"></small><div id="download-list"></div></section>`);
    $('#download-form').onsubmit=e=>{e.preventDefault();this.safe(async()=>{await this.host.platform.api('/downloads/start',{url:$('#download-url').value,name:$('#download-name').value,sha256:$('#download-sha').value});await this.renderDownloads();});};
    await this.renderDownloads();
  }
  async renderDownloads(){
    clearTimeout(this.downloadTimer);if(!$('#download-list'))return;
    const data=await this.host.platform.api('/downloads');if(!$('#download-list'))return;
    const size=n=>(n/1e9).toLocaleString('es',{maximumFractionDigits:3})+' GB';$('#download-location').textContent=data.directory+' · '+size(data.free)+' libres';
    $('#download-list').innerHTML=data.items.map(x=>`<article class="download-item"><strong>${esc(x.name)}</strong><span>${esc({downloading:'Descargando',paused:'Pausada',verifying:'Verificando',complete:'Completada',error:'Error'}[x.status])}</span><progress max="${x.total||1}" value="${x.total?x.bytes:0}"></progress><small>${size(x.bytes)}${x.total?' / '+size(x.total):''} · ${(x.speed/1e6).toFixed(1)} MB/s</small>${x.error?`<p role="alert">${esc(x.error)}</p>`:''}${x.status==='complete'?`<code>${esc(x.path)}</code>`:`<button class="secondary-button" data-download="${x.id}" data-op="${['downloading','verifying'].includes(x.status)?'pause':'resume'}">${['downloading','verifying'].includes(x.status)?'Pausar':'Reanudar'}</button>`}</article>`).join('')||'<p>No hay descargas.</p>';
    document.querySelectorAll('[data-download]').forEach(b=>b.onclick=()=>this.safe(async()=>{await this.host.platform.api('/downloads/'+b.dataset.op,{id:b.dataset.download});await this.renderDownloads();}));this.downloadTimer=setTimeout(()=>this.safe(()=>this.renderDownloads()),1200);
  }
  extensionButtons(){
    document.querySelectorAll('[data-extension-toggle]').forEach(toggle=>{const card=toggle.closest('.extension-card');if(card.querySelector('[data-extension-execute]'))return;const item=this.host.platform.extensionItems?.find(x=>x.id===toggle.dataset.extensionToggle);if(!item?.supported?.includes('runtime'))return;const b=document.createElement('button');b.className='secondary-button small-button';b.dataset.extensionExecute=item.id;b.textContent=this.runtimeHosts?.some(x=>x.id===item.id&&x.running)?'Detener motor':'Iniciar motor';toggle.before(b);});
    if($('.tools-content')&&!$('#download-tools-link')){const b=document.createElement('button');b.id='download-tools-link';b.className='secondary-button';b.textContent='Descargar compilador · hasta 500 GB';b.onclick=()=>this.safe(()=>this.downloads());$('.tools-content .section-heading').append(b);}
  }
  async startExtension(id){
    if(this.runtimeHosts?.some(x=>x.id===id&&x.running)){const stopped=await this.host.platform.api('/extensions/runtime/stop',{id});this.registerExtensions(stopped.hosts);return;}
    if(!await this.host.platform.host.ensureTrust())return;
    if(!await this.host.confirmDialog('Ejecutar '+id,'Este plugin ejecutará código Node.js con tus permisos de usuario. Tendrá acceso al equipo y a los documentos que consultes. El proceso separado evita que bloquee la interfaz; no es un aislamiento de seguridad.','Autorizar motor'))return;
    const data=await this.host.platform.api('/extensions/runtime/start',{id,consent:true});this.registerExtensions(data.hosts);this.host.notify('Motor iniciado. Comandos disponibles en la paleta.');
  }
  registerExtensions(hosts){
    for(const p of this.providers)p.dispose?.();this.providers=[];this.runtimeHosts=hosts;document.querySelectorAll('[data-extension-execute]').forEach(b=>b.textContent=hosts.some(x=>x.id===b.dataset.extensionExecute&&x.running)?'Detener motor':'Iniciar motor');const platform=this.host.platform,m=window.monaco,ed=this.host.editor;
    const doc=model=>{const path=[...ed.models].find(([,r])=>r.model===model)?.[0]||ed.current;return {path,text:model?.getValue()??ed.getValue(),language:languageFor(path)};};
    const relativeUri=value=>{const raw=typeof value==='string'?value:(value?.fsPath||value?.external||value?.path||'');const absolute=decodeURIComponent(raw.replace(/^file:\/\//,'')).replaceAll('\\','/').replace(/^\/(?:([A-Za-z]:))/, '$1');const root=this.host.service().workspace.replaceAll('\\','/').replace(/\/$/,'');if(absolute.toLowerCase().startsWith(root.toLowerCase()+'/'))return absolute.slice(root.length+1);if(/^(?:[A-Za-z]:|\/)/.test(absolute))throw Error('La definición está fuera del proyecto abierto.');return absolute;};
    const call=(ext,kind,model,extra={})=>platform.api('/extensions/runtime/request',{id:ext.id,method:'provide',kind,document:doc(model),...extra}).then(x=>x.items);
    const mr=r=>r?new m.Range(r.start.line+1,r.start.character+1,r.end.line+1,r.end.character+1):undefined;
    if(!this.extensionCommandBridge)this.extensionCommandBridge=m?.editor.registerCommand('lumen.extension.command',(_,id,args)=>this.safe(()=>platform.pluginCommand(id,args)));
    this.runtimeCommands=new Map();
    for(const ext of hosts.filter(x=>x.running)){
      for(const command of ext.commands)this.runtimeCommands.set(ext.id+':'+command.id,{ext:ext.id,...command});
      if(!m)continue;
      for(const token of ext.tokens||[])this.providers.push(m.languages.setMonarchTokensProvider(token.language,{tokenizer:{root:token.rules.map(r=>[new RegExp(r.pattern,r.flags||''),r.token])}}));
      const contents=value=>(Array.isArray(value)?value:[value]).filter(Boolean).map(c=>typeof c==='string'?{value:c}:{value:c.value||String(c),isTrusted:false});
      for(const p of ext.providers){const language=p.language;
        if(p.kind==='hover')this.providers.push(m.languages.registerHoverProvider(language,{provideHover:async(model,pos)=>{const items=await call(ext,'hover',model,{position:{line:pos.lineNumber-1,character:pos.column-1}});return items.length?{contents:items.flatMap(i=>contents(i.contents)),range:mr(items[0].range)}:null;}}));
        if(p.kind==='format')this.providers.push(m.languages.registerDocumentFormattingEditProvider(language,{provideDocumentFormattingEdits:async model=>(await call(ext,'format',model)).map(e=>({range:mr(e.range),text:e.newText}))}));
        if(p.kind==='semantic'&&p.legend)this.providers.push(m.languages.registerDocumentSemanticTokensProvider(language,{getLegend:()=>p.legend,provideDocumentSemanticTokens:async model=>{const items=await call(ext,'semantic',model);return items.length?{data:new Uint32Array(items[0].data),resultId:items[0].resultId}:null;},releaseDocumentSemanticTokens(){}}));
        if(p.kind==='symbols')this.providers.push(m.languages.registerDocumentSymbolProvider(language,{provideDocumentSymbols:async model=>{const convert=s=>({...s,range:mr(s.range),selectionRange:mr(s.selectionRange||s.range),children:(s.children||[]).map(convert)});return (await call(ext,'symbols',model)).map(convert);}}));
        if(p.kind==='codelens')this.providers.push(m.languages.registerCodeLensProvider(language,{provideCodeLenses:async model=>({lenses:(await call(ext,'codelens',model)).map(c=>({...c,range:mr(c.range),command:c.command?{id:'lumen.extension.command',title:c.command.title,arguments:[ext.id+':'+c.command.command,c.command.arguments||[]]}:undefined})),dispose(){}})}));
        if(p.kind==='diagnostics'){
          let timer,poll,disposed=false;const refresh=()=>{clearTimeout(timer);clearTimeout(poll);timer=setTimeout(async()=>{const model=ed.view.getModel();if(disposed||!model||doc(model).language!==language)return;const version=model.getVersionId(),path=doc(model).path;try{const items=await call(ext,'diagnostics',model);if(!model.isDisposed()&&model.getVersionId()===version){const markers=items.map(d=>{const line=d.startLineNumber||d.line||1,column=d.startColumn||d.column||1;const range=model.validateRange(new m.Range(line,column,d.endLineNumber||d.endLine||line,d.endColumn||column+1));return {...range,message:String(d.message||''),severity:typeof d.severity==='number'?d.severity:({warning:m.MarkerSeverity.Warning,info:m.MarkerSeverity.Info,hint:m.MarkerSeverity.Hint}[d.severity]||m.MarkerSeverity.Error),source:ext.id};});ed.setDiagnostics(path,markers,'plugin-'+ext.id);if(!disposed&&ed.view.getModel()===model)poll=setTimeout(refresh,1800);}}catch(e){this.host.notify(e.message,'error');}},450);};
          const a=ed.view.onDidChangeModelContent(refresh),b=ed.view.onDidChangeModel(refresh);this.providers.push({dispose(){disposed=true;clearTimeout(timer);clearTimeout(poll);a.dispose();b.dispose();for(const [path] of ed.models)ed.setDiagnostics(path,[],'plugin-'+ext.id);}});refresh();
        }
        if(p.kind==='completion')this.providers.push(m.languages.registerCompletionItemProvider(language,{triggerCharacters:p.triggers||[],provideCompletionItems:async(model,pos)=>{const word=model.getWordUntilPosition(pos);const items=await call(ext,'completion',model,{position:{line:pos.lineNumber-1,character:pos.column-1}});return {suggestions:items.map(i=>({...i,insertText:typeof i.insertText==='object'?i.insertText.value:(i.insertText||i.label),insertTextRules:typeof i.insertText==='object'?4:i.insertTextRules,documentation:typeof i.documentation==='object'?{value:i.documentation.value,isTrusted:false}:i.documentation,range:new m.Range(pos.lineNumber,word.startColumn,pos.lineNumber,word.endColumn)}))};}}));
        if(p.kind==='inlay')this.providers.push(m.languages.registerInlayHintsProvider(language,{provideInlayHints:async(model,range)=>({hints:(await call(ext,'inlay',model,{range:{start:{line:range.startLineNumber-1,character:range.startColumn-1},end:{line:range.endLineNumber-1,character:range.endColumn-1}}})).map(h=>({...h,position:{lineNumber:h.position.line+1,column:h.position.character+1}})),dispose(){}})}));
        if(p.kind==='definition')this.providers.push(m.languages.registerDefinitionProvider(language,{provideDefinition:async(model,pos)=>{const items=await call(ext,'definition',model,{position:{line:pos.lineNumber-1,character:pos.column-1}});return items.map(d=>{const path=d.path||(d.uri||d.targetUri?relativeUri(d.uri||d.targetUri):doc(model).path);return {uri:ed.models.get(path)?.model?.uri||m.Uri.parse('file:///'+path),range:mr(d.range||d.targetSelectionRange||d.targetRange)};});}}));
      }
    }
    if(!this.oldPluginCommand)this.oldPluginCommand=platform.pluginCommand.bind(platform);
    platform.pluginCommand=async(id,args=[])=>{
      const command=this.runtimeCommands.get(id);if(!command)return this.oldPluginCommand(id);
      const snapshot={path:ed.current,text:ed.getValue()},model=ed.models.get(ed.current)?.model;
      const data=await platform.api('/extensions/runtime/request',{id:command.ext,method:'command',command:command.id,arguments:args,document:doc()});
      const edits=[];
      for(const e of data.effects||[]){
        if(e.message)this.host.notify(e.message);
        if(e.clipboard!==undefined)await navigator.clipboard.writeText(String(e.clipboard));
        if(e.open)await this.host.openFile(relativeUri(e.open));
        if(e.url){const u=new URL(e.url);if(!['https:','http:'].includes(u.protocol))throw Error('El enlace de la extensión debe usar HTTPS o HTTP.');window.open(u.href,'_blank','noopener,noreferrer');}
        if(e.output!==undefined)this.host.modal(e.title||'Salida de extensión',`<pre class="extension-output">${esc(e.output)}</pre>`);
        if(e.terminal!==undefined){
          const profiles=await platform.api('/terminals/profiles');const profile=profiles.profiles.find(p=>p.id===platform.prefs['terminal.defaultProfile'])||profiles.profiles[0];
          if(!profile)throw Error('No hay un perfil de terminal disponible para la extensión.');
          const terminal=await platform.openTerminal(profile.id);if(terminal)await platform.terminals.get(terminal.id).input.write(String(e.terminal)+'\r');
        }
        if(e.edits){if(relativeUri(e.path)!==snapshot.path)throw Error('Esta propuesta modifica varios archivos. La revisión del plugin admite el archivo activo en esta preview.');edits.push(...e.edits);}
      }
      if(edits.length){
        if(!model||model.isDisposed()||model.getValue()!==snapshot.text)throw Error('El archivo cambió durante la propuesta de la extensión.');
        const changes=edits.map(e=>{const range=mr(e.range);const valid=model.validateRange(range);if(!m.Range.equalsRange(range,valid))throw Error('La extensión devolvió un rango de edición inválido.');return {start:model.getOffsetAt(range.getStartPosition()),end:model.getOffsetAt(range.getEndPosition()),text:e.newText};}).sort((a,b)=>b.start-a.start);
        let text=snapshot.text,last=text.length;for(const change of changes){if(change.end>last)throw Error('La extensión devolvió ediciones solapadas.');text=text.slice(0,change.start)+change.text+text.slice(change.end);last=change.start;}
        return platform.reviewCode(text,snapshot);
      }
      if(typeof data.result?.text==='string')return platform.reviewCode(data.result.text,snapshot);if(typeof data.result==='string')this.host.notify(data.result);
    };
    platform.host.setPluginCommands([...platform.extensionContributions.commands,...[...this.runtimeCommands].map(([id,c])=>({id,title:c.title}))]);
  }
  languageFeatures(){
    const m=window.monaco;if(!m)return;
    this.editorOpener=m.editor.registerEditorOpener({openCodeEditor:async(source,resource,selection)=>{if(resource.scheme!=='file')return false;const ed=this.host.editor,path=[...ed.models].find(([,r])=>r.model?.uri.toString()===resource.toString())?.[0]||resource.path.replace(/^\/+/, '');await this.host.openFile(path);if(selection?.startLineNumber){ed.view.setSelection(selection);ed.view.revealRangeInCenter(selection);}else if(selection?.lineNumber){ed.view.setPosition(selection);ed.view.revealPositionInCenter(selection);}ed.view.focus();return true;}});
    for(const defaults of [m.languages.typescript?.typescriptDefaults,m.languages.typescript?.javascriptDefaults])defaults?.setInlayHintsOptions?.({includeInlayParameterNameHints:'all',includeInlayVariableTypeHints:true,includeInlayFunctionLikeReturnTypeHints:true,includeInlayPropertyDeclarationTypeHints:true});
    this.host.editor.view.updateOptions({inlayHints:{enabled:'on'},'semanticHighlighting.enabled':true});
    this.host.editor.view.addAction({id:'lumen.goToDefinition',label:'Ir a definición · F12',keybindings:[m.KeyCode.F12],run:ed=>ed.trigger('lumen','editor.action.revealDefinition',{})});
    for(const [id,label,run] of [
      ['lantern','Lantern: ejecutar este búfer',()=>this.host.studio.lantern.action('start')],
      ['save','Guardar archivo',()=>this.host.saveFile(this.host.editor.current)],
      ['saveAs','Guardar como…',()=>this.saveAs()],
      ['newWindow','Abrir en otra ventana',()=>this.newWindow(this.host.editor.current)],
      ['explain','Preguntar a la IA sobre este código',()=>{this.host.dock.show('assistant');$('#ai-input').value='Explica este código y qué mejorarías.';$('#ai-input').focus();}],
    ])this.host.editor.view.addAction({id:'lumen.context.'+id,label,contextMenuGroupId:'9_lumen',run:()=>this.safe(run)});
    const requested=new URLSearchParams(location.search).get('file');if(requested)this.safe(()=>this.host.openFile(requested));
  }
}
