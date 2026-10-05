import {icon,escapeHTML as esc} from './icons.js';
const $=s=>document.querySelector(s);

export class DesktopWorkflows{
  constructor(host){this.host=host;this.shared=new Map();this.pending=new Set();this.applying=false;this.disposed=false;this.query=new URLSearchParams(location.search);this.channel=new BroadcastChannel('lumen-native-panels');}
  async init(){
    const h=this.host;
    const bar=document.createElement('div');bar.className='editor-workflows';
    bar.innerHTML=`<button class="icon-button" data-action="split-editor" title="Dividir editor · Ctrl+\\" aria-label="Dividir editor">${icon('split')}</button><button class="icon-button" data-action="detach-editor" title="Editor en otra ventana" aria-label="Editor en otra ventana">${icon('arrow-up-right')}</button>`;
    $('.editor-tabbar').append(bar);
    // Keep the preference and action IDs stable for profiles from early R7 builds.
    const hacker=document.createElement('button');hacker.className='hacker-toggle forge-toggle';hacker.dataset.action='forge-window';hacker.title='Abrir Forge en su propia ventana';hacker.innerHTML=icon('build')+'<span>Forge</span>'+icon('arrow-up-right');$('.top-actions').prepend(hacker);
    this.hackerBar=document.createElement('section');this.hackerBar.className='hacker-bar forge-dashboard';this.hackerBar.setAttribute('aria-label','Forge · ejecución y depuración');
    this.hackerBar.innerHTML=`<div class="forge-main"><div class="forge-identity"><span class="forge-mark">${icon('build')}</span><div><strong>Forge</strong><small>Ejecuta. Inspecciona. Itera.</small></div></div><div class="forge-context">${icon('file')}<span class="forge-file"></span><span class="forge-buffer"></span></div><div class="forge-actions"><button class="forge-action forge-python" data-action="hacker-python">${icon('play')}<span><strong>Ejecutar Python</strong><small>Búfer actual · terminal integrada</small></span></button><button class="forge-action forge-gdb" data-action="hacker-gdb">${icon('bug')}<span><strong>Compilar y depurar C</strong><small>GCC → GDB · pausa en main</small></span></button></div></div><div class="forge-footer"><div class="forge-tools" aria-label="Herramientas detectadas"></div><span class="forge-status" role="status"></span><button class="icon-button forge-refresh" data-action="forge-refresh" title="Volver a detectar herramientas" aria-label="Volver a detectar herramientas">${icon('refresh')}</button><button class="forge-placement" data-action="forge-window">${icon('arrow-up-right')}<span>Otra ventana</span></button></div><div class="forge-guide"></div>`;
    $('#terminal-panel').prepend(this.hackerBar);this.paintHacker();await this.refreshForgeTools();
    const appearance=h.platform.onAppearance;h.platform.onAppearance=()=>{appearance?.();this.paintHacker();};
    const old=h.editor.callbacks.change;h.editor.callbacks.change=(path,...args)=>{old?.(path,...args);this.paintHacker();if(!this.applying&&this.shared.has(path))this.queue(path);};
    const renderTerminal=h.platform.renderActiveTerminal;h.platform.renderActiveTerminal=(...args)=>{renderTerminal?.apply(h.platform,args);this.paintHacker();};
    this.channel.onmessage=e=>this.safe(async()=>{if(e.data.type==='workspace-changed'&&this.query.has('panel')){this.freezeWorkspace();return;}if(e.data.workspace!==h.service().workspace)return;if(e.data.type==='open'&&!this.query.has('panel'))await h.openFile(e.data.path);if(e.data.type==='active'&&e.data.path&&this.query.get('panel')==='assistant')await h.openFile(e.data.path);if(e.data.type==='active'&&this.query.get('panel')==='forge')await this.followForgeFile(e.data.path);if(e.data.type==='forge-terminal'&&!this.query.has('panel'))await this.openForgeTerminal();});
    if(!this.query.has('panel')){const active=h.editor.callbacks.active;h.editor.callbacks.active=(path,...args)=>{active?.(path,...args);this.activeFile(path);};}
    for(const [panel,node] of Object.entries(h.dock.panels)){
      const b=document.createElement('button');b.className='icon-button';b.title='Abrir '+{project:'Proyecto',assistant:'asistente',console:'terminal'}[panel]+' en el escritorio';b.setAttribute('aria-label',b.title);b.innerHTML=icon('arrow-up-right');b.onclick=()=>this.safe(()=>this.detach(panel));node.querySelector(panel==='console'?'.terminal-tools':'.heading-actions').append(b);
    }
    this.returned=e=>{if(e.detail.panel==='forge'){this.forgeWindowOpen=false;return;}if(e.detail.panel!=='editor'){h.dock.nativeDetached.delete(e.detail.panel);h.dock.show(e.detail.panel);}};window.addEventListener('lumen:native-return',this.returned);
    this.detachEditor=e=>this.safe(()=>this.detach(e.detail?.panel||'editor',e.detail?.path||h.editor.current,e.detail?.position));window.addEventListener('lumen:detach-editor',this.detachEditor);
    h.dock.onDetach=(panel,position)=>this.safe(()=>this.detach(panel,'',position));
    h.commands.push(['split-editor','layout','Editor: ver dos archivos a la vez','Ctrl \\'],['close-split-editor','close','Editor: cerrar división',''],['detach-editor','plus','Editor: sacar al escritorio',''],['forge-window','build','Forge: abrir en otra ventana',''],['forge-terminal','terminal','Forge: abrir en la terminal integrada',''],['hacker','build','Forge: activar / desactivar controles',''],['hacker-python','play','Forge: ejecutar Python desde el búfer',''],['hacker-gdb','bug','Forge: compilar C y abrir GDB integrado',''],['updates','download','Lumen: comprobar actualizaciones de GitHub','']);
    if(this.query.has('panel'))await this.detached();
    this.pollBuffers();this.pollUpdates();
  }
  safe(fn){return Promise.resolve().then(fn).catch(e=>this.host.notify(e.message,'error'));}
  paintHacker(){
    const h=this.host,enabled=this.query.get('panel')==='forge'||!!h.platform.prefs['hacker.enabled'],path=this.forgeNoFile?'':h.editor.current||'',dirty=path&&h.editor.isDirty(path),tools=this.forgeTools;
    this.hackerBar.hidden=!enabled;document.documentElement.classList.toggle('hacker-mode',enabled);$('.hacker-toggle')?.setAttribute('aria-pressed',String(enabled));
    const file=this.hackerBar.querySelector('.forge-file');file.textContent=path||'Abre un archivo para comenzar';file.title=path;
    const buffer=this.hackerBar.querySelector('.forge-buffer');buffer.textContent=path?(dirty?'Sin guardar':'Búfer actual'):'';buffer.dataset.dirty=String(!!dirty);buffer.hidden=!path;
    for(const [mode,selector,valid] of [['python','.forge-python',/\.pyw?$/i.test(path)],['gdb','.forge-gdb',/\.c$/i.test(path)]]){
      const button=this.hackerBar.querySelector(selector),available=mode==='python'?tools?.python:tools?.gcc&&tools?.gdb;
      button.disabled=!!this.forgeBusy||!!this.forgeFollowing||!!this.staleWorkspace||!valid||!available;
      button.title=this.forgeBusy?'Espera a que termine la preparación.':!valid?(mode==='python'?'Abre un archivo .py o .pyw.':'Abre un archivo .c.'):!tools?'Detectando herramientas…':!available?'Instala GCC y GDB desde Lenguajes y herramientas.':'Ejecutar el texto del editor sin guardar el archivo';
    }
    this.hackerBar.querySelector('.forge-tools').innerHTML=['python','gcc','gdb'].map(name=>`<span class="forge-tool ${tools?.[name]?'available':'missing'}" title="${esc(tools?.[name]||(!tools?'Detectando…':'No se ha encontrado. Configura su ruta en Lenguajes y herramientas.'))}">${icon(tools?.[name]?'check':'minus')}<span>${name==='python'?'Python integrado':name.toUpperCase()}</span></span>`).join('');
    const run=this.forgeRun,terminal=run?.terminal&&h.platform.terminals.get(run.terminal),closed=run?.terminal&&(!terminal||terminal.closed);
    const message=this.forgeBusy?(run.mode==='gdb'?'Compilando con símbolos…':'Preparando Python…'):this.forgeError?'Revisa la salida de tareas':run?(closed?'Sesión finalizada':run.mode==='gdb'?'Depurador preparado':'Python en ejecución'):tools?'Listo para tu código':'Detectando herramientas…';
    const status=this.hackerBar.querySelector('.forge-status');status.textContent=message+(run?' · '+run.path:'');status.title=status.textContent;status.dataset.state=this.forgeError?'error':this.forgeBusy?'busy':closed?'idle':run?'running':'idle';
    this.hackerBar.querySelector('.forge-refresh').disabled=!!this.forgeBusy||!!this.refreshingForge;
    const guide=this.hackerBar.querySelector('.forge-guide');guide.innerHTML=/\.c$/i.test(path)?'<span>Depuración C</span><code>-g3 -O0 -Wall -Wextra -fno-omit-frame-pointer</code><small>En GDB: <b>next</b> · <b>step</b> · <b>print variable</b> · <b>continue</b></small>':'<span>Python</span><small>Entrada interactiva e imports locales. El archivo se guarda cuando tú decides.</small>';
  }
  async refreshForgeTools(){
    this.refreshingForge=true;this.paintHacker();
    try{this.forgeTools=await this.host.platform.api('/hacker');}
    catch(error){this.forgeTools=null;this.host.notify('Forge: '+error.message,'error');}
    finally{this.refreshingForge=false;this.paintHacker();}
  }
  showForgeConsole(){
    const dock=this.host.dock;dock.show('console');
    if(!this.query.has('panel')&&!dock.nativeDetached.has('console')&&!dock.state.floating.console&&dock.state.groups.bottom.includes('console')){
      const height=dock.state.sizes.bottom||dock.limits().bottom.preferred;
      if(height<420)dock.setSize('bottom',420);
    }
  }
  async openForgeTerminal(){
    const h=this.host;if(!h.platform.prefs['hacker.enabled'])await h.platform.savePreference('hacker.enabled',true);
    h.studio.enter();this.showForgeConsole();this.paintHacker();
    if(h.service().trusted){const data=await h.platform.api('/terminals');for(const t of data.sessions)if(t.profile.kind==='hacker'&&!h.platform.terminals.has(t.id))await h.platform.attachTerminal(t);}
  }
  async openForgeWindow(){
    if(this.query.has('panel'))return;
    if(!this.host.platform.prefs['hacker.enabled'])await this.host.platform.savePreference('hacker.enabled',true);
    this.paintHacker();const path=this.host.editor.current;if(path)await this.share(path);
    const api=window.pywebview?.api;
    if(api?.detach_panel)await api.detach_panel('forge',path||'');
    else{
      const url=new URL(location.href);url.search=new URLSearchParams({panel:'forge',file:path||''});
      const child=window.open(url.href,'lumen-forge','width=940,height=760');if(!child)throw Error('Permite las ventanas emergentes para abrir Forge.');
      const timer=setInterval(()=>{if(child.closed){clearInterval(timer);this.forgeWindowOpen=false;}},800);
    }
    this.forgeWindowOpen=true;this.activeFile(path);
  }
  async followForgeFile(path){
    this.forgeNoFile=!path;if(!path){this.paintHacker();return;}
    this.forgeFollowing=true;this.paintHacker();
    try{
      await this.host.openFile(path);const data=await this.host.platform.api('/buffers'),remote=data.buffers.find(x=>x.path===path);
      if(remote){this.shared.set(path,remote);this.applying=true;try{this.host.editor.insertText(remote.text,true);}finally{this.applying=false;}}
    }finally{this.forgeFollowing=false;this.paintHacker();}
  }
  async handle(action){
    const h=this.host;
    if(action==='split-editor'){h.studio.enter();const paths=[...h.editor.models.keys()],path=paths.find(p=>p!==h.editor.current)||h.editor.current;if(!path)throw Error('Abre un archivo para dividir el editor.');h.editor.split(path);return true;}
    if(action==='close-split-editor'){h.editor.closeSplit();return true;}
    if(action==='detach-editor'){await this.detach('editor',h.editor.current);return true;}
    if(action==='hacker'){const enabled=!h.platform.prefs['hacker.enabled'];await h.platform.savePreference('hacker.enabled',enabled);this.paintHacker();if(enabled){h.studio.enter();this.showForgeConsole();await this.refreshForgeTools();}return true;}
    if(action==='forge-window'){await this.openForgeWindow();return true;}
    if(action==='forge-terminal'){
      if(this.query.get('panel')==='forge'){this.channel.postMessage({type:'forge-terminal',workspace:h.service().workspace});if(window.pywebview?.api?.close_forge)await window.pywebview.api.close_forge();else window.close();}
      else await this.openForgeTerminal();return true;
    }
    if(action==='forge-refresh'){await this.refreshForgeTools();return true;}
    if(action==='hacker-python'||action==='hacker-gdb'){await this.runHacker(action==='hacker-python'?'python':'gdb');return true;}
    if(action==='updates'){await this.updatesPage(true);return true;}
    return false;
  }
  async runHacker(mode){
    if(this.forgeBusy||this.forgeFollowing)return;
    const h=this.host,path=h.editor.current,content=h.editor.getValue();if(!path)throw Error('Abre el archivo que quieres ejecutar.');if(!await h.ensureTrust())return;
    this.forgeBusy=true;this.forgeError=false;this.forgeRun={mode,path};
    try{
      if(!h.platform.prefs['hacker.enabled'])await h.platform.savePreference('hacker.enabled',true);
      h.studio.enter();this.showForgeConsole();this.paintHacker();
      const result=await h.platform.api('/hacker/start',{mode,path,content});
      if(result.terminal){await h.platform.attachTerminal(result.terminal);this.forgeRun.terminal=result.terminal.id;return;}
      h.showConsole();await h.watchJob(result.job,path);
      const terminal=await h.platform.api('/hacker/attach',{job:result.job});await h.platform.attachTerminal(terminal);this.forgeRun.terminal=terminal.id;
      h.notify('Forge · GDB listo en main. Usa next, step, print variable, continue o quit.');
    }catch(error){this.forgeError=true;throw error;}
    finally{this.forgeBusy=false;this.paintHacker();}
  }
  async detach(panel,path='',position){
    const h=this.host,api=window.pywebview?.api;
    if(panel==='editor'&&!path)throw Error('Abre un archivo para separarlo.');
    if(panel==='editor'||panel==='assistant'){
      const target=path||h.editor.current;if(target)await this.share(target);path=target||'';
    }
    if(api?.detach_panel)await api.detach_panel(panel,path,position||null);
    else{
      const url=new URL(location.href);url.search=new URLSearchParams({panel,file:path});
      const child=window.open(url.href,'_blank','width=900,height=760');if(!child)throw Error('Permite las ventanas emergentes para separar el panel.');
      const timer=setInterval(()=>{if(child.closed){clearInterval(timer);if(panel!=='editor')h.dock.show(panel);}},800);
    }
    if(panel!=='editor'){h.dock.nativeDetached.add(panel);h.dock.hide(panel);}
  }
  activeFile(path){this.paintHacker();if(this.query.has('panel'))return;this.safe(async()=>{if(path&&(this.forgeWindowOpen||this.host.dock.nativeDetached.has('assistant')))await this.share(path);this.channel.postMessage({type:'active',path,workspace:this.host.service().workspace});});}
  openInParent(path){this.channel.postMessage({type:'open',path,workspace:this.host.service().workspace});}
  workspaceChanged(){this.shared.clear();this.pending.clear();this.channel.postMessage({type:'workspace-changed',workspace:this.host.service().workspace});}
  freezeWorkspace(){
    if(this.staleWorkspace)return;this.staleWorkspace=true;this.disposed=true;clearTimeout(this.publishTimer);clearTimeout(this.bufferTimer);clearTimeout(this.updateTimer);
    for(const pane of this.host.editor.panes)pane.view.updateOptions({readOnly:true});
    this.paintHacker();
    const notice=document.createElement('div');notice.className='native-workspace-notice';notice.textContent='La carpeta cambió en la ventana principal. Tu texto permanece aquí: cópialo antes de cerrar y vuelve a abrir el panel.';$('#app').prepend(notice);
  }
  bufferWrite(fn){const request=(this.bufferWrites||Promise.resolve()).catch(()=>{}).then(fn);this.bufferWrites=request;return request;}
  share(path){return this.bufferWrite(()=>this.shareUnlocked(path));}
  async shareUnlocked(path){
    const r=this.host.editor.models.get(path);if(!r)return;
    const all=await this.host.platform.api('/buffers'),old=all.buffers.find(x=>x.path===path);
    const text=r.model?.getValue()??r.value;
    if(old&&old.text!==text&&this.shared.has(path)&&old.sequence!==this.shared.get(path).sequence)throw Error('Hay cambios pendientes de otra ventana. Resuelve la sincronización antes de separarlo.');
    const result=await this.host.platform.api('/buffers',{path,text,sequence:old?.sequence||0,saved:!this.host.editor.isDirty(path),revision:r.revision});
    if(result.conflict)throw Error('Otra ventana acaba de editar este archivo. Repite la acción.');this.shared.set(path,result.buffer);
  }
  queue(path){this.pending.add(path);clearTimeout(this.publishTimer);this.publishTimer=setTimeout(()=>this.safe(()=>this.publish()),100);}
  publish(){return this.bufferWrite(()=>this.publishUnlocked());}
  async publishUnlocked(){
    if(this.publishing)return;this.publishing=true;
    try{for(const path of [...this.pending]){
      this.pending.delete(path);const r=this.host.editor.models.get(path),base=this.shared.get(path);if(!r||!base)continue;
      const text=r.model?.getValue()??r.value,saved=!this.host.editor.isDirty(path);if(text===base.text&&saved===base.saved)continue;
      const result=await this.host.platform.api('/buffers',{path,text,sequence:base.sequence,saved,revision:r.revision});
      if(result.conflict){this.shared.delete(path);this.host.notify('Ediciones simultáneas en '+path+'. Tu búfer se conserva; compara las dos ventanas antes de guardar.','error');}
      else this.shared.set(path,result.buffer);
      if((r.model?.getValue()??r.value)!==text&&this.shared.has(path))this.pending.add(path);
    }}finally{this.publishing=false;if(this.pending.size)this.publishTimer=setTimeout(()=>this.safe(()=>this.publish()),100);}
  }
  async pollBuffers(){
    if(this.disposed)return;
    try{
      const data=await this.host.platform.api('/buffers');
      for(const remote of data.buffers){
        const r=this.host.editor.models.get(remote.path);if(!r)continue;
        const old=this.shared.get(remote.path),text=r.model?.getValue()??r.value;
        if(this.pending.has(remote.path)||this.publishing)continue;
        if(old&&remote.sequence<=old.sequence)continue;
        if(old&&text!==old.text){this.queue(remote.path);continue;}
        if(!old&&this.host.editor.isDirty(remote.path)&&text!==remote.text)continue;
        this.shared.set(remote.path,remote);
        this.applying=true;try{if(text!==remote.text){if(r.model){r.model.pushStackElement();r.model.pushEditOperations([],[{range:r.model.getFullModelRange(),text:remote.text}],()=>null);r.model.pushStackElement();}else{r.value=remote.text;if(this.host.editor.current===remote.path)this.host.editor.setValue(remote.text);}}if(remote.saved){r.savedValue=remote.text;if(remote.revision)r.revision=remote.revision;r.value=remote.text;this.host.editor.callbacks.change?.(remote.path,false);}}finally{this.applying=false;}
      }
    }catch(error){if(!this.disposed)console.warn('Window sync:',error.message);}
    this.bufferTimer=setTimeout(()=>this.pollBuffers(),this.query.has('panel')?250:400);
  }
  async detached(){
    const panel=this.query.get('panel'),h=this.host;
    if(!['project','assistant','console','editor','forge'].includes(panel))return;
    h.studio.enter();document.documentElement.dataset.detachedPanel=panel;
    if(this.query.get('file')){
      await h.openFile(this.query.get('file'));
      const data=await h.platform.api('/buffers'),remote=data.buffers.find(x=>x.path===h.editor.current);
      if(remote){this.shared.set(remote.path,remote);this.applying=true;h.editor.insertText(remote.text,true);this.applying=false;}
    }
    if(panel!=='editor'){const node=h.dock.panels[panel==='forge'?'console':panel];node.classList.add('native-detached-content');node.hidden=false;node.inert=false;node.removeAttribute('aria-hidden');$('#app').append(node);}
    if(panel==='forge'){const button=this.hackerBar.querySelector('.forge-placement');button.dataset.action='forge-terminal';button.innerHTML=icon('dock-bottom')+'<span>Integrar en Lumen</span>';this.paintHacker();}
    if(panel==='console'||panel==='forge'){
      if(h.service().trusted){const data=await h.platform.api('/terminals');for(const terminal of data.sessions)if((panel!=='forge'||terminal.profile.kind==='hacker')&&!h.platform.terminals.has(terminal.id))await h.platform.attachTerminal(terminal);}
    }
  }
  async pollUpdates(){
    if(this.disposed)return;
    try{this.updateState=await this.host.platform.api('/updates');
      if(this.updateState.status==='ready'&&!this.readyNotified&&!this.query.has('panel')){this.readyNotified=true;this.host.notify('Actualización '+this.updateState.available.version+' descargada. Abre «Lumen: comprobar actualizaciones» para instalarla.', 'info',9000);}
      if($('#update-status'))this.renderUpdate();
    }catch(_){/* Network failures remain visible in the update page. */}
    this.updateTimer=setTimeout(()=>this.pollUpdates(),2500);
  }
  async updatesPage(check=false){
    const h=this.host;h.platform.openPage('updates',`<section class="updates-page"><span class="eyebrow">EDRYVO · ACTUALIZACIONES</span><h1>Tu espacio, al día.</h1><p>Las versiones publicadas en GitHub se descargan en segundo plano y se verifican con SHA-256.</p><div id="update-status" role="status"></div><div class="update-actions"><button class="secondary-button" id="update-check">Comprobar ahora</button><button class="secondary-button" id="update-download">Descargar actualización</button><button class="primary-button" id="update-install">Instalar actualización…</button></div><label class="setting-row"><span>Descarga automática<small>Comprueba al iniciar y cada seis horas.</small></span><input id="automatic-updates" type="checkbox" ${h.platform.prefs['updates.automatic']?'checked':''}></label><small>El instalador se abre cuando tú eliges. Guarda tus archivos antes de actualizar.</small></section>`);
    $('#update-check').onclick=()=>this.safe(async()=>{this.updateState=await h.platform.api('/updates/check',{download:h.platform.prefs['updates.automatic']});this.renderUpdate();});
    $('#update-download').onclick=()=>this.safe(async()=>{this.updateState=await h.platform.api('/updates/download',{});this.renderUpdate();});
    $('#update-install').onclick=()=>this.safe(async()=>{if(!window.pywebview?.api?.install_update)throw Error('La instalación de actualizaciones está disponible en Lumen de escritorio.');await window.pywebview.api.install_update();});
    $('#automatic-updates').onchange=e=>this.safe(()=>h.platform.savePreference('updates.automatic',e.target.checked));
    this.updateState=check?await h.platform.api('/updates/check',{download:h.platform.prefs['updates.automatic']}):await h.platform.api('/updates');this.renderUpdate();
  }
  renderUpdate(){
    const s=this.updateState;if(!s||!$('#update-status'))return;
    const labels={idle:'Pendiente de comprobar',checking:'Buscando en GitHub…',available:'Nueva versión disponible',up_to_date:'Tienes la versión más reciente',downloading:'Descargando y verificando…',ready:'Lista para instalar',error:'No se pudo completar la actualización'};
    $('#update-status').innerHTML=`<strong>${esc(labels[s.status])}</strong><p>${esc(s.current)}${s.available?' → '+esc(s.available.version):''}</p>${s.transfer?`<progress max="${s.transfer.total||s.available.size}" value="${s.transfer.bytes}"></progress><small>${(s.transfer.bytes/1e6).toFixed(1)} / ${(s.available.size/1e6).toFixed(1)} MB</small>`:''}${s.error?`<p role="alert">${esc(s.error)}</p>`:''}`;
    $('#update-download').disabled=!s.available||['ready','downloading'].includes(s.status);$('#update-install').disabled=s.status!=='ready';
  }
  dispose(){this.disposed=true;this.channel.close();clearTimeout(this.publishTimer);clearTimeout(this.bufferTimer);clearTimeout(this.updateTimer);window.removeEventListener('lumen:native-return',this.returned);window.removeEventListener('lumen:detach-editor',this.detachEditor);}
}
