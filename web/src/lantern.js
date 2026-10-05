import {icon,escapeHTML as esc} from './icons.js';
import {languageFor} from './editor.js';
const $=s=>document.querySelector(s);
const labels={idle:'En espera',stopped:'Detenido',preparing:'Preparando',running:'En ejecución',watching:'Escuchando cambios',debouncing:'Esperando estabilidad',waiting:'Esperando código válido',error:'Revisa los errores'};

/** Live follows the active buffer; Lens decorations never enter the source model. */
export class LanternView{
  constructor(studio){this.studio=studio;this.host=studio.host;this.state={active:false,status:'idle',revision:0};this.disposed=false;this.previewRevision=-1;}
  init(){
    const card=document.createElement('section');card.className='lantern-monitor';card.id='lantern-monitor';card.setAttribute('aria-label','Monitor Lantern');
    card.innerHTML=`<header><span>${icon('sparkles')} LANTERN</span><button class="icon-button" data-lantern="hide" aria-label="Ocultar monitor Lantern">${icon('close')}</button></header><button class="lantern-open" data-lantern="open"><span class="lantern-led"></span><strong data-lantern-status>En espera</strong>${icon('arrow-up-right')}</button><small data-lantern-path>Continuidad para tu código</small><p data-lantern-summary>Ejecuta, edita y revisa cada cambio.</p><div class="lantern-monitor-actions"><button class="secondary-button" data-lantern="start">${icon('play')}Iniciar</button><button class="text-button" data-lantern="stop" disabled>Detener</button></div>`;
    $('#sidebar-content').after(card);
    this.click=e=>{const action=e.target.closest('[data-lantern]')?.dataset.lantern;if(action)this.studio.safe(()=>this.action(action));};document.addEventListener('click',this.click);
    this.host.platform.lantern=this;this.render();this.poll();
  }
  async action(action){
    if(action==='detach'){await this.studio.desktop.detach('lantern',this.state.path||this.host.editor.current||'');return;}
    if(action==='hide'||action==='show'){await this.host.platform.savePreference('appearance.lanternMonitor',action==='show');this.render();return;}
    if(action==='open'){this.openInline();return;}
    if(action==='close-inline'){$('#lantern-inline')?.remove();return;}
    if(action==='memory'){this.host.modal('Memoria de Lantern',`<p>${esc(this.state.memoryHelp||'')}</p><p>El programa guarda su estado en puntos seguros y lo recupera tras recompilar. C/C++ dispone de SDK con esquema, checksum y migración; nC usa un contrato JSON nativo.</p><button class="secondary-button" data-lantern="support">Ejemplo de continuidad</button>${this.state.nativeMemory?`<pre>${esc(JSON.stringify(this.state.nativeMemory,null,2))}</pre>`:''}<pre>${esc(JSON.stringify(this.state.memory||{},null,2))}</pre><h3>Revisiones anteriores</h3>${(this.state.history||[]).slice().reverse().map(h=>`<details><summary>Revisión ${h.revision} · ${esc(h.path)} · salida ${h.code??'detenida'}</summary><pre>${esc(h.output)}</pre></details>`).join('')||'<p>Se guardará la primera revisión al actualizar o detener.</p>'}`);return;}
    if(action==='support'){
      const language=languageFor(this.host.editor.current),supported=['c','cpp','nc'].includes(language);
      if(!supported)throw Error('Abre un archivo C, C++ o nC para crear su ejemplo de continuidad.');
      const template=await this.host.api('/platform/lantern/template?language='+language);
      this.host.modal('Continuidad nativa · '+language,`<p>Este ejemplo crea un archivo nuevo con estado persistente. Adapta sus campos y puntos de guardado a tu programa.</p><details><summary>Guía de integración</summary><pre>${esc(template.guide)}</pre></details><pre>${esc(template.content)}</pre><form id="lantern-template"><label>Nuevo archivo<input id="lantern-template-path" required value="${esc(template.name)}"></label><button class="primary-button">Crear ejemplo</button></form>`);
      $('#lantern-template').onsubmit=e=>{e.preventDefault();this.studio.safe(async()=>{const path=$('#lantern-template-path').value;await this.host.api('/save',{path,content:template.content,create:true});this.host.closeModal();await this.host.refreshTree();await this.host.openFile(path);});};return;
    }
    if(action==='analyze'){
      this.host.dock.show('assistant');const input=$('#ai-input');
      input.value=`Analiza esta sesión Lantern y el código seleccionado. Explica los errores y propón una corrección revisable.\nArchivo: ${this.state.path||this.host.editor.current||''}\nEstado: ${labels[this.state.status]} · revisión ${this.state.revision}\n${(this.state.output||'').slice(-6500)}`;input.focus();return;
    }
    if(action==='start'){
      if(!await this.host.ensureTrust())return;
      const path=this.host.editor.current;
      if(!path)throw new Error('Abre un archivo antes de iniciar Lantern.');
      this.clearLens();this.submitted=this.capture();
      const buffer=this.submitted;
      this.enabled=true;await this.control(()=>this.host.api('/platform/lantern/start',buffer));
      if(this.host.editor.current===path&&this.host.editor.getValue()!==buffer.content)this.changed();
      this.openInline();
    }else {if(action!=='restart'){this.enabled=false;clearTimeout(this.followTimer);clearTimeout(this.bufferTimer);}await this.control(()=>this.host.api('/platform/lantern/'+(action==='restart'?'restart':'stop'),{}));}
    this.render();this.renderLens();
  }
  async follow(){
    if(new URLSearchParams(location.search).has('panel'))return;
    this.clearLens();clearTimeout(this.followTimer);this.followTimer=setTimeout(()=>this.studio.safe(async()=>{
      const path=this.host.editor.current;if(this.enabled===false||(!this.state.active&&!this.enabled))return;
      if(!path){await this.control(()=>this.host.api('/platform/lantern/stop',{}));this.render();return;}
      if(path===this.state.path)return;
      this.clearLens();this.submitted=this.capture();
      const buffer=this.submitted;await this.control(()=>this.host.api('/platform/lantern/start',buffer));this.render();
    }),250);
  }
  async control(operation){
    const epoch=this.controlEpoch=(this.controlEpoch||0)+1;this.controlPending=true;
    const task=(this.controlQueue||Promise.resolve()).catch(()=>{}).then(async()=>{if(epoch!==this.controlEpoch)return;const state=await operation();if(epoch===this.controlEpoch)this.state=state;});
    this.controlQueue=task;try{await task;}finally{if(epoch===this.controlEpoch)this.controlPending=false;}
  }
  openInline(){
    this.studio.enter();if(this.host.platform.page)this.host.platform.closePage();
    if(!$('#lantern-inline')){
      const panel=document.createElement('section');panel.id='lantern-inline';panel.className='lantern-workbench lantern-inline';
      panel.innerHTML=`<header><strong>${icon('sparkles')} Lantern</strong><span class="lantern-led"></span><span data-lantern-status></span><small data-lantern-path></small><button class="text-button" data-lantern="memory">Memoria e historial</button><button class="icon-button" data-lantern="restart" title="Aplicar de nuevo">${icon('refresh')}</button><button class="icon-button" data-lantern="stop" title="Detener">${icon('stop')}</button><button class="icon-button" data-lantern="detach" title="${new URLSearchParams(location.search).has('panel')?'Volver a Zénit':'Desacoplar Lantern en ventana'}" aria-label="Desacoplar o acoplar Lantern">${icon('arrow-up-right')}</button><button class="icon-button" data-lantern="close-inline" title="Ocultar monitor">${icon('close')}</button></header><div class="lantern-preview" hidden></div><pre class="lantern-output" aria-label="Salida de Lantern en el editor"></pre><form class="lantern-inline-input"><input aria-label="Entrada de Lantern" placeholder="Entrada del programa · Enter" autocomplete="off"><button class="icon-button">${icon('send')}</button><button type="button" class="text-button" data-lantern="analyze">Analizar con IA</button></form>`;
      $('#editor-panel').append(panel);panel.querySelector('form').onsubmit=e=>{e.preventDefault();this.studio.safe(async()=>{const input=panel.querySelector('input');if(!this.state.job)throw Error('No hay proceso esperando entrada.');await this.host.api('/task-input',{id:this.state.job,text:input.value+'\n'});input.value='';});};
    }
    this.render();
    if(this.studio.desktop?.auxiliary.has('lantern'))$('#lantern-inline')?.setAttribute('hidden','');
  }
  mountDebug(){
    const card=document.createElement('section');card.className='lantern-workbench';card.id='lantern-workbench';
    card.innerHTML=`<header><div><span class="eyebrow">CONTINUIDAD</span><h2>${icon('sparkles')}Lantern <span class="lantern-led"></span><small data-lantern-status></small></h2><p>Revisiones con checkpoints e historial por archivo. El monitor sigue al editor sin abandonar tu código.</p></div><div class="lantern-toolbar"><button class="primary-button" data-lantern="start">${icon('play')}Iniciar Lantern</button><button class="secondary-button" data-lantern="restart">${icon('refresh')}Reiniciar</button><button class="secondary-button" data-lantern="stop">${icon('stop')}Detener</button></div></header><div class="lantern-session"><span data-lantern-path></span><span data-lantern-summary></span><button class="text-button" data-lantern="analyze">${icon('sparkles')}Analizar con IA</button><label class="lantern-autosave"><input id="lantern-lens" type="checkbox" ${this.host.platform.prefs['lantern.lens']!==false?'checked':''}>Lens · resultados junto al código</label><small>Live ejecuta el buffer. Guardar es tu decisión.</small></div><div class="lantern-preview" hidden></div><pre class="lantern-output" aria-label="Salida de Lantern"></pre><form id="lantern-input-form"><span>›</span><input id="lantern-input" placeholder="Entrada del programa · Enter para enviar" autocomplete="off"><button class="icon-button" aria-label="Enviar entrada">${icon('arrow-right')}</button></form>`;
    $('.debug-controls').before(card);
    $('#lantern-lens').onchange=e=>this.studio.safe(async()=>{await this.host.platform.savePreference('lantern.lens',e.target.checked);this.renderLens();});
    $('#lantern-input-form').onsubmit=e=>{e.preventDefault();this.studio.safe(async()=>{if(!this.state.job)throw new Error('No hay un programa esperando entrada.');await this.host.api('/task-input',{id:this.state.job,text:$('#lantern-input').value+'\n'});$('#lantern-input').value='';});};
    this.previewRevision=-1;this.render();
  }
  render(){
    const s=this.state;$('#lantern-monitor')?.toggleAttribute('hidden',!this.host.platform.prefs['appearance.lanternMonitor']);
    for(const root of document.querySelectorAll('.lantern-monitor,.lantern-workbench')){
      root.dataset.status=s.status;
      root.querySelectorAll('[data-lantern-status]').forEach(x=>x.textContent=labels[s.status]||s.status);
      root.querySelectorAll('[data-lantern-path]').forEach(x=>{x.textContent=s.path||'Continuidad para tu código';x.title=s.path||'';});
      root.querySelectorAll('[data-lantern-summary]').forEach(x=>{x.title=s.error||'';x.textContent=s.active?`Revisión ${s.revision} · ${s.diagnostics?.length||0} diagnósticos${s.code!=null?' · salida '+s.code:''}${s.error?' · '+s.error:''}`:'Ejecuta, edita y revisa cada cambio.';});
      root.querySelectorAll('[data-lantern=stop],[data-lantern=restart]').forEach(x=>x.disabled=!s.active);
      root.querySelectorAll('[data-lantern=start]').forEach(x=>x.disabled=s.active);
      const output=root.querySelector('.lantern-output');if(output&&output.textContent!==s.output){const bottom=output.scrollHeight-output.scrollTop-output.clientHeight<40;output.textContent=s.output||'Inicia Lantern para seguir la ejecución y los errores aquí.';if(bottom)output.scrollTop=output.scrollHeight;}
      const preview=root.querySelector('.lantern-preview');if(preview){preview.hidden=!s.preview;if(s.preview&&preview.dataset.revision!==String(s.revision)){preview.replaceChildren(this.frame(s.preview));preview.dataset.revision=String(s.revision);}}
    }
  }
  capture(){const ed=this.host.editor;return {path:ed.current,content:ed.getValue(),version:ed.models.get(ed.current)?.model?.getVersionId()??(this.bufferVersion=(this.bufferVersion||0)+1)};}
  changed(){
    if(new URLSearchParams(location.search).has('panel'))return;
    if(!this.state.active)return;this.clearLens();clearTimeout(this.bufferTimer);
    const buffer=this.capture();if(!buffer.path)return;
    this.state={...this.state,status:'debouncing',lens:[],diagnostics:[]};this.render();
    // Send revisions in order; the backend handles syntax gating and debounce.
    this.bufferTimer=setTimeout(()=>{this.bufferQueue=(this.bufferQueue||Promise.resolve()).catch(()=>{}).then(async()=>{
      if(!this.state.active||this.host.editor.current!==buffer.path||this.host.editor.getValue()!==buffer.content)return;
      this.submitted=buffer;
      const epoch=this.controlEpoch,result=await this.host.api('/platform/lantern/buffer',buffer);
      if(!result.ignored&&!this.controlPending&&epoch===this.controlEpoch&&this.host.editor.current===buffer.path&&this.host.editor.getValue()===buffer.content){this.state=result;this.render();}
    }).catch(e=>this.host.notify(e.message,'error'));},80);
  }
  clearLens(){
    if(this.lensModel&&!this.lensModel.isDisposed())this.lensModel.deltaDecorations(this.lensIds||[],[]);
    this.lensModel=null;this.lensIds=[];this.lensKey='';
  }
  matchesBuffer(){const ed=this.host.editor;return this.state.active&&this.state.path===ed.current&&this.submitted?.path===ed.current&&this.submitted.content===ed.getValue()&&this.state.bufferVersion===this.submitted.version;}
  renderLens(){
    const ed=this.host.editor,model=ed.models.get(ed.current)?.model;
    if(!this.matchesBuffer()||!model||!window.monaco||this.host.platform.prefs['lantern.lens']===false){this.clearLens();return;}
    const values=[...(this.state.lens||[]),...(this.state.diagnostics||[]).map(x=>({line:x.startLineNumber,value:x.message,error:true}))];
    const key=JSON.stringify(values);if(this.lensKey===key&&this.lensModel===model)return;
    this.clearLens();this.lensModel=model;this.lensKey=key;
    this.lensIds=model.deltaDecorations([],values.filter(v=>Number.isInteger(v.line)&&v.line>0&&v.line<=model.getLineCount()).slice(0,200).map(v=>{
      const col=model.getLineMaxColumn(v.line),text=(v.label?v.label+' · ':'')+String(v.value).replace(/[\r\n\t]/g,' ');
      return {range:new monaco.Range(v.line,col,v.line,col),options:{description:'Lantern Lens',showIfCollapsed:true,stickiness:monaco.editor.TrackedRangeStickiness.NeverGrowsWhenTypingAtEdges,
        after:{content:'   '+(v.error?'! ':'↳ ')+text.slice(0,120),inlineClassName:'lantern-lens-value'+(v.error?' lantern-lens-error':''),cursorStops:monaco.editor.InjectedTextCursorStops.None},hoverMessage:{value:'Lantern Lens: '+text,isTrusted:false}}};
    }));
  }
  frame(preview){const frame=document.createElement('iframe');frame.title='Vista previa del proyecto';frame.sandbox='allow-scripts allow-forms allow-modals allow-same-origin';frame.src=preview.url;frame.referrerPolicy='no-referrer';return frame;}
  showPreview(preview){this.studio.enter();this.host.platform.openPage('preview',`<div class="preview-toolbar"><span>${esc(preview.path)}</span><button class="secondary-button" id="refresh-preview">${icon('refresh')}Recargar</button><button class="primary-button" data-lantern="start">${icon('sparkles')}Continuar con Lantern</button></div><div class="embedded-preview"></div>`);$('.embedded-preview').append(this.frame(preview));$('#refresh-preview').onclick=()=>$('.embedded-preview').replaceChildren(this.frame(preview));}
  async poll(){
    if(this.disposed)return;
    try{const epoch=this.controlEpoch;const s=await this.host.api('/platform/lantern');if(this.disposed)return;if(!this.controlPending&&epoch===this.controlEpoch){this.state=s;this.render();this.renderLens();
      if(this.matchesBuffer()&&s.status!=='preparing')this.host.editor.setDiagnostics(s.path,s.diagnostics||[],'lumen-build');
      }
    }catch(error){if(!this.disposed)this.state={...this.state,status:'error',error:error.message};}
    this.timer=setTimeout(()=>this.poll(),document.hidden?2000:600);
  }
  dispose(){this.disposed=true;this.clearLens();clearTimeout(this.bufferTimer);clearTimeout(this.timer);clearTimeout(this.followTimer);document.removeEventListener('click',this.click);}
}
