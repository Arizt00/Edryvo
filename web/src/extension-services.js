import {escapeHTML as esc,icon} from './icons.js';

export class ExtensionServicesUI {
  constructor(host){this.host=host;this.panels=new Map();this.disposed=false;this.message=e=>this.receive(e);window.addEventListener('message',this.message);this.resize=new ResizeObserver(()=>this.layout());this.resize.observe(document.getElementById('editor-panel'));this.poll();}
  layout(){const panel=document.getElementById('editor-panel').getBoundingClientRect(),mount=document.getElementById('editor-mount').getBoundingClientRect();for(const state of this.panels.values())if(state.node)state.node.style.top=Math.max(54,mount.top-panel.top)+'px';}
  async event(event){
    const h=this.host,p=h.platform,ed=h.editor;
    if(event.command==='zenit.pick')return this.pick(event);
    if(event.command==='zenit.document.saved'){
      const buffer=event.buffer,record=ed.models.get(buffer.path);if(record&&(record.model?.getValue()??record.value)===buffer.text){record.savedValue=buffer.text;record.revision=buffer.revision;ed.callbacks.change?.(buffer.path,false);h.renderTabs();}return;
    }
    if(event.command==='zenit.terminal.show'){
      if(!p.terminals.has(event.terminal)){const data=await p.api('/terminals');const t=data.sessions.find(x=>x.id===event.terminal);if(t)await p.attachTerminal(t);}else p.selectTerminal(event.terminal);
      return;
    }
    if(event.command==='zenit.terminal.hide'){if(p.activeTerminal===event.terminal)p.useConsole();return;}
    if(event.command==='zenit.debug.show'){await h.studio.debug();return;}
    if(event.command==='zenit.command'){
      if(event.id==='workbench.action.reloadWindow')location.reload();
      if(event.id==='workbench.action.terminal.focus')h.dock.show('console');
      return;
    }
    if(event.command!=='zenit.workspace.edit')return;
    const change=event.edit;
    for(const resource of change.resources||[]){
      if(resource.kind==='rename')for(const path of [...ed.models.keys()])if(path===resource.oldPath||path.startsWith(resource.oldPath+'/')){
        const old=ed.models.get(path),active=ed.current===path,text=old.model?.getValue()??old.value,next=resource.path+path.slice(resource.oldPath.length);ed.close(path);ed.open({...old,path:next,content:text},{activate:active});ed.models.get(next).savedValue=old.savedValue;
      }
      if(resource.kind==='delete')for(const path of [...ed.models.keys()])if(path===resource.path||path.startsWith(resource.path+'/'))ed.close(path);
    }
    for(const buffer of change.buffers||[]){
      let record=ed.models.get(buffer.path);
      if(!record){ed.open({path:buffer.path,content:buffer.before},{activate:false});record=ed.models.get(buffer.path);}
      const text=record.model?.getValue()??record.value;
      if(text===buffer.text)continue;
      if(text!==buffer.before){h.notify('Hay cambios simultáneos en '+buffer.path+'. El búfer local se conserva.','error');continue;}
      if(record.model){record.model.pushStackElement();record.model.pushEditOperations([],[{range:record.model.getFullModelRange(),text:buffer.text}],()=>null);record.model.pushStackElement();}
      else{record.value=buffer.text;if(ed.current===buffer.path)ed.setValue(buffer.text);}
    }
    h.renderTabs();await h.refreshTree();
  }
  async pick(event){
    const h=this.host,opts=event.options||{},items=event.items||[];
    const value=await new Promise(resolve=>{
      let done=false;const finish=value=>{if(done)return;done=true;observer.disconnect();h.closeModal();resolve(value);};
      h.modal(opts.title||'Seleccionar',`<input id="extension-pick-search" class="extension-pick-search" placeholder="${esc(opts.placeHolder||'Buscar…')}" aria-label="Buscar opciones"><div class="extension-pick-list"></div>${opts.canPickMany?'<div class="modal-actions"><button class="primary-button" id="extension-pick-accept">Aceptar</button></div>':''}`);
      const container=document.querySelector('.extension-pick-list'),selected=new Set(items.flatMap((x,i)=>x.picked?[i]:[]));
      const render=query=>{container.replaceChildren();items.forEach((item,index)=>{if(item.kind===-1||!`${item.label} ${item.description||''} ${item.detail||''}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()))return;const button=document.createElement('button');button.className='extension-pick-option';button.innerHTML=`${opts.canPickMany?`<input type="checkbox" tabindex="-1" ${selected.has(index)?'checked':''}>`:''}<span><strong>${esc(item.label)}</strong><small>${esc(item.description||'')}</small><small>${esc(item.detail||'')}</small></span>`;button.onclick=()=>{if(opts.canPickMany){selected.has(index)?selected.delete(index):selected.add(index);render(query);}else finish(index);};container.append(button);});};
      const observer=new MutationObserver(()=>{if(document.querySelector('#modal-backdrop').classList.contains('hidden'))finish(null);});observer.observe(document.querySelector('#modal-backdrop'),{attributes:true,attributeFilter:['class']});
      const search=document.getElementById('extension-pick-search');search.oninput=()=>render(search.value);search.onkeydown=e=>{if(e.key==='Enter'&&!opts.canPickMany){e.preventDefault();container.querySelector('button')?.click();}};document.getElementById('extension-pick-accept')?.addEventListener('click',()=>finish([...selected]));render('');
    });
    await h.platform.api('/extensions/pick',{id:event.id,value});
  }
  async poll(){
    if(this.disposed)return;
    try{
      const {panels}=await this.host.platform.api('/extensions/services');const ids=new Set(panels.filter(x=>x.visible).map(x=>x.id));
      for(const [id,state] of this.panels)if(!ids.has(id)){this.remove(state);this.panels.delete(id);}
      for(const panel of panels){if(!panel.visible)continue;let state=this.panels.get(panel.id);
        if(!state){state={panel,seq:0,urls:[]};this.panels.set(panel.id,state);await this.render(state);this.show(state);}else if(state.panel.html!==panel.html){state.panel=panel;await this.render(state);}else {const previous=state.panel;state.panel=panel;this.title(state);if(previous.revision!==panel.revision&&panel.revealSequence!==previous.revealSequence)this.show(state);}
        for(const item of panel.messages)if(item.seq>state.seq&&state.loaded){state.frame.contentWindow.postMessage(item.message,'*');state.seq=item.seq;}
      }
    }catch(error){if(!this.disposed)console.warn('Extension services:',error.message);}
    this.timer=setTimeout(()=>this.poll(),500);
  }
  restoreTabs(){for(const state of this.panels.values())if(state.tab&&!state.tab.isConnected)document.getElementById('file-tabs').append(state.tab);}
  title(state){if(state.tab)state.tab.querySelector('span').textContent=state.panel.title;if(state.node)state.node.querySelector('strong').textContent=state.panel.title;}
  hide(){for(const state of this.panels.values()){if(state.node){state.node.hidden=true;state.node.classList.remove('active');}state.tab?.classList.remove('active');}if(!this.host.platform.page)delete document.documentElement.dataset.editorCovered;}
  remove(state){state.node?.remove();state.tab?.remove();for(const url of state.urls)URL.revokeObjectURL(url);if(state.node?.classList.contains('active'))this.host.platform.closePage();}
  async render(state){
    const h=this.host,p=state.panel;
    if(!state.tab){const tab=document.createElement('button');tab.className='file-tab extension-webview-tab';tab.innerHTML=icon('browser')+'<span></span>';tab.onclick=()=>this.show(state);document.getElementById('file-tabs').append(tab);state.tab=tab;}
    const active=state.node?.classList.contains('active');state.tab.querySelector('span').textContent=p.title;state.node?.remove();for(const url of state.urls)URL.revokeObjectURL(url);state.urls=[];
    const node=document.createElement('section');node.className='extension-webview-surface';node.hidden=!active;node.classList.toggle('active',!!active);node.dataset.panel=p.id;
    const header=document.createElement('header');header.innerHTML=`<strong>${esc(p.title)}</strong><span>${esc(p.extension)}</span><button class="icon-button" aria-label="Cerrar panel de extensión">${icon('close')}</button>`;header.querySelector('button').onclick=()=>h.platform.api('/extensions/runtime/request',{id:p.extension,method:'webviewDispose',panel:p.id}).catch(error=>h.notify(error.message,'error'));node.append(header);
    const frame=document.createElement('iframe');frame.title=p.title;frame.setAttribute('sandbox',p.options?.enableScripts?'allow-scripts allow-forms allow-downloads':'allow-forms');node.append(frame);state.node=node;state.frame=frame;state.loaded=false;
    let html=p.html;const resources=[...new Set(html.match(/zenit-resource:\/\/[^/]+\/[^"'<>\s)]+/g)||[])];
    for(const resource of resources){try{const uri=new URL(resource),value=decodeURIComponent(uri.pathname.slice(1));const data=await h.platform.api('/extensions/resource?panel='+encodeURIComponent(p.id)+'&path='+encodeURIComponent(value)),raw=Uint8Array.from(atob(data.data),x=>x.charCodeAt(0)),blob=URL.createObjectURL(new Blob([raw],{type:data.mime}));state.urls.push(blob);html=html.replaceAll(resource,blob);}catch(error){h.notify('Recurso del panel: '+error.message,'error');}}
    const nonce=html.match(/nonce=["']([^"']+)["']/)?.[1]||'';
    const script=`<script${nonce?' nonce="'+esc(nonce)+'"':''}>const __stateKey=${JSON.stringify(p.id)};let __state=${JSON.stringify(state.savedState??p.state??null).replaceAll('<','\\u003c')},__acquired=false;window.acquireVsCodeApi=()=>{if(__acquired)throw Error('acquireVsCodeApi ya se ha llamado.');__acquired=true;return Object.freeze({postMessage:message=>parent.postMessage({zenitWebview:__stateKey,message},'*'),getState:()=>__state,setState:value=>{__state=value;parent.postMessage({zenitWebview:__stateKey,state:value,stateUpdate:true},'*');return value;}});};<\/script>`;
    frame.onload=()=>{state.loaded=true;};const rendered=await h.platform.api('/extensions/webview/document',{panel:p.id,html:script+html});frame.src=rendered.url;
    document.getElementById('editor-panel').append(node);this.layout();
  }
  show(state){for(const value of this.panels.values()){if(value.node){value.node.hidden=true;value.node.classList.remove('active');}value.tab?.classList.remove('active');}this.host.platform.closePage();state.node.hidden=false;state.node.classList.add('active');state.tab.classList.add('active');document.documentElement.dataset.editorCovered='true';}
  async receive(event){const id=event.data?.zenitWebview,state=this.panels.get(id);if(!state||event.source!==state.frame?.contentWindow)return;if(event.data.stateUpdate){state.savedState=event.data.state;return;}try{await this.host.platform.api('/extensions/runtime/request',{id:state.panel.extension,method:'webviewMessage',panel:id,message:event.data.message});}catch(error){this.host.notify(error.message,'error');}}
  dispose(){this.disposed=true;clearTimeout(this.timer);this.resize.disconnect();window.removeEventListener('message',this.message);for(const state of this.panels.values())this.remove(state);}
}
