import {icon,escapeHTML} from './icons.js';
import {outsideViewport} from './document-drag.js';
import {defaultLayout,normalizeLayout,layoutPreset,movePanel,setCollapsed,sideOf,SIDES,LAYOUT_KEY,PRESET_NAMES} from './layout-state.js';

const PANEL_LABELS={project:'Proyecto',assistant:'Asistente',console:'Consola'};
const PANEL_ICONS={project:'files',assistant:'sparkles',console:'terminal'};
const SIDE_LABELS={left:'izquierda',right:'derecha',bottom:'abajo'};
const PANEL_SELECTORS={project:'#project-panel',assistant:'#assistant-panel',console:'#terminal-panel'};

/** Three persistent tool docks. Reparents live DOM, never clones editor or forms. */
export class DockManager {
  constructor(workspace,motion,onChange=()=>{}) {
    this.root=workspace;this.motion=motion;this.onChange=onChange;this.compactOpen=false;
    this.focusRestore=null;this.savedFocus={};this.drag=null;this.listeners=[];this.sizeFrame=0;this.nativeDetached=new Set();
    this.panels=Object.fromEntries(Object.entries(PANEL_SELECTORS).map(([id,selector])=>[id,workspace.querySelector(selector)]));
    this.editor=workspace.querySelector('#editor-panel');
    this.state=this.read();this.slots={};this.floats={};this.root.classList.add('docking-enabled');
    for(const side of SIDES) {
      const slot=document.createElement('section');slot.className='dock-slot';slot.dataset.dockSide=side;
      slot.id='dock-'+side;slot.setAttribute('aria-label','Paneles: '+SIDE_LABELS[side]);
      slot.innerHTML=`<div class="dock-strip"><div class="dock-tabs" role="tablist" aria-label="Paneles agrupados ${SIDE_LABELS[side]}"></div><div class="dock-group-actions"></div></div><div class="dock-content" id="dock-content-${side}"></div><div class="dock-collapsed-rail" aria-label="Panel contraído"></div>`;
      this.root.appendChild(slot);this.slots[side]=slot;
    }
    this.targets=document.createElement('div');this.targets.className='dock-targets';this.targets.hidden=true;
    this.targets.innerHTML=SIDES.map(side=>`<div class="dock-target dock-target-${side}" data-drop-side="${side}"><span>${icon('dock-'+side)}<strong>Agrupar ${side==='bottom'?'abajo':'a la '+SIDE_LABELS[side]}</strong><small>Conserva el contenido del panel</small></span></div>`).join('');
    this.root.appendChild(this.targets);
    this.ghost=document.createElement('div');this.ghost.className='dock-ghost';this.ghost.hidden=true;document.body.appendChild(this.ghost);
    this.scrim=document.createElement('button');this.scrim.className='dock-scrim';this.scrim.hidden=true;this.scrim.setAttribute('aria-label','Cerrar panel lateral');this.root.appendChild(this.scrim);
    this.listen(this.scrim,'click',()=>{this.compactOpen=false;this.render();});
    for(const [id,panel] of Object.entries(this.panels)) {
      const actions=panel.querySelector(id==='console'?'.terminal-tools':'.heading-actions');
      actions.insertAdjacentHTML('beforeend',`<button class="icon-button pane-float" data-panel-float="${id}" title="Dejar ${PANEL_LABELS[id]} flotante" aria-label="Dejar ${PANEL_LABELS[id]} flotante">${icon('layout')}</button>${id!=='console'?`<button class="icon-button pane-close" data-dock-hide="${id}" title="Cerrar panel ${PANEL_LABELS[id]}" aria-label="Cerrar panel ${PANEL_LABELS[id]}">${icon('close')}</button>`:''}`);
      if(id==='console')continue;
      const button=document.createElement('button');button.className='icon-button pane-collapse';button.dataset.collapsePanel=id;
      panel.querySelector('.heading-actions').appendChild(button);
    }
    this.bindEvents();this.bindResizers();this.render();
  }
  listen(target,event,handler,options){target.addEventListener(event,handler,options);this.listeners.push(()=>target.removeEventListener(event,handler,options));}
  read(){try{return normalizeLayout(JSON.parse(localStorage.getItem(LAYOUT_KEY)||localStorage.getItem('lumen.layout.v2')||'null'));}catch(_){return defaultLayout();}}
  save(){if(new URLSearchParams(location.search).has('panel'))return;try{localStorage.setItem(LAYOUT_KEY,JSON.stringify({...this.state,hidden:this.state.hidden.filter(id=>!this.nativeDetached.has(id))}));}catch(_){/* Session remains usable in storage-restricted webviews. */}}
  snapshot(){return JSON.parse(JSON.stringify(this.state));}
  visibleIds(side){return this.state.groups[side].filter(id=>!this.state.hidden.includes(id)&&!this.state.floating[id]);}
  isVisible(id){const side=sideOf(this.state,id);return !this.state.hidden.includes(id)&&(!!this.state.floating[id]||(!this.state.collapsed.includes(side)&&this.state.active[side]===id));}
  announce(message){document.querySelector('#layout-announcement').textContent=message;}
  transition(change,animate=true){
    const apply=()=>{change();this.state=normalizeLayout(this.state);this.save();this.render();};
    if(animate)this.motion.changeLayout([this.editor,...Object.values(this.slots)],apply);else apply();
  }
  preset(name){
    this.transition(()=>{const rail=this.state.railCompact;this.state=layoutPreset(name);this.state.railCompact=rail;this.compactOpen=false;this.focusRestore=null;});
    this.announce('Distribución '+(PRESET_NAMES[name]||'Lumen')+' aplicada.');
  }
  reset(){this.transition(()=>{this.state=defaultLayout();this.compactOpen=false;this.focusRestore=null;});this.announce('Distribución Lumen restaurada, con navegación completa.');}
  focus(){
    if(this.state.preset==='focus'){const previous=this.focusRestore||defaultLayout();this.transition(()=>{this.state=previous;this.focusRestore=null;});}
    else {this.focusRestore=this.snapshot();this.transition(()=>{const rail=this.state.railCompact;this.state=layoutPreset('focus');this.state.railCompact=rail;this.compactOpen=false;});}
    this.announce(this.state.preset==='focus'?'Modo enfoque. Pulsa Ctrl Alt F para volver.':'Distribución restaurada.');
  }
  move(id,side,index=Infinity){
    this.transition(()=>{this.state=movePanel(this.state,id,side,index);if(side==='right')this.compactOpen=true;});
    this.announce(`${PANEL_LABELS[id]} movido ${side==='bottom'?'abajo':'a la '+SIDE_LABELS[side]}.`);
  }
  show(id,{animate=true}={}){
    if(!this.panels[id])return;
    if(this.isVisible(id))return;
    this.transition(()=>{const side=sideOf(this.state,id);this.state.hidden=this.state.hidden.filter(item=>item!==id);this.state.active[side]=id;this.state.collapsed=this.state.collapsed.filter(value=>value!==side);if(side==='right')this.compactOpen=true;this.state.preset='custom';},animate);
  }
  hide(id){
    if(!this.panels[id])return;
    const focused=this.panels[id].contains(document.activeElement);
    this.transition(()=>{this.state.hidden=[...new Set([...this.state.hidden,id])];this.state.preset='custom';});
    if(focused)document.querySelector('#layout-trigger')?.focus();
  }
  toggle(id){this.isVisible(id)?this.hide(id):this.show(id);}
  select(id,focusTab=false){
    if(this.state.floating[id]){this.show(id);this.raiseFloat(id);return;}
    const side=sideOf(this.state,id),changed=this.state.active[side]!==id;
    this.state.active[side]=id;this.state.collapsed=this.state.collapsed.filter(value=>value!==side);this.state.hidden=this.state.hidden.filter(item=>item!==id);this.save();this.render();
    if(changed)this.motion.enter(this.panels[id],3);
    if(focusTab)this.slots[side].querySelector(`[data-dock-tab="${id}"]`)?.focus();
  }
  collapse(side) {
    if(!['left','right'].includes(side)||!this.visibleIds(side).length||this.state.collapsed.includes(side))return;
    const content=this.slots[side].querySelector('.dock-content');
    if(content.contains(document.activeElement))this.savedFocus[side]=document.activeElement;
    this.transition(()=>{this.state=setCollapsed(this.state,side,true);if(side==='right')this.compactOpen=false;});
    const target=this.slots[side].querySelector('[data-dock-expand]');
    (target?.offsetParent?target:document.querySelector(`[data-toggle-side="${side}"]`))?.focus({preventScroll:true});
    this.announce('Panel '+SIDE_LABELS[side]+' contraído. Su contenido se conserva.');
  }
  expand(side,id=null) {
    if(!['left','right'].includes(side))return;
    this.transition(()=>{
      this.state=setCollapsed(this.state,side,false);
      if(id&&this.state.groups[side].includes(id))this.state.active[side]=id;
      if(side==='right')this.compactOpen=true;
    });
    const focus=this.savedFocus[side];
    if(focus?.isConnected&&!focus.closest('[hidden],[inert]'))focus.focus({preventScroll:true});
    else this.slots[side].querySelector('[data-collapse-panel], [data-dock-collapse]')?.focus({preventScroll:true});
    this.announce('Panel '+SIDE_LABELS[side]+' expandido.');
  }
  toggleSide(side) {
    if(!['left','right'].includes(side))return;
    if(!this.visibleIds(side).length){
      const id=this.state.groups[side][0]||({left:'project',right:'assistant'}[side]);
      if(sideOf(this.state,id)!==side)this.move(id,side);
      this.show(id);return;
    }
    if(this.state.collapsed.includes(side))this.expand(side);
    else this.collapse(side);
  }
  toggleRail() {
    this.transition(()=>{this.state.railCompact=!this.state.railCompact;});
    this.announce(this.state.railCompact?'Navegación compacta: solo iconos.':'Navegación con etiquetas.');
  }
  organize(id){this.root.dispatchEvent(new CustomEvent('lumen:organize',{bubbles:true,detail:{panel:id}}));}
  floatBounds(id,rect){
    const area=this.root.getBoundingClientRect(),left=(this.root.querySelector('.activity-rail')?.getBoundingClientRect().width||48)+8;
    const width=Math.min(Math.max(id==='assistant'?320:280,rect.width),Math.max(280,area.width-left-8));
    const height=Math.min(Math.max(id==='assistant'?450:200,rect.height),Math.max(200,area.height-8));
    return {x:Math.max(left,Math.min(area.width-width-8,rect.x)),y:Math.max(0,Math.min(area.height-height-8,rect.y)),width,height};
  }
  floatPanel(id,rect){
    if(!this.panels[id])return;
    const area=this.root.getBoundingClientRect(),width=id==='console'?650:id==='assistant'?390:330,height=id==='console'?300:Math.min(640,area.height-24);
    this.transition(()=>{this.state.floating[id]=this.floatBounds(id,rect||this.state.floating[id]||{x:(area.width-width)/2,y:24,width,height});this.state.hidden=this.state.hidden.filter(x=>x!==id);this.state.preset='custom';});
    this.raiseFloat(id);this.announce(PANEL_LABELS[id]+' flotante. Arrastra su cabecera; sus controles permiten acoplarlo o cerrarlo.');
  }
  raiseFloat(id){const frames=Object.entries(this.floats).filter(([key])=>key!==id).sort((a,b)=>Number(a[1].style.zIndex)-Number(b[1].style.zIndex));if(this.floats[id])frames.push([id,this.floats[id]]);frames.forEach(([,frame],i)=>frame.style.zIndex=String(20+i));}
  placeFloat(id){
    const rect=this.floatBounds(id,this.state.floating[id]);this.state.floating[id]=rect;
    Object.assign(this.floats[id].style,{left:rect.x+'px',top:rect.y+'px',width:rect.width+'px',height:rect.height+'px'});
  }
  renderFloats(){
    for(const [id,panel] of Object.entries(this.panels)){
      if(panel.classList.contains('native-detached-content'))continue;
      if(!this.state.floating[id]){this.floats[id]?.remove();delete this.floats[id];continue;}
      let frame=this.floats[id];const created=!frame;
      if(!frame){
        frame=document.createElement('section');frame.className='floating-panel';frame.dataset.floatingPanel=id;frame.setAttribute('aria-label',PANEL_LABELS[id]+' flotante');
        frame.innerHTML=`<header class="floating-title" data-dock-handle="${id}"><span>${icon(PANEL_ICONS[id])}${PANEL_LABELS[id]}</span><small>Flotante</small><div>${SIDES.map(side=>`<button class="icon-button" data-float-dock="${id}" data-float-side="${side}" title="Acoplar ${SIDE_LABELS[side]}" aria-label="Acoplar ${PANEL_LABELS[id]} ${SIDE_LABELS[side]}">${icon('dock-'+side)}</button>`).join('')}<button class="icon-button" data-dock-hide="${id}" title="Cerrar panel" aria-label="Cerrar ${PANEL_LABELS[id]} flotante">${icon('close')}</button></div></header><div class="floating-content"></div><button class="floating-resize" data-floating-resize="${id}" aria-label="Cambiar tamaño de ${PANEL_LABELS[id]}" title="Arrastra para cambiar tamaño; flechas para ajuste fino">${icon('grip')}</button>`;
        this.root.appendChild(frame);this.floats[id]=frame;this.raiseFloat(id);
      }
      const content=frame.querySelector('.floating-content');if(panel.parentElement!==content)content.appendChild(panel);
      frame.hidden=this.state.hidden.includes(id);panel.hidden=frame.hidden;panel.inert=frame.hidden;panel.removeAttribute('role');panel.removeAttribute('aria-labelledby');this.placeFloat(id);if(created&&!frame.hidden)this.motion.enter(frame,4);
    }
  }
  resizeFloat(event,id){
    event.preventDefault();event.stopPropagation();this.motion.cancelLayout();this.raiseFloat(id);
    const start={...this.state.floating[id]},x=event.clientX,y=event.clientY;
    const move=e=>{this.state.floating[id]=this.floatBounds(id,{...start,width:start.width+e.clientX-x,height:start.height+e.clientY-y});this.placeFloat(id);};
    const end=()=>{window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',end);window.removeEventListener('pointercancel',end);window.removeEventListener('blur',end);this.save();this.onChange();};
    window.addEventListener('pointermove',move);window.addEventListener('pointerup',end);window.addEventListener('pointercancel',end);window.addEventListener('blur',end);
  }
  render(){
    const compact=false; // Side panels stay in the grid at every supported desktop size.
    this.root.classList.toggle('rail-compact',this.state.railCompact);
    document.querySelector('[data-action="toggle-rail"]')?.setAttribute('aria-expanded',String(!this.state.railCompact));
    const limits=this.limits();
    for(const side of SIDES){
      const slot=this.slots[side],visible=this.visibleIds(side),active=this.state.active[side];
      const available=visible.length>0&&(side!=='right'||!compact||this.compactOpen);
      const collapsed=this.state.collapsed.includes(side)&&side!=='bottom';
      slot.hidden=!available;slot.classList.toggle('is-collapsed',collapsed);
      const content=slot.querySelector('.dock-content');content.inert=collapsed||!available;content.setAttribute('aria-hidden',String(collapsed||!available));slot.classList.toggle('is-grouped',visible.length>1);
      slot.classList.toggle('is-overlay',side==='right'&&compact&&available);
      const rail=slot.querySelector('.dock-collapsed-rail');
      rail.hidden=!collapsed;
      const railHTML=`<button class="icon-button dock-expand" data-dock-expand="${side}" aria-expanded="false" aria-controls="dock-content-${side}" title="Expandir panel ${SIDE_LABELS[side]}" aria-label="Expandir panel ${SIDE_LABELS[side]}">${icon('panel-expand-'+side)}</button><span class="collapsed-divider"></span>`+visible.map(id=>`<button class="collapsed-tool ${id===active?'active':''}" data-dock-restore="${id}" data-dock-start="${id}" title="Abrir ${PANEL_LABELS[id]}" aria-label="Abrir ${PANEL_LABELS[id]}" aria-controls="${this.panels[id].id}" aria-expanded="false">${icon(PANEL_ICONS[id])}</button>`).join('')+`<span class="collapsed-caption" aria-hidden="true">${visible.length>1?'Paneles':PANEL_LABELS[active]||''}</span>`;
      if(rail.innerHTML!==railHTML)rail.innerHTML=railHTML;
      const tabs=slot.querySelector('.dock-tabs');
      // No duplication of panes, textarea values, output or listeners.
      for(const id of this.state.groups[side]){
        if(this.panels[id].classList.contains('native-detached-content'))continue;
        if(this.state.floating[id])continue;
        const panel=this.panels[id];if(panel.parentElement!==slot.querySelector('.dock-content'))slot.querySelector('.dock-content').appendChild(panel);
        panel.hidden=id!==active||this.state.hidden.includes(id);panel.inert=panel.hidden;
        if(visible.length>1){panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby','dock-tab-'+id);}
        else {panel.removeAttribute('role');panel.removeAttribute('aria-labelledby');}
      }
      tabs.innerHTML=visible.map(id=>`<button id="dock-tab-${id}" role="tab" aria-selected="${id===active}" aria-controls="${this.panels[id].id}" tabindex="${id===active?0:-1}" class="dock-tab${id===active?' active':''}" data-dock-tab="${id}" data-dock-start="${id}" title="${escapeHTML(PANEL_LABELS[id])}: arrastra para separar o agrupar">${icon(PANEL_ICONS[id])}<span>${PANEL_LABELS[id]}</span></button>`).join('');
      const actions=slot.querySelector('.dock-group-actions');
      // Grouping replaces the heading, so retain the active pane's real actions.
      const contextActions=active==='assistant'
        ? `<button class="icon-button" data-action="new-chat" title="Nueva conversación" aria-label="Nueva conversación">${icon('plus')}</button><button class="icon-button" data-action="ai-settings" title="Conectar modelo local" aria-label="Conectar modelo local">${icon('sliders')}</button>`
        : active==='project'
        ? `<button class="icon-button" data-action="new-file" title="Nuevo archivo" aria-label="Nuevo archivo">${icon('plus')}</button><button class="icon-button" data-action="project-menu" title="Acciones del proyecto" aria-label="Acciones del proyecto">${icon('folder-open')}</button>` : '';
      actions.innerHTML=active?contextActions+(side!=='bottom'?`<button class="icon-button" data-dock-collapse="${side}" aria-expanded="${!collapsed}" aria-controls="dock-content-${side}" title="Contraer panel ${SIDE_LABELS[side]}" aria-label="Contraer panel ${SIDE_LABELS[side]}">${icon('panel-collapse-'+side)}</button>`:'')+`<button class="icon-button" data-dock-place="${active}" title="Mover ${PANEL_LABELS[active]}" aria-label="Mover ${PANEL_LABELS[active]}">${icon('layout')}</button><button class="icon-button" data-dock-hide="${active}" title="Ocultar ${PANEL_LABELS[active]}" aria-label="Ocultar ${PANEL_LABELS[active]}">${icon('close')}</button>`:'';
      const requested=this.state.sizes[side]??limits[side].preferred;
      const size=Math.max(limits[side].min,Math.min(limits[side].max,requested));
      this.root.style.setProperty(`--dock-${side}-size`,size+'px');
      this.root.style.setProperty(`--dock-${side}-track`,available&&!(side==='right'&&compact)?((collapsed?44:size)+10)+'px':'0px');
      const handle=slot.querySelector('.resize-handle');
      if(handle){handle.setAttribute('aria-valuenow',String(Math.round(size)));handle.setAttribute('aria-valuemin',String(limits[side].min));handle.setAttribute('aria-valuemax',String(limits[side].max));}
    }
    this.renderFloats();
    for(const button of this.root.querySelectorAll('[data-collapse-panel]')){
      const side=sideOf(this.state,button.dataset.collapsePanel);
      button.hidden=side==='bottom';button.innerHTML=icon('panel-collapse-'+side);
      button.setAttribute('title','Contraer panel '+SIDE_LABELS[side]);button.dataset.tooltip='Contraer panel '+SIDE_LABELS[side];
      button.setAttribute('aria-label','Contraer panel '+SIDE_LABELS[side]);button.setAttribute('aria-expanded','true');button.setAttribute('aria-controls','dock-content-'+side);
    }
    for(const button of document.querySelectorAll('[data-toggle-side]')){
      const side=button.dataset.toggleSide,expanded=this.visibleIds(side).length>0&&!this.state.collapsed.includes(side)&&!(side==='right'&&compact&&!this.compactOpen);
      button.setAttribute('aria-expanded',String(expanded));button.classList.toggle('is-open',expanded);
      button.setAttribute('aria-controls','dock-content-'+side);
      const label=(expanded?'Contraer':'Expandir')+' panel '+SIDE_LABELS[side];
      button.setAttribute('aria-label',label);button.dataset.tooltip=label;
    }
    this.scrim.hidden=!(compact&&this.compactOpen&&this.visibleIds('right').length);
    this.root.classList.toggle('dock-focus',this.state.hidden.length===3);
    const trigger=document.querySelector('#layout-trigger');
    trigger?.setAttribute('aria-label','Organizar paneles. Distribución: '+(PRESET_NAMES[this.state.preset]||'Personalizada'));
    document.querySelector('[data-action="toggle-ai"]')?.setAttribute('aria-pressed',String(this.isVisible('assistant')));
    this.onChange();
  }
  limits(){
    const small=innerWidth<=1450;
    return {
      left:{min:200,max:Math.max(210,Math.min(430,innerWidth*.24)),preferred:innerWidth<1180?230:small?250:Math.min(320,innerWidth*.1796)},
      right:{min:280,max:Math.max(290,Math.min(560,innerWidth*.32)),preferred:innerWidth<1180?300:small?350:Math.min(460,innerWidth*.256)},
      bottom:{min:110,max:Math.max(130,Math.round((innerHeight-100)*.65)),preferred:innerHeight<800?158:180}
    };
  }
  setSize(side,value,persist=true){
    this.motion.cancelLayout();
    const limit=this.limits()[side];this.state.sizes[side]=Math.round(Math.min(limit.max,Math.max(limit.min,value)));
    const actual=this.state.sizes[side];this.root.style.setProperty(`--dock-${side}-size`,actual+'px');
    this.root.style.setProperty(`--dock-${side}-track`,(actual+10)+'px');
    this.slots[side].querySelector('.resize-handle')?.setAttribute('aria-valuenow',String(actual));
    if(persist)this.save();
  }
  toggleConsoleSize(){const side=sideOf(this.state,'console');this.show('console');if(side==='bottom'){const current=this.slots.bottom.getBoundingClientRect().height;this.transition(()=>{this.state.sizes.bottom=current>250?180:Math.round((innerHeight-100)*.52);});}else this.move('console','bottom');}
  bindResizers(){
    const handles={left:'tree-resizer',right:'ai-resizer',bottom:'terminal-resizer'};
    for(const [side,id] of Object.entries(handles)){
      const handle=document.getElementById(id);this.slots[side].appendChild(handle);
      handle.className='resize-handle '+(side==='bottom'?'horizontal':'vertical')+' dock-resizer dock-resizer-'+side;
      handle.setAttribute('aria-orientation',side==='bottom'?'horizontal':'vertical');
      handle.setAttribute('aria-label',side==='bottom'?'Altura del grupo inferior':'Ancho del grupo '+SIDE_LABELS[side]);
      this.listen(handle,'pointerdown',event=>{
        if(event.button!==0)return;event.preventDefault();event.stopPropagation();this.motion.cancelLayout();
        const axis=side==='bottom'?'clientY':'clientX',start=event[axis],sign=side==='left'?1:-1;
        const r=this.slots[side].getBoundingClientRect(),size=side==='bottom'?r.height:r.width;
        handle.setPointerCapture(event.pointerId);document.body.classList.add('resizing');document.body.style.cursor=side==='bottom'?'row-resize':'col-resize';
        const move=e=>{this.setSize(side,size+(e[axis]-start)*sign,false);};
        const done=()=>{this.save();document.body.classList.remove('resizing');document.body.style.cursor='';handle.removeEventListener('pointermove',move);handle.removeEventListener('pointerup',done);handle.removeEventListener('pointercancel',done);handle.removeEventListener('lostpointercapture',done);};
        handle.addEventListener('pointermove',move);handle.addEventListener('pointerup',done);handle.addEventListener('pointercancel',done);handle.addEventListener('lostpointercapture',done);
      });
      this.listen(handle,'dblclick',()=>this.transition(()=>{delete this.state.sizes[side];}));
      this.listen(handle,'keydown',event=>{
        const vertical=side!=='bottom';const keys=vertical?['ArrowLeft','ArrowRight']:['ArrowUp','ArrowDown'];
        if(!keys.includes(event.key))return;event.preventDefault();this.motion.cancelLayout();
        const rect=this.slots[side].getBoundingClientRect(),size=vertical?rect.width:rect.height;
        const step=event.shiftKey?30:10,sign=side==='left'?1:-1;
        this.setSize(side,size+(event.key===keys[1]?step:-step)*sign);
      });
    }
  }
  bindEvents(){
    this.listen(this.root,'click',event=>{
      if(this.suppressClick){event.preventDefault();event.stopImmediatePropagation();return;}
      const floating=event.target.closest('[data-panel-float]');if(floating){this.floatPanel(floating.dataset.panelFloat);return;}
      const anchor=event.target.closest('[data-float-dock]');if(anchor){this.move(anchor.dataset.floatDock,anchor.dataset.floatSide);return;}
      const collapse=event.target.closest('[data-collapse-panel],[data-dock-collapse]');
      if(collapse){this.collapse(collapse.dataset.dockCollapse||sideOf(this.state,collapse.dataset.collapsePanel));return;}
      const expand=event.target.closest('[data-dock-expand],[data-dock-restore]');
      if(expand){const id=expand.dataset.dockRestore;this.expand(expand.dataset.dockExpand||sideOf(this.state,id),id);return;}
      const tab=event.target.closest('[data-dock-tab]');if(tab){this.select(tab.dataset.dockTab,true);return;}
      const place=event.target.closest('[data-dock-place],.dock-grip');if(place){this.organize(place.dataset.dockPlace||place.dataset.dockStart);return;}
      const close=event.target.closest('[data-dock-hide]');if(close)this.hide(close.dataset.dockHide);
    },true);
    this.listen(this.root,'keydown',event=>{
      const resize=event.target.closest('[data-floating-resize]');
      if(resize&&['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key)){
        event.preventDefault();const id=resize.dataset.floatingResize,rect=this.state.floating[id],step=event.shiftKey?30:10;
        this.state.floating[id]=this.floatBounds(id,{...rect,width:rect.width+(event.key==='ArrowRight'?step:event.key==='ArrowLeft'?-step:0),height:rect.height+(event.key==='ArrowDown'?step:event.key==='ArrowUp'?-step:0)});this.placeFloat(id);this.save();this.onChange();return;
      }
      const tab=event.target.closest('[data-dock-tab]');if(!tab)return;
      const side=sideOf(this.state,tab.dataset.dockTab),ids=this.visibleIds(side),index=ids.indexOf(tab.dataset.dockTab);
      if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){
        event.preventDefault();const n=event.key==='Home'?0:event.key==='End'?ids.length-1:(index+(event.key==='ArrowRight'?1:-1)+ids.length)%ids.length;
        this.select(ids[n],true);
      }
      if(event.key==='Delete'){event.preventDefault();this.hide(tab.dataset.dockTab);}
    });
    this.listen(this.root,'pointerdown',event=>this.beginDrag(event));
    this.listen(window,'resize',()=>{cancelAnimationFrame(this.sizeFrame);this.sizeFrame=requestAnimationFrame(()=>{this.motion.cancelLayout();this.render();});});
    this.listen(document,'keydown',event=>{if(event.key==='Escape'){if(this.drag){event.preventDefault();event.stopPropagation();this.finishDrag(true);}else if(this.compactOpen&&innerWidth<1180){this.compactOpen=false;this.render();}}},true);
  }
  beginDrag(event){
    if(event.button!==0||event.isPrimary===false||event.target.closest('.resize-handle'))return;
    const resize=event.target.closest('[data-floating-resize]');if(resize){this.resizeFloat(event,resize.dataset.floatingResize);return;}
    const float=event.target.closest('[data-floating-panel]');if(float)this.raiseFloat(float.dataset.floatingPanel);
    const grip=event.target.closest('[data-dock-start]');
    const heading=event.target.closest('[data-dock-handle]');
    if(!grip&&(!heading||event.target.closest('button,input,textarea,select,a')))return;
    const id=grip?.dataset.dockStart||heading?.dataset.dockHandle;if(!this.panels[id])return;
    const original=this.state.floating[id]?{...this.state.floating[id]}:null,rect=(this.floats[id]||this.panels[id]).getBoundingClientRect();
    const start={id,x:event.clientX,y:event.clientY,clientX:event.clientX,clientY:event.clientY,offsetX:event.clientX-rect.left,offsetY:event.clientY-rect.top,width:rect.width,height:rect.height,original,pointerId:event.pointerId,started:false,target:null};this.drag=start;
    const move=e=>{
      if(this.drag!==start)return;
      if(!start.started&&Math.hypot(e.clientX-start.x,e.clientY-start.y)<6)return;
      if(!start.started){start.started=true;this.targets.hidden=false;this.ghost.hidden=!!original;this.ghost.innerHTML=icon(PANEL_ICONS[id])+`<span>${PANEL_LABELS[id]}</span><kbd>esc</kbd>`;document.body.classList.add('docking-drag');}
      start.clientX=e.clientX;start.clientY=e.clientY;start.screenX=e.screenX;start.screenY=e.screenY;
      if(original){this.state.floating[id]=this.floatBounds(id,{...original,x:original.x+e.clientX-start.x,y:original.y+e.clientY-start.y});this.placeFloat(id);}
      e.preventDefault();this.ghost.style.transform=`translate(${Math.min(innerWidth-230,e.clientX+18)}px,${Math.min(innerHeight-58,e.clientY+18)}px)`;
      let target=null;
      for(const el of this.targets.querySelectorAll('[data-drop-side]')){const r=el.getBoundingClientRect();const hit=e.clientX>=r.left&&e.clientX<=r.right&&e.clientY>=r.top&&e.clientY<=r.bottom;el.classList.toggle('target-active',hit);if(hit)target=el.dataset.dropSide;}
      if(!target){const underneath=document.elementFromPoint(e.clientX,e.clientY)?.closest('[data-dock-side]');target=underneath?.dataset.dockSide||null;}
      start.target=target;
    };
    const capture=event.target;try{capture.setPointerCapture(event.pointerId);}catch(_){}
    const up=e=>{start.clientX=e.clientX;start.clientY=e.clientY;start.screenX=e.screenX;start.screenY=e.screenY;this.finishDrag(false);},cancel=()=>this.finishDrag(true);
    start.cleanup=()=>{try{capture.releasePointerCapture(event.pointerId);}catch(_){}window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',up);window.removeEventListener('pointercancel',cancel);window.removeEventListener('blur',cancel);};
    window.addEventListener('pointermove',move,{passive:false});window.addEventListener('pointerup',up);window.addEventListener('pointercancel',cancel);window.addEventListener('blur',cancel);
  }
  finishDrag(cancelled){
    const drag=this.drag;if(!drag)return;drag.cleanup();this.drag=null;
    this.targets.hidden=true;this.ghost.hidden=true;document.body.classList.remove('docking-drag');
    this.targets.querySelectorAll('.target-active').forEach(el=>el.classList.remove('target-active'));
    if(drag.started){
      this.suppressClick=true;setTimeout(()=>this.suppressClick=false,0);
      if(cancelled){if(drag.original){this.state.floating[drag.id]=drag.original;this.placeFloat(drag.id);}return;}
      if(this.onDetach&&outsideViewport(drag.clientX,drag.clientY,innerWidth,innerHeight)){
        if(drag.original){this.state.floating[drag.id]=drag.original;this.placeFloat(drag.id);}
        this.onDetach(drag.id,{x:drag.screenX-40,y:drag.screenY-24});return;
      }
      if(drag.target)this.move(drag.id,drag.target);
      else {const area=this.root.getBoundingClientRect();if(drag.clientX>=area.left&&drag.clientX<=area.right&&drag.clientY>=area.top&&drag.clientY<=area.bottom)this.floatPanel(drag.id,{x:drag.clientX-area.left-drag.offsetX,y:drag.clientY-area.top-drag.offsetY,width:drag.width,height:drag.height});else if(drag.original){this.state.floating[drag.id]=drag.original;this.placeFloat(drag.id);}}
    }
  }
  dispose(){this.finishDrag(true);cancelAnimationFrame(this.sizeFrame);this.listeners.forEach(remove=>remove());this.ghost.remove();}
}
