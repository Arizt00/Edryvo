import {escapeHTML as esc,icon} from './icons.js';

export class ExtensionQuickInputUI {
  constructor(host){this.host=host;this.sequence=0;this.queue=Promise.resolve();this.closed=new Map();}
  send(type,values={}){
    const data={id:this.state.id,type,sequence:++this.sequence,...values};
    this.queue=this.queue.then(()=>this.host.platform.api('/extensions/quickinput/event',data)).catch(error=>this.host.notify(error.message,'error'));
    return this.queue;
  }
  dismiss(notify=true){
    if(!this.root)return;
    if(notify){this.send('hide');this.closed.set(this.state.id,this.sequence);}
    this.root.remove();this.root=null;this.previousFocus?.focus?.();
  }
  update(state){
    if(!state.visible){this.closed.delete(state.id);if(this.state?.id===state.id)this.dismiss(false);return;}
    if((this.closed.get(state.id)||0)>(state.ack||0))return;
    if(this.state?.id!==state.id||!this.root){
      if(this.root)this.dismiss();this.state=state;this.sequence=state.ack||0;this.previousFocus=document.activeElement;
      this.root=document.createElement('div');this.root.className='zenit-quick-backdrop';
      this.root.innerHTML=`<section class="zenit-quickinput" role="dialog" aria-modal="true" aria-labelledby="zenit-quick-title"><header><div class="zenit-quick-buttons"></div><strong id="zenit-quick-title"></strong><small class="zenit-quick-step"></small><button class="icon-button zenit-quick-close" aria-label="Cerrar">${icon('close')}</button></header><div class="zenit-quick-field"><input autocomplete="off" spellcheck="false"><span class="zenit-quick-busy" hidden>${icon('refresh')}</span></div><p class="zenit-quick-prompt"></p><p class="zenit-quick-validation" role="status" aria-live="polite"></p><div class="zenit-quick-list" role="listbox"></div><footer><small class="zenit-quick-source"></small><button class="primary-button zenit-quick-accept">Aceptar</button><span class="zenit-quick-hint"><kbd>↑ ↓</kbd> navegar · <kbd>↵</kbd> elegir · <kbd>Esc</kbd> cerrar</span></footer></section>`;
      document.body.append(this.root);this.input=this.root.querySelector('input');this.list=this.root.querySelector('.zenit-quick-list');
      this.input.oninput=()=>{this.state.value=this.input.value;this.send('value',{value:this.input.value});this.renderItems();};
      this.root.querySelector('.zenit-quick-close').onclick=()=>this.dismiss();this.root.querySelector('.zenit-quick-accept').onclick=()=>this.accept();
      this.root.onpointerdown=e=>{if(e.target===this.root&&!this.state.ignoreFocusOut)this.dismiss();};
      this.root.onkeydown=e=>this.key(e);this.input.focus();
    }
    this.state=state;
    const q=selector=>this.root.querySelector(selector),message=state.validationMessage;
    q('#zenit-quick-title').textContent=state.title||(state.kind==='pick'?'Seleccionar opción':'Introducir valor');
    q('.zenit-quick-step').textContent=state.step?`${state.step}${state.totalSteps?' / '+state.totalSteps:''}`:'';
    q('.zenit-quick-source').textContent=state.extension||'';
    const buttons=q('.zenit-quick-buttons');buttons.replaceChildren();for(const b of state.buttons||[]){const button=document.createElement('button');button.className='icon-button';button.title=b.tooltip;button.setAttribute('aria-label',b.tooltip||'Acción');button.innerHTML=icon(b.back?'chevron-left':b.icon==='add'?'plus':b.icon==='refresh'?'refresh':'more');button.onclick=()=>this.send('button',{key:b.key});buttons.append(button);}
    this.input.type=state.password?'password':'text';this.input.placeholder=state.placeholder||'';this.input.setAttribute('aria-label',state.placeholder||state.title||'Valor');this.input.disabled=state.enabled===false;
    if((state.ack||0)>=this.sequence||this.sequence===0){if(this.input.value!==(state.value||''))this.input.value=state.value||'';if(state.valueSelection){this.input.setSelectionRange(...state.valueSelection);}}
    q('.zenit-quick-busy').hidden=!state.busy;q('.zenit-quick-prompt').textContent=state.prompt||'';
    q('.zenit-quick-validation').textContent=typeof message==='string'?message:message?.message||'';q('.zenit-quick-validation').dataset.severity=typeof message==='string'?'3':String(message?.severity||1);
    q('.zenit-quick-accept').hidden=state.kind==='pick'&&!state.canSelectMany;q('.zenit-quick-hint').hidden=state.kind!=='pick';
    q('.zenit-quick-accept').disabled=state.enabled===false||!!message&&(typeof message==='string'||message.severity===3);
    this.root.querySelector('section').dataset.kind=state.kind;this.renderItems();
  }
  renderItems(){
    const s=this.state,query=this.input.value.toLocaleLowerCase(),scroll=this.list.scrollTop;this.list.replaceChildren();this.visible=[];
    if(s.kind!=='pick')return;
    const selected=new Set(s.selectedItems||[]);
    for(const item of s.items||[]){
      if(item.kind===-1){const separator=document.createElement('div');separator.className='zenit-quick-separator';separator.textContent=item.label||'';this.list.append(separator);continue;}
      const text=[s.matchOnLabel===false?'':item.label,s.matchOnDescription?item.description:'',s.matchOnDetail?item.detail:''].filter(Boolean).join(' ').toLocaleLowerCase();
      if(!item.alwaysShow&&!text.includes(query))continue;
      this.visible.push(item);const row=document.createElement('div');row.className='zenit-quick-row';row.dataset.key=item.key;row.setAttribute('role','option');row.setAttribute('aria-selected',String(selected.has(item.key)));row.tabIndex=-1;
      row.innerHTML=`${s.canSelectMany?`<span class="zenit-quick-check">${selected.has(item.key)?icon('check'):''}</span>`:''}<span class="zenit-quick-label"><strong>${esc(item.label)}</strong>${item.description?`<small>${esc(item.description)}</small>`:''}${item.detail?`<small class="zenit-quick-detail">${esc(item.detail)}</small>`:''}</span><span class="zenit-quick-item-buttons"></span>`;
      row.onpointermove=()=>this.active(item.key);row.onclick=()=>{if(s.enabled===false)return;this.active(item.key);if(s.canSelectMany){selected.has(item.key)?selected.delete(item.key):selected.add(item.key);s.selectedItems=[...selected];this.send('selection',{keys:s.selectedItems});this.renderItems();}else{this.state.selectedItems=[item.key];this.send('selection',{keys:[item.key]});this.send('accept');}};
      for(const b of item.buttons||[]){const button=document.createElement('button');button.className='icon-button';button.title=b.tooltip;button.setAttribute('aria-label',b.tooltip||'Acción');button.innerHTML=icon(b.icon==='trash'?'trash':b.icon==='refresh'?'refresh':'more');button.onclick=e=>{e.stopPropagation();this.send('itemButton',{item:item.key,key:b.key});};row.lastChild.append(button);}
      this.list.append(row);
    }
    if(!this.visible.length){const empty=document.createElement('p');empty.className='zenit-quick-empty';empty.textContent=s.busy?'Buscando opciones…':'No hay coincidencias';this.list.append(empty);}
    const wanted=(s.activeItems||[]).find(key=>this.visible.some(item=>item.key===key))||this.visible[0]?.key;
    this.active(wanted);
    if(s.keepScrollPosition)this.list.scrollTop=scroll;
  }
  active(key){
    if(!key)return;
    const changed=this.activeKey!==key;this.activeKey=key;
    for(const row of this.list.querySelectorAll('[role=option]'))row.classList.toggle('active',row.dataset.key===key);
    if(changed)this.send('active',{keys:[key]});
  }
  accept(){if(this.state.enabled===false)return;if(this.state.kind==='pick'&&!this.state.canSelectMany){this.send('selection',{keys:this.activeKey?[this.activeKey]:[]});}this.send('accept');}
  key(e){
    if(e.key==='Escape'){e.preventDefault();e.stopPropagation();this.dismiss();return;}
    if(e.key==='Enter'){e.preventDefault();this.accept();return;}
    if(this.state.kind==='pick'&&['ArrowDown','ArrowUp'].includes(e.key)){
      e.preventDefault();if(!this.visible.length)return;let index=this.visible.findIndex(x=>x.key===this.activeKey);index=(index+(e.key==='ArrowDown'?1:-1)+this.visible.length)%this.visible.length;this.active(this.visible[index].key);this.list.querySelector(`[data-key="${this.activeKey}"]`)?.scrollIntoView({block:'nearest'});
    }
    if(e.key==='Tab'){const nodes=[...this.root.querySelectorAll('button:not([hidden]):not(:disabled),input:not(:disabled)')].filter(x=>x.getClientRects().length);if(nodes.length){e.preventDefault();const current=nodes.indexOf(document.activeElement),next=(current+(e.shiftKey?-1:1)+nodes.length)%nodes.length;nodes[next].focus();}}
  }
  dispose(){this.dismiss();}
}
