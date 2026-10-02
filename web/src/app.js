import {installExplorerMenu} from './explorer-menu.js';
import './controls.js';
import {installPreview} from './preview.js';
import {icon,renderIcons,escapeHTML as esc,fileIcon} from './icons.js';
import {LumenEditor,languageLabel,languageFor} from './editor.js';
import {createLumenScene} from './glass.js';
import {LenonStudio} from './studio.js';
import {LumenMotion} from './motion.js';
import {DockManager} from './docking.js';
import {PRESET_NAMES,sideOf} from './layout-state.js';
import {installInteractions} from './interactions.js';
import {LumenPlatform} from './workbench.js';

const motion=new LumenMotion();
let dock=null,polish=null,platformUI=null,studio=null,previewUI=null,tabsSignature='';

const $=selector=>document.querySelector(selector);
const $$=selector=>[...document.querySelectorAll(selector)];
let token='',service=null,editor=null,scene=null,sceneStatus='CSS fallback',activeView='explorer';
let tree=[],rootExpanded=true,openFolders=new Set(['Assets','Assets/Scripts','Assets/Scenes','Assets/Prefabs','Settings']);
let cwd='',terminalHistory=[],historyIndex=0,activeJob=null,terminalMode='terminal',lastOutput='';
let aiBusy=false,aiConsent=false,notifications=[],paletteEntries=[],paletteIndex=0,paletteRequest=0;
let popoverAnchor=null,modalResolve=null,previousFocus=null;
const defaultSettings={fontSize:12.5,tabSize:4,minimap:true,wordWrap:false,motion:true,density:'comfortable'};
let settings={...defaultSettings};
try{Object.assign(settings,JSON.parse(localStorage.getItem('lumen.settings')||'{}'));}catch(_){/* Use defaults if local storage is unavailable. */}
settings.fontSize=Math.min(22,Math.max(11,Number(settings.fontSize)||12.5));

function persist(){try{localStorage.setItem('lumen.settings',JSON.stringify(settings));}catch(_){}}
async function api(path,body) {
  const options={credentials:'same-origin',headers:{'X-Lumen-Token':token}};
  if(body!==undefined){options.method='POST';options.headers['Content-Type']='application/json';options.body=JSON.stringify(body);}
  const controller=new AbortController();options.signal=controller.signal;const deadline=setTimeout(()=>controller.abort(),35000);let response;try{response=await fetch('/api'+path,options);}catch(error){if(error.name==='AbortError')throw new Error('La operación está tardando demasiado. Puedes seguir trabajando; revisa su estado antes de repetirla.');throw error;}finally{clearTimeout(deadline);}
  const data=await response.json();
  if(!response.ok){const error=new Error(data.error||`Request failed (${response.status})`);error.status=response.status;throw error;}
  return data;
}
function notify(message,type='info',duration=5000){
  const toast=document.createElement('div');toast.className='toast'+(type==='error'?' error':'');
  toast.innerHTML=icon(type==='error'?'warning':'info')+`<span>${esc(message)}</span>`;$('#toasts').appendChild(toast);motion.enter(toast,6);
  setTimeout(()=>toast.remove(),duration);
  notifications.unshift({message,type,time:new Date().toLocaleTimeString()});notifications=notifications.slice(0,25);
  $('#notification-dot').classList.remove('hidden');
}
const guard=fn=>(...args)=>{try{return Promise.resolve(fn(...args)).catch(error=>notify(error.message,'error',6500));}catch(error){notify(error.message,'error',6500);}};
function allFiles(nodes=tree){return nodes.flatMap(node=>node.directory?allFiles(node.children||[]):[node.path]);}
function currentRecord(){return editor?.models.get(editor.current);}
function closePopover(){$('#popover').classList.add('hidden');popoverAnchor=null;}

function applyTheme(theme,persistTheme=true) {
  if(persistTheme&&platformUI&&platformUI.prefs['appearance.theme']!==theme)return guard(()=>platformUI.savePreference('appearance.theme',theme))();
  if(!['day','dark','forest'].includes(theme))return;
  const changed=document.documentElement.dataset.theme!==theme;
  if(changed)motion.theme();document.documentElement.dataset.theme=theme;
  if(persistTheme){try{localStorage.setItem('lumen.theme',theme);}catch(_){}}
  const landscapePath=`/assets/landscape-${theme}.png`;
  $('#landscape').src=window.LUMEN_ASSETS?.[landscapePath]||landscapePath;
  const titles={day:'Light,<br>clarity, flow.',dark:'Build<br>brighter<br>tomorrow.',forest:'Build<br>brighter<br>worlds.'};
  $('#landscape-title').innerHTML=titles[theme];
  $('#landscape-caption').innerHTML=theme==='day'?'Build something<br>brighter.':'A little space<br>to think.';
  $('#theme-trigger').innerHTML=icon({day:'sun',dark:'moon',forest:'leaf'}[theme]);
  $('#theme-trigger').setAttribute('aria-label','Tema: '+{day:'día',dark:'oscuro',forest:'bosque'}[theme]);
  scene?.setTheme(theme);if(changed)editor?.changedTheme();
  try{localStorage.setItem('lumen.theme',theme);}catch(_){}
  $$('.theme-card').forEach(card=>card.classList.toggle('selected',card.dataset.theme===theme));
}
function applySettings(){
  persist();editor?.applySettings(settings);
  document.documentElement.dataset.motion=settings.motion?'on':'off';document.documentElement.dataset.density=settings.density==='compact'?'compact':'comfortable';if(!motion.enabled)motion.cancelAll();scene?.setMotion(settings.motion);
}

function treeMarkup(nodes,depth=0){
  return nodes.map(node=>{
    const isOpen=openFolders.has(node.path),selected=editor?.current===node.path;
    const indent=16+depth*20;
    if(node.directory)return `<div class="tree-node"><button class="tree-row" data-dir="${esc(node.path)}" style="padding-left:${indent}px" aria-expanded="${isOpen}"><span class="tree-chevron">${icon(isOpen?'chevron-down':'chevron-right')}</span><span class="folder-icon">${icon('folder')}</span><span class="label">${esc(node.name)}</span></button><div class="tree-children${isOpen?'':' closed'}">${treeMarkup(node.children||[],depth+1)}</div></div>`;
    return `<button class="tree-row${selected?' active':''}" data-file="${esc(node.path)}" title="${esc(node.path)}" style="padding-left:${indent+20}px">${fileIcon(node.path)}<span class="label">${esc(node.name)}</span></button>`;
  }).join('');
}
function renderTree(){
  if(activeView!=='explorer')return;
  $('#sidebar-title').textContent=platformUI?.t('Proyecto','Project')||'Project';
  $('#sidebar-content').innerHTML=`<button class="tree-root" data-action="toggle-root" aria-expanded="${rootExpanded}">${icon(rootExpanded?'chevron-down':'chevron-right')}${icon('folder-open')}<span>${esc(service?.name||'MyProject')}</span></button><div class="tree-children${rootExpanded?'':' closed'}">${treeMarkup(tree)}</div>`;
}
async function refreshTree(){const data=await api('/tree');tree=data.tree;service.name=data.name;renderTree();}
function revealFile(path){
  const parts=path.split('/');parts.pop();let parent='';for(const part of parts){parent=parent?parent+'/'+part:part;openFolders.add(parent);}
  rootExpanded=true;
}
async function openFile(path,line=null){
  studio?.enter();
  if(platformUI?.page)platformUI.closePage();
  if(!editor.models.has(path)){const item=await api('/file?path='+encodeURIComponent(path));editor.open(item);}
  else editor.activate(path);
  revealFile(path);renderTabs();renderTree();updateDocumentStatus();
  if(line)editor.showLine(line);
  studio?.remember(path);previewUI?.activeChanged();
}
function renderTabs(){
  const signature=JSON.stringify([...editor.models.keys()].map(path=>[path,path===editor.current,editor.isDirty(path)]));
  if(signature===tabsSignature)return;tabsSignature=signature;
  const previousTabs=new Set([...$('#file-tabs').querySelectorAll('[data-tab]')].map(el=>el.dataset.tab));
  $('#file-tabs').innerHTML=[...editor.models.values()].map(item=>`<button class="file-tab${item.path===editor.current?' active':''}" role="tab" tabindex="${item.path===editor.current?0:-1}" aria-selected="${item.path===editor.current}" draggable="true" aria-controls="editor-mount" data-tab="${esc(item.path)}" title="${esc(item.path)}">${fileIcon(item.path)}<span class="file-label">${esc(item.path.split('/').pop())}</span><span class="tab-close" data-close-file="${esc(item.path)}" aria-label="Cerrar archivo">${editor.isDirty(item.path)?'<i class="dirty-dot"></i>':icon('close')}</span></button>`).join('');
  previewUI?.renderGroups();
  for(const tab of $('#file-tabs').querySelectorAll('[data-tab]'))if(!previousTabs.has(tab.dataset.tab))motion.enter(tab,3);
  const empty=editor.models.size===0;$('#editor-empty').classList.toggle('hidden',!empty);
  $('#editor-mount').style.visibility=empty?'hidden':'visible';
  document.title=(editor.current?editor.current.split('/').pop()+' · ':'')+'Lumen Studio';
  const selected=$('#file-tabs .file-tab.active');
  if(selected){const container=$('#file-tabs'),r=selected.getBoundingClientRect(),b=container.getBoundingClientRect();if(r.right>b.right)container.scrollLeft+=r.right-b.right;else if(r.left<b.left)container.scrollLeft-=b.left-r.left;}

}
function reorderFile(source,target,after=false){
  if(source===target||!editor.models.has(source)||!editor.models.has(target))return;
  const entries=[...editor.models.entries()],moved=entries.find(([path])=>path===source),remaining=entries.filter(([path])=>path!==source);
  remaining.splice(remaining.findIndex(([path])=>path===target)+(after?1:0),0,moved);
  editor.models=new Map(remaining);renderTabs();
}
function activateFile(path){studio?.enter();if(platformUI?.page)platformUI.closePage();editor.activate(path);renderTabs();renderTree();updateDocumentStatus();studio?.remember(path);previewUI?.activeChanged();}
function updateDocumentStatus(){
  const item=currentRecord();
  if(!item){$('#breadcrumbs').replaceChildren();$('#breadcrumbs').hidden=true;$('#language-status').textContent='';$('#target-label').textContent='';$('#cursor-status').textContent='';return;}
  $('#breadcrumbs').hidden=false;
  const parts=item.path.replaceAll('\\','/').split('/').filter(Boolean);
  $('#breadcrumbs').innerHTML=parts.map((part,i)=>i===parts.length-1?`${fileIcon(item.path)}<span class="last">${esc(part)}</span>`:`<span>${esc(part)}</span>${icon('chevron-right')}`).join('');
  $('#newline-status').textContent=item.newline||'LF';$('#language-status').textContent=languageLabel(item.path);
  $('#target-label').textContent=languageLabel(item.path);
  updateDiagnostics(editor.diagnostics());platformUI?.documentChanged();
}
async function saveFile(path=editor.current,{automatic=false}={}){
  if(typeof path!=='string')path=editor.current;
  const item=editor.models.get(path);if(!item)return;
  let content=path===editor.current?editor.getValue():item.value;if(platformUI?.prefs['files.trimTrailingWhitespace'])content=content.split('\n').map(line=>line.replace(/[ \t]+$/,'')).join('\n');if(platformUI?.prefs['files.insertFinalNewline']&&!content.endsWith('\n'))content+='\n';if(path===editor.current&&content!==editor.getValue())editor.insertText(content,true);
  item.value=content;
  if(path!==editor.current&&item.model&&item.model.getValue()!==content)item.model.setValue(content);
  const result=await api('/save',{path:item.path,content:item.value,revision:item.revision,newline:item.newline,bom:item.bom});
  editor.markSaved(result);renderTabs();if(platformUI)await platformUI.afterSave(item.path);if(!automatic&&platformUI?.prefs['files.saveNotifications']!==false)notify('Guardado: '+item.path,'info',1600);
  return result;
}
async function closeFile(path){
  if(editor.isDirty(path)){
    const choice=await confirmDialog('Cambios sin guardar',`${path} tiene cambios. Puedes cancelar el cierre o descartarlos. Guarda antes con Ctrl+S para conservarlos.`,'Descartar y cerrar');
    if(!choice)return;
  }
  const list=[...editor.models.keys()],index=list.indexOf(path),wasCurrent=path===editor.current;
  editor.close(path);
  if(wasCurrent&&editor.models.size)editor.activate(list[index+1]||list[index-1]);
  renderTabs();renderTree();updateDocumentStatus();previewUI?.activeChanged();
}
function updateDiagnostics(items=[]){
  const errors=items.filter(i=>i.severity==='error').length,warnings=items.length-errors;
  $('#error-count').textContent=errors;$('#warning-count').textContent=warnings;$('#problem-count').textContent=items.length;
  if(terminalMode==='problems')renderTerminalContent();
}

function modal(title,content,{wide=false}={}){
  closePopover();previousFocus=document.activeElement;
  $('#modal').classList.toggle('wide',wide);
  $('#modal').innerHTML=`<div class="modal-header"><div><h2 id="modal-title">${esc(title)}</h2></div><button class="icon-button" data-action="close-modal" aria-label="Cerrar">${icon('close')}</button></div>${content}`;
  $('#modal-backdrop').classList.remove('hidden');motion.enter($('#modal'),7);
  requestAnimationFrame(()=>($('#modal').querySelector('input:not([type=checkbox]),select,button.primary-button')||$('#modal').querySelector('button'))?.focus());
}
function closeModal(result=false){
  $('#modal-backdrop').classList.add('hidden');$('#modal').replaceChildren();
  if(modalResolve){const resolve=modalResolve;modalResolve=null;resolve(result);}
  previousFocus?.focus?.();
}
function confirmDialog(title,text,positive='Continuar'){
  modal(title,`<p>${esc(text)}</p><div class="modal-actions"><button class="secondary-button" data-action="close-modal">Cancelar</button><button class="primary-button" id="confirm-yes">${esc(positive)}</button></div>`);
  return new Promise(resolve=>{modalResolve=resolve;$('#confirm-yes').onclick=()=>closeModal(true);});
}
function showErrorInModal(error){let box=$('#modal .error-message');if(!box){box=document.createElement('div');box.className='error-message';$('#modal').appendChild(box);}box.textContent=error.message;}
function newFileDialog(){
  modal('Nuevo archivo',`<p>Se creará dentro de <strong>${esc(service.name)}</strong>. Las rutas relativas permiten organizarlo en subcarpetas.</p><form id="new-file-form"><label class="field-label" for="new-file-name">Nombre o ruta relativa</label><input id="new-file-name" type="text" value="Untitled.py" required autocomplete="off"><div class="modal-actions"><button class="secondary-button" type="button" data-action="close-modal">Cancelar</button><button class="primary-button" type="submit">Crear archivo</button></div></form>`);
  $('#new-file-name').select();
  $('#new-file-form').onsubmit=async event=>{event.preventDefault();try{const name=$('#new-file-name').value.trim();if(!name)throw new Error('Escribe un nombre.');await api('/save',{path:name,content:'',create:true});closeModal();await refreshTree();await openFile(name);editor.focus();}catch(error){showErrorInModal(error);}};
}
async function changeWorkspace(path){
  if([...editor.models.keys()].some(p=>editor.isDirty(p))){const ok=await confirmDialog('Cambios sin guardar','Cambiar de carpeta descartará los cambios no guardados. Guarda primero para conservarlos.','Descartar y abrir');if(!ok)return false;}
  const data=await api('/workspace',{path});service={...service,...data};tree=data.tree;cwd='';platformUI?.workspaceChanged();editor.reset();tabsSignature='';closeModal();activeView='explorer';
  await initializeDocuments();await setView('explorer');updatePrompt();termClear();await checkWorkspace();notify('Carpeta abierta.');return true;
}
async function openWorkspaceDialog(){
  if(window.pywebview?.api?.choose_folder){const path=await window.pywebview.api.choose_folder();if(path)await changeWorkspace(path);return;}
  modal('Abrir carpeta',`<p>Elige la carpeta que contiene tu proyecto.</p><form id="open-workspace-form"><label class="field-label" for="workspace-path">Ruta de la carpeta</label><input id="workspace-path" type="text" value="${esc(service.workspace)}" required autocomplete="off"><div class="modal-actions"><button class="secondary-button" type="button" data-action="close-modal">Cancelar</button><button class="primary-button" type="submit">Abrir carpeta</button></div></form>`);
  $('#open-workspace-form').onsubmit=event=>{event.preventDefault();guard(()=>changeWorkspace($('#workspace-path').value.trim()))();};
}
function layoutSettingsDialog(highlight=null){
  const state=dock.snapshot();
  const panels=[['project','Proyecto','files'],['assistant','Asistente','sparkles'],['console','Consola','terminal']];
  const descriptions={studio:'La composición original, con todo a mano.',code:'Editor y consola. El asistente permanece oculto.',grouped:'Asistente y consola comparten pestañas a la derecha.',focus:'Solo código. Vuelve con Ctrl Alt F.'};
  modal('Cada panel, en su sitio.',`<p>Arrastra una cabecera al centro para dejar el panel flotante o a un borde para acoplarlo. Aquí puedes cerrar y volver a abrir cualquier panel; su contenido se conserva.</p><div class="layout-presets">${Object.entries(PRESET_NAMES).map(([id,label])=>`<button class="layout-preset ${state.preset===id?'selected':''}" data-layout-preset="${id}" aria-pressed="${state.preset===id}"><span class="layout-mini layout-mini-${id}"><i></i><i></i><i></i><i></i></span><strong>${label}</strong><small>${descriptions[id]}</small></button>`).join('')}</div><h3>PANELES Y GRUPOS</h3><div class="panel-placements">${panels.map(([id,label,glyph])=>`<div class="panel-placement ${highlight===id?'highlighted':''}"><span class="placement-icon">${icon(glyph)}</span><label for="place-${id}">${label}<small>Contenido conservado al moverlo</small></label><select id="place-${id}" data-place-panel="${id}" aria-label="Posición de ${label}">${[['left','Izquierda'],['right','Derecha'],['bottom','Abajo'],['floating','Flotante']].map(([side,text])=>`<option value="${side}" ${(state.floating[id]?'floating':sideOf(state,id))===side?'selected':''}>${text}</option>`).join('')}</select><label class="visibility-toggle" title="Mostrar ${label}"><input type="checkbox" data-visible-panel="${id}" aria-label="Mostrar ${label}" ${!state.hidden.includes(id)?'checked':''}><span>Visible</span></label></div>`).join('')}</div><div class="layout-note">${icon('info')}<span>Los paneles en la misma zona se agrupan en pestañas. La distribución y los tamaños se guardan en este equipo. No se modifican archivos del proyecto.</span></div><div class="modal-actions"><button class="secondary-button" id="layout-reset-all">Restaurar Lumen</button><button class="primary-button" data-action="close-modal">Listo</button></div>`,{wide:true});
  const sync=()=>{const next=dock.snapshot();$$('[data-place-panel]').forEach(select=>select.value=next.floating[select.dataset.placePanel]?'floating':sideOf(next,select.dataset.placePanel));$$('[data-visible-panel]').forEach(input=>input.checked=!next.hidden.includes(input.dataset.visiblePanel));$$('[data-layout-preset]').forEach(button=>{const selected=next.preset===button.dataset.layoutPreset;button.classList.toggle('selected',selected);button.setAttribute('aria-pressed',String(selected));});};
  $$('[data-layout-preset]').forEach(button=>button.onclick=()=>{if(button.dataset.layoutPreset==='focus')dock.focus();else dock.preset(button.dataset.layoutPreset);sync();});
  $$('[data-place-panel]').forEach(select=>select.onchange=()=>{if(select.value==='floating')dock.floatPanel(select.dataset.placePanel);else dock.move(select.dataset.placePanel,select.value);sync();});
  $$('[data-visible-panel]').forEach(input=>input.onchange=()=>{input.checked?dock.show(input.dataset.visiblePanel):dock.hide(input.dataset.visiblePanel);sync();});
  $('#layout-reset-all').onclick=()=>{dock.reset();sync();};
}

function appearanceDialog(){
  const selected=document.documentElement.dataset.theme;
  modal('Un espacio para concentrarte.',`<p>Tres ambientes. La misma distribución. Todos los ajustes se conservan en este navegador.</p><h3>APARIENCIA</h3><div class="theme-cards">${[['day','Día','Porcelana · violeta'],['dark','Oscuro','Grafito · lavanda'],['forest','Bosque','Verde profundo · salvia']].map(([id,name,detail])=>`<button class="theme-card${selected===id?' selected':''}" data-theme="${id}"><span class="theme-mini ${id}"><i></i><i></i><i></i></span><strong>${name}</strong><small>${detail}</small></button>`).join('')}</div><h3>ESPACIO DE TRABAJO</h3><label class="setting-row"><span>Navegación compacta<small>Solo iconos; conserva el acceso a todas las herramientas.</small></span><input id="compact-nav-setting" type="checkbox" ${dock.snapshot().railCompact?'checked':''}></label><label class="setting-row"><span>Densidad de interfaz<small>Espaciado del árbol y los controles, sin reducir el texto.</small></span><select id="density-setting"><option value="comfortable" ${settings.density!=='compact'?'selected':''}>Cómoda</option><option value="compact" ${settings.density==='compact'?'selected':''}>Compacta</option></select></label><div class="setting-row"><span>Tamaño del código<small id="font-value">${settings.fontSize} px</small></span><input id="font-setting" type="range" min="11" max="22" step=".5" value="${settings.fontSize}" aria-label="Tamaño del código"></div><label class="setting-row"><span>Minimapa<small>Navegación visual del archivo abierto.</small></span><input id="minimap-setting" type="checkbox" ${settings.minimap?'checked':''}></label><label class="setting-row"><span>Ajuste de línea<small>${editor.kind==='monaco'?'Requiere Monaco; no altera el archivo.':'Disponible tras instalar Monaco.'}</small></span><input id="wrap-setting" type="checkbox" ${settings.wordWrap?'checked':''} ${editor.kind!=='monaco'?'disabled':''}></label><label class="setting-row"><span>Movimiento sutil<small>La esfera se detiene cuando ocultas la pestaña. Respeta movimiento reducido del sistema.</small></span><input id="motion-setting" type="checkbox" ${settings.motion?'checked':''}></label><div class="modal-actions"><button class="secondary-button" id="reset-layout">Restaurar distribución</button><button class="primary-button" data-action="close-modal">Listo</button></div>`,{wide:true});
  $$('.theme-card').forEach(button=>button.onclick=()=>applyTheme(button.dataset.theme));
  $('#compact-nav-setting').onchange=event=>{if(event.target.checked!==dock.snapshot().railCompact)dock.toggleRail();};
  $('#density-setting').onchange=event=>{settings.density=event.target.value;applySettings();};
  $('#font-setting').oninput=event=>{settings.fontSize=+event.target.value;$('#font-value').textContent=settings.fontSize+' px';applySettings();};
  $('#minimap-setting').onchange=event=>{settings.minimap=event.target.checked;applySettings();};
  $('#wrap-setting').onchange=event=>{settings.wordWrap=event.target.checked;applySettings();};
  $('#motion-setting').onchange=event=>{settings.motion=event.target.checked;applySettings();};
  $('#reset-layout').onclick=()=>{dock.reset();settings.fontSize=12.5;settings.minimap=true;settings.wordWrap=false;applySettings();appearanceDialog();};
}
function aboutDialog(){
  modal('Lumen Studio',`<p>Developer Preview 0.5.2. Interfaz reconstruida a partir de la referencia Lumen, con tres temas y servicios locales reales.</p><dl class="about-grid"><dt>Interfaz</dt><dd>JavaScript + CSS / DOM</dd><dt>Servicio local</dt><dd>Python ${esc(service.python)} · ${esc(service.platform)}</dd><dt>Editor</dt><dd>${editor.kind==='monaco'?'Monaco Editor 0.52.2':'Editor base integrado (sin dependencias)'}</dd><dt>Detalle gráfico</dt><dd>${esc(sceneStatus)}</dd><dt>Módulo nativo</dt><dd>${esc(service.native)}</dd><dt>Proyecto</dt><dd>${esc(service.workspace)}</dd><dt>IA</dt><dd>${platformUI?esc(platformUI.prefs['ai.provider'])+' · '+esc(platformUI.prefs['ai.model']||'modelo sin configurar'):'Sin proveedor configurado'}</dd></dl><div class="inline-note">Los proveedores se conectan con tus credenciales; una selección de modelo no acredita una conexión validada. Los servidores LSP y los compiladores se instalan por separado. Incluye depuración paso a paso para Python. Unity y los adaptadores de otros lenguajes se configuran por separado. El editor base funciona sin descargas. <code>python tools/setup_assets.py</code> prepara Monaco, Babylon y xterm en tu equipo.</div><div class="modal-actions"><button class="primary-button" data-action="close-modal">Cerrar</button></div>`);
}
function componentsDialog(){
  modal('Componentes de Lumen',`<p>Estado de las integraciones incluidas. No es un marketplace de extensiones de Visual Studio.</p><dl class="about-grid"><dt>Python bridge</dt><dd>Activo · archivos, búsquedas y tareas.</dd><dt>Monaco</dt><dd>${service.monaco?'Instalado':'No descargado; editor base activo'}.</dd><dt>Babylon.js</dt><dd>${service.babylon?'Instalado':'No descargado; esfera CSS activa'}.</dd><dt>C / C++ / ASM</dt><dd>${esc(service.native)}.</dd><dt>Git</dt><dd>Estado, diferencias resumidas e historial del repositorio local.</dd><dt>Ollama</dt><dd>Adaptador disponible. Modelo no incluido.</dd></dl><p>Instala las dependencias visuales con <code>python tools/setup_assets.py</code>. Compila el núcleo opcional con <code>python tools/build_native.py</code> y reinicia Lumen.</p><div class="modal-actions"><button class="primary-button" data-action="close-modal">Cerrar</button></div>`);
}
function sessionDialog(){
  modal('Sesión local',`<p>El proyecto permanece en este equipo. Lumen no requiere cuenta, no envía telemetría y no sincroniza tus archivos con una nube.</p><dl class="about-grid"><dt>Carpeta</dt><dd>${esc(service.workspace)}</dd><dt>Ejecución</dt><dd>${service.trusted?'Autorizada para esta sesión':'Protegida: requiere confirmación'}</dd><dt>Shell</dt><dd>${service.shell?'Sin restricciones, iniciada con --allow-shell':'Comandos locales limitados'}</dd></dl><div class="modal-actions"><button class="secondary-button" id="revoke-trust">Revocar confianza</button><button class="primary-button" data-action="close-modal">Cerrar</button></div>`);
  $('#revoke-trust').onclick=guard(async()=>{await api('/trust',{trusted:false});service.trusted=false;closeModal();notify('Confianza revocada. Las tareas nuevas necesitan autorización.');});
}
function showMenu(anchor,items,label=''){
  closePopover();popoverAnchor=anchor;
  const pop=$('#popover');pop.innerHTML=(label?`<div class="menu-label">${esc(label)}</div>`:'')+items.map((item,i)=>item.separator?'<div class="menu-separator"></div>':`<button class="menu-item" data-menu-index="${i}" role="menuitem" aria-label="${esc(item.label)}">${item.theme?`<span class="theme-swatch swatch-${item.theme}"></span>`:icon(item.icon||'code')}<span>${esc(item.label)}</span>${item.shortcut?`<span class="menu-shortcut" aria-hidden="true">${esc(item.shortcut)}</span>`:''}</button>`).join('');
  pop.classList.remove('hidden');motion.enter(pop,-4);const rect=anchor?.getBoundingClientRect?.()||{right:innerWidth/2,left:innerWidth/2,bottom:80};
  const box=pop.getBoundingClientRect();pop.style.left=Math.max(12,Math.min(innerWidth-box.width-12,Math.max(12,rect.right-box.width)))+'px';pop.style.top=Math.max(12,Math.min(innerHeight-box.height-12,rect.bottom+8))+'px';
  pop.onkeydown=event=>{const items=[...pop.querySelectorAll('[role=menuitem]')],index=items.indexOf(document.activeElement);if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){event.preventDefault();const n=event.key==='Home'?0:event.key==='End'?items.length-1:(index+(event.key==='ArrowDown'?1:-1)+items.length)%items.length;items[n]?.focus();}if(event.key==='Escape'){event.preventDefault();closePopover();anchor?.focus();}};
  requestAnimationFrame(()=>pop.querySelector('[role=menuitem]')?.focus());
  pop.querySelectorAll('[data-menu-index]').forEach(button=>button.onclick=guard(async()=>{const item=items[+button.dataset.menuIndex];closePopover();if(item.run)await item.run();else if(item.action)await perform(item.action,anchor);}));
}
function themeMenu(anchor){showMenu(anchor,[{label:'Día',theme:'day',shortcut:'Ctrl Alt 1',run:()=>applyTheme('day')},{label:'Oscuro',theme:'dark',shortcut:'Ctrl Alt 2',run:()=>applyTheme('dark')},{label:'Bosque',theme:'forest',shortcut:'Ctrl Alt 3',run:()=>applyTheme('forest')},{separator:true},{label:'Personalizar apariencia',icon:'settings',action:'settings'}],'Ambiente Lumen');}

async function setView(view){
  studio?.enter();
  if(studio&&(view==='search'||view==='run')){activeView='explorer';renderTree();$$('.rail-item[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===view));return view==='search'?studio.search():studio.debug();}
  if(platformUI?.page)platformUI.closePage();
  activeView=view;dock?.show('project');
  $$('[data-view]').forEach(button=>{if(button.classList.contains('rail-item'))button.classList.toggle('active',button.dataset.view===view);});
  if(view==='explorer'){renderTree();return;}
  if(view==='search'){
    $('#sidebar-title').textContent='Search';$('#sidebar-content').innerHTML='<div class="sidebar-search"><input id="project-search" type="text" placeholder="Search in files..." aria-label="Buscar texto en el proyecto"><div class="sidebar-badge">Literal · hasta 200 resultados</div></div><div id="project-search-results" class="search-results"></div>';
    let timer,request=0;$('#project-search').oninput=event=>{clearTimeout(timer);const q=event.target.value,id=++request;timer=setTimeout(guard(async()=>{const data=await api('/search?q='+encodeURIComponent(q)+'&content=1');if(id!==request)return;$('#project-search-results').innerHTML=data.results.map(result=>`<button class="search-result" data-file="${esc(result.path)}" data-line="${result.line}"><strong>${esc(result.path)}:${result.line}</strong><small>${esc(result.text)}</small></button>`).join('')||(q?'<div class="tree-message">Sin coincidencias.</div>':'');}),180);};$('#project-search').focus();return;
  }
  if(view==='git'){
    $('#sidebar-title').textContent='Source Control';$('#sidebar-content').innerHTML=`<div class="sidebar-section"><button class="secondary-button" data-action="refresh-git">${icon('refresh')} Refresh</button><span class="sidebar-badge">Lectura del repositorio local</span></div><pre class="sidebar-pre" id="git-output">Consultando Git...</pre>`;
    const result=await api('/git?mode=status');if(activeView!=='git')return;$('#git-output').textContent=result.output;
    const match=/^## ([^\.\n ]+)/m.exec(result.output);$('#branch-label').textContent=match?match[1]:'local';return;
  }
  if(view==='run'){
    $('#sidebar-title').textContent='Run & Debug';const examples=allFiles().filter(path=>path.startsWith('Examples/'));
    $('#sidebar-content').innerHTML=`<div class="sidebar-section"><h3>Current file</h3><button class="sidebar-task" data-action="run">${icon('play')} Run active file <kbd>F5</kbd></button><button class="sidebar-task" data-action="check-file">${icon('check')} Check syntax</button><button class="sidebar-task" data-action="workspace-check">${icon('files')} Check workspace</button><span class="sidebar-badge">${icon('shield')}${service.trusted?'Trusted for this session':'Workspace protected'}</span></div><div class="sidebar-section"><h3>Executable examples</h3>${examples.map(path=>`<button class="sidebar-task" data-file="${esc(path)}">${fileIcon(path)}${esc(path.split('/').pop())}</button>`).join('')||'<p class="tree-message">No hay ejemplos en esta carpeta.</p>'}</div><div class="tree-message">La ejecución es real y no está aislada. La depuración paso a paso y la conexión con Unity no están incluidas en esta edición.</div>`;
  }
}

function termWrite(text,cls=''){
  const span=document.createElement('span');if(cls)span.className=cls;span.textContent=text;$('#terminal-log').appendChild(span);
  if($('#terminal-log').textContent.length>550000)$('#terminal-log').textContent=$('#terminal-log').textContent.slice(-450000);
  const scroll=$('#terminal-scroll');scroll.scrollTop=scroll.scrollHeight;
}
function termClear(){$('#terminal-log').textContent='';}
function updatePrompt(){$('#prompt-path').textContent=`~/Projects/${service.name}${cwd&&cwd!=='.'?'/'+cwd:''}`;$('#console-label').textContent=service.shell?'shell':'local';}
function showTerminal(mode='terminal'){studio?.enter();if(platformUI?.page&&platformUI.page!=='settings')platformUI.closePage();if(platformUI){platformUI.showingPTY=false;platformUI.renderActiveTerminal();}dock?.show('console');terminalMode=mode;renderTerminalContent();}
async function renderTerminalContent(){
  $$('.terminal-tab').forEach(button=>{button.classList.toggle('active',button.dataset.terminal===terminalMode);button.setAttribute('aria-selected',String(button.dataset.terminal===terminalMode));button.tabIndex=button.dataset.terminal===terminalMode?0:-1;button.id='terminal-tab-'+button.dataset.terminal;button.setAttribute('aria-controls',button.dataset.terminal==='terminal'?'terminal-scroll':'terminal-content');});
  const standard=terminalMode==='terminal';$('#terminal-scroll').classList.toggle('hidden',!standard);$('#terminal-content').classList.toggle('hidden',standard);$('.terminal-signature').classList.toggle('hidden',!standard);
  const currentPane=standard?$('#terminal-scroll'):$('#terminal-content');currentPane.setAttribute('role','tabpanel');currentPane.setAttribute('aria-labelledby','terminal-tab-'+terminalMode);
  if(standard)return;
  const pane=$('#terminal-content');
  if(terminalMode==='problems'){
    const items=editor.diagnostics();pane.textContent=items.length?items.map(item=>`${item.severity.toUpperCase()} · line ${item.line}: ${item.message}`).join('\n'):'Sin diagnósticos recibidos.\nEsto no equivale a una compilación correcta. Configura un servidor LSP para el análisis semántico.';
  }else if(terminalMode==='output')pane.textContent=lastOutput||'No tasks have run in this session.';
  else if(terminalMode==='debug')pane.innerHTML='<p>Abre Depuración para inspeccionar tu programa paso a paso.</p><button class="secondary-button" data-action="debug-view">Abrir depuración</button>';
  else if(terminalMode==='git'){pane.textContent='Reading repository...';try{const result=await api('/git?mode=status');if(terminalMode==='git')pane.textContent=result.output;}catch(error){pane.textContent=error.message;}}
}
async function checkWorkspace(reveal=true){if(reveal)showTerminal();const data=await api('/console',{command:'check'});termWrite('❯ check\n','term-command');termWrite(data.output,'term-success');}
async function ensureTrust(){
  if(service.trusted)return true;
  const yes=await confirmDialog('¿Confías en este proyecto?','El código podrá leer y modificar archivos, acceder a la red y ejecutar procesos con tus permisos. Esto no es una sandbox. Solo autoriza una carpeta cuyo contenido conoces. La confianza se revoca al cambiar de proyecto o reiniciar Lumen.','Confiar y continuar');
  if(yes){await api('/trust',{trusted:true});service.trusted=true;if(activeView==='run')setView('run');}
  return yes;
}
async function runCurrent(check=false){
  if(!editor.current){notify('Abre un archivo para ejecutarlo.');return;}
  if(activeJob){notify('Ya hay una tarea activa en esta consola. Deténla antes de iniciar otra.');return;}
  if(!await ensureTrust())return;
  if(editor.isDirty())await saveFile();
  showTerminal();termWrite('\n','term-muted');lastOutput='';
  let result;try{result=await api('/task',{path:editor.current,check});}catch(error){lastOutput=error.message;termWrite(error.message+'\n','term-error');notify(error.message,'error');return;}
  if(result.preview){studio.lantern.showPreview(result.preview);termWrite('Vista previa: '+result.preview.url+'\n','term-success');}else if(result.job)await watchJob(result.job);else{termWrite(result.output,'term-success');lastOutput=result.output;}
}
function updateTaskUI(running){
  const button=$('.run-button');button.innerHTML=icon(running?'stop':'play');button.dataset.action=running?'stop-task':'run';
  button.classList.toggle('task-running',running);button.setAttribute('aria-label',running?'Detener tarea':'Ejecutar archivo activo');
  button.dataset.tooltip=running?'Detener tarea (Shift+F5)':'Ejecutar archivo activo (F5)';button.setAttribute('aria-busy',String(running));
}
async function watchJob(id){
  const path=editor.current;
  updateTaskUI(true);
  activeJob=id;$('#stop-task').classList.remove('hidden');$('#terminal-input').disabled=false;const oldPlaceholder=$('#terminal-input').placeholder;$('#terminal-input').placeholder='Entrada del programa · Enter para enviar';let offset=0;
  try{
    while(activeJob===id){
      const result=await api('/job?id='+encodeURIComponent(id)+'&offset='+offset);offset=result.offset;
      termWrite(result.output);lastOutput+=result.output;
      if(result.done){const parsed=await api('/platform/diagnostics/output',{path,output:lastOutput});editor.setDiagnostics(path,parsed.diagnostics,'lumen-build');notify(`Tarea finalizada. Código de salida: ${result.code??0}`,result.code?'error':'info',3300);break;}
      await new Promise(resolve=>setTimeout(resolve,180));
    }
  }finally{updateTaskUI(false);activeJob=null;$('#stop-task').classList.add('hidden');$('#terminal-input').disabled=false;$('#terminal-input').placeholder=oldPlaceholder;}
}
async function consoleCommand(command){
  if(activeJob){await api('/task-input',{id:activeJob,text:command+'\n'});termWrite(command+'\n','term-command');$('#terminal-input').value='';return;}
  if(/^(?:lumen\s+)?\/?lantern$/i.test(command.trim())){$('#terminal-input').value='';await studio.lantern.action('start');return;}
  const focus=/^(?:lumen\s+)?(?:\/?focus|concentracion)(?:\s+(on|off|toggle))?$/i.exec(command.trim());if(focus&&platformUI){$('#terminal-input').value='';platformUI.setFocus(focus[1]||'toggle');return;}
  if(!command.trim())return;terminalHistory.push(command);historyIndex=terminalHistory.length;
  termWrite(`${$('#prompt-path').textContent} ❯ ${command}\n`,'term-command');$('#terminal-input').value='';
  const themeMatch=/^theme\s+(day|dark|forest)$/.exec(command.trim());if(themeMatch){applyTheme(themeMatch[1]);return;}
  if(/^run\s/.test(command)&&!await ensureTrust())return;
  try{
    const data=await api('/console',{command,cwd});
    if(data.clear)termClear();if(data.cwd!==undefined){cwd=data.cwd;updatePrompt();}if(data.output)termWrite(data.output);
    if(data.preview)studio.lantern.showPreview(data.preview);if(data.job){lastOutput='';await watchJob(data.job);}
  }catch(error){termWrite(error.message+'\n','term-error');}
}

function aiSettingsDialog(){
  modal('Conectar un modelo local',`<p>El panel utiliza Ollama en tu equipo. No se incluye un modelo ni se instala uno automáticamente. Solo se envía el código seleccionado o el archivo activo cuando pulsas Enviar.</p><form id="ai-connect-form"><label class="field-label" for="ai-base">Dirección de Ollama</label><input id="ai-base" type="url" value="${esc(service.ai?.base||'http://127.0.0.1:11434')}" required><label class="field-label" for="ai-model">Modelo instalado (vacío: primer modelo disponible)</label><input id="ai-model" type="text" value="${esc(service.ai?.model||'')}" placeholder="Nombre exacto mostrado por Ollama"><div class="inline-note">Inicia Ollama e instala un modelo por tu cuenta. No hay claves de API, telemetría ni envíos a servicios externos en esta integración.</div><div id="ai-connect-status" class="error-message"></div><div class="modal-actions"><button class="secondary-button" type="button" id="ai-disconnect">Desconectar</button><button class="primary-button" type="submit" id="ai-connect-button">Conectar</button></div></form>`);
  $('#ai-connect-form').onsubmit=async event=>{
    event.preventDefault();const button=$('#ai-connect-button');button.disabled=true;$('#ai-connect-status').textContent='Consultando Ollama local...';
    try{
      const data=await api('/ai/connect',{base:$('#ai-base').value.trim(),model:$('#ai-model').value.trim()});
      service.ai=data;aiConsent=false;
      if(!data.connected){$('#ai-connect-status').textContent='Ollama responde, pero no hay modelos instalados.';return;}
      closeModal();notify('Modelo conectado: '+data.model);$('#assistant-subtitle').textContent='Connected locally · '+data.model;$('#ai-input').focus();
    }catch(error){$('#ai-connect-status').textContent=error.message;}finally{button.disabled=false;}
  };
  $('#ai-disconnect').onclick=guard(async()=>{await api('/ai/disconnect',{});service.ai.connected=false;aiConsent=false;closeModal();$('#assistant-subtitle').textContent='Connect a local model. Keep your flow.';notify('Modelo desconectado.');});
}
function appendChat(text,role='assistant',label=''){
  $('#assistant-hero').classList.add('hidden');$('#ai-actions').classList.add('hidden');$('#chat-messages').classList.remove('hidden');$('#assistant-body').classList.add('chatting');
  const message=document.createElement('div');message.className='chat-message '+role;
  const heading=document.createElement('small');heading.textContent=label||(role==='user'?'TÚ':'LUMEN · MODELO LOCAL');message.appendChild(heading);
  const chunks=text.split(/```[^\n]*\n([\s\S]*?)```/g);
  chunks.forEach((part,index)=>{
    if(index%2){const pre=document.createElement('pre');pre.textContent=part;message.appendChild(pre);const copy=document.createElement('button');copy.className='copy-code';copy.textContent='Copiar código';copy.onclick=guard(async()=>{await navigator.clipboard.writeText(part);copy.textContent='Copiado';});message.appendChild(copy);}
    else{const span=document.createElement('span');span.textContent=part;message.appendChild(span);}
  });
  $('#chat-messages').appendChild(message);$('#chat-messages').scrollTop=$('#chat-messages').scrollHeight;return message;
}
async function sendAI(question){
  if(platformUI)return platformUI.sendAI(question);
  if(aiBusy||!question.trim())return;
  if(!service.ai?.connected){aiSettingsDialog();return;}
  if(!aiConsent){const yes=await confirmDialog('Contexto para el modelo local','Se enviará esta pregunta junto con la selección de código, o con el archivo activo si no hay selección, al servidor Ollama local que has conectado. Las respuestas proponen cambios; nunca modifican archivos automáticamente.','Enviar al modelo');if(!yes)return;aiConsent=true;}
  aiBusy=true;$('.send-button').disabled=true;
  appendChat(question,'user');$('#ai-input').value='';
  const waiting=appendChat('El modelo local está generando la respuesta...','assistant',service.ai.model);
  try{
    const result=await api('/ai/chat',{question,path:editor.current||'Sin archivo',content:editor.getSelection()||editor.getValue()});
    waiting.remove();appendChat(result.text,'assistant',result.model);
  }catch(error){waiting.remove();appendChat(error.message,'assistant','CONEXIÓN LOCAL');}
  finally{aiBusy=false;$('.send-button').disabled=false;}
}
function beginAiAction(action){
  const prompts={generate:'Propón una mejora concreta para este archivo y proporciona el código necesario.',refactor:'Refactoriza este código conservando su comportamiento. Explica los cambios antes de presentar el código.',explain:'Explica este código, su flujo de ejecución y las decisiones importantes.',fix:'Analiza este código y busca problemas reales. Distingue errores confirmados de posibles riesgos y propone correcciones.'};
  $('#ai-input').value=prompts[action]||'';if(!platformUI&&!service.ai?.connected)aiSettingsDialog();else $('#ai-input').focus();
}
function newChat(){if(platformUI)guard(()=>platformUI.clearAI())();if(aiBusy){notify('Espera a que termine la respuesta antes de abrir otra conversación.');return;}$('#chat-messages').textContent='';$('#chat-messages').classList.add('hidden');$('#assistant-hero').classList.remove('hidden');$('#ai-actions').classList.remove('hidden');$('#assistant-body').classList.remove('chatting');$('#ai-input').value='';}

const commandDefinitions=[
  ['new-window','plus','Nueva ventana','Ctrl Shift N'],['save-as','file','Guardar como','Ctrl Shift O'],['downloads','download','Descargas de compiladores · hasta 500 GB',''],['group-tabs','folder','Agrupar pestañas por carpeta',''],['lantern','sparkles','Lantern: iniciar continuidad','Ctrl Alt L'],['lantern-monitor','sparkles','Lantern: mostrar / ocultar monitor del proyecto',''],['debug-view','bug','Abrir depuración y Lantern',''],
  ['lumen.focus.toggle','focus','lumen.focus.toggle · Alternar concentración','Ctrl Alt F'],['platform-tools','build','Lenguajes, compiladores y CMake',''],['platform-terminal','terminal','Nueva terminal: CMD, PowerShell, Bash o WSL','Ctrl Alt T'],['extensions','extensions','Marketplace Open VSX y extensiones','Ctrl Alt E'],['platform-hardware','cpu','Métricas de hardware',''],['platform-snippets','code','Insertar fragmento de extensión',''],['platform-completion','code','LSP: solicitar autocompletado','Ctrl Space'],['platform-hover','info','LSP: consultar símbolo',''],
  ['settings','settings','Apariencia y ajustes','Ctrl ,'],['layout-settings','layout','Organizar y agrupar paneles',''],['focus-layout','focus','Alternar modo enfoque','Ctrl Alt F'],['reset-layout','refresh','Restaurar distribución Lumen',''],['open-workspace','folder-open','Abrir carpeta',''],['new-file','file','Nuevo archivo',''],
  ['save','check','Guardar archivo','Ctrl S'],['find','search','Buscar en el archivo','Ctrl F'],['run','play','Ejecutar archivo activo','F5'],
  ['check-file','check','Comprobar sintaxis',''],['workspace-check','files','Comprobar proyecto',''],
  ['toggle-tree','dock-left','Contraer / expandir panel izquierdo','Ctrl B'],['toggle-terminal','terminal','Mostrar / ocultar terminal','Ctrl J'],
  ['collapse-right','dock-right','Contraer / expandir panel derecho','Ctrl Alt B'],['toggle-rail','rail-compact','Navegación: iconos o etiquetas','Ctrl Alt N'],['toggle-ai','sparkles','Mostrar / ocultar asistente',''],['theme-day','sun','Tema: Día','Ctrl Alt 1'],['theme-dark','moon','Tema: Oscuro','Ctrl Alt 2'],['theme-forest','leaf','Tema: Bosque','Ctrl Alt 3'],
  ['ai-settings','sparkles','Conectar Copilot, OpenAI, Gemini, Claude u Ollama',''],['about','info','Acerca de Lumen','']
];
function openPalette(initial=''){
  closePopover();$('#palette-backdrop').classList.remove('hidden');motion.enter($('.command-palette'),-6);$('#palette-input').value=initial;paletteIndex=0;updatePalette();requestAnimationFrame(()=>$('#palette-input').focus());
}
function closePalette(){$('#palette-backdrop').classList.add('hidden');editor?.focus();}
async function updatePalette(){
  const input=$('#palette-input').value,commandsOnly=input.startsWith('>'),query=(commandsOnly?input.slice(1):input).trim().toLowerCase(),request=++paletteRequest;
  const commands=commandDefinitions.filter(entry=>!query||entry[2].toLowerCase().includes(query)).map(entry=>({action:entry[0],icon:entry[1],label:entry[2],meta:entry[3]||'Comando'}));
  let entries=[];
  if(!commandsOnly){
    if(query){
      const [names,content]=await Promise.all([api('/search?q='+encodeURIComponent(query)),api('/search?q='+encodeURIComponent(query)+'&content=1')]);
      entries=names.results.map(item=>({path:item.path,label:item.path.split('/').pop(),meta:item.path}));
      entries.push(...content.results.slice(0,45).map(item=>({path:item.path,line:item.line,label:item.text?.trim()||item.path,meta:item.path+':'+item.line})));
      entries.push(...(platformUI?.schema||[]).filter(x=>(x.label.es+' '+x.label.en+' '+x.key).toLowerCase().includes(query)).slice(0,8).map(x=>({category:x.category,icon:'settings',label:x.label[platformUI.prefs['general.locale']]||x.label.es,meta:'Ajustes · '+x.category})));
      entries.push(...commands.slice(0,8));
    }else entries=allFiles().slice(0,60).map(path=>({path,label:path.split('/').pop(),meta:path}));
  }
  if(request!==paletteRequest)return;
  paletteEntries=commandsOnly?commands:entries.slice(0,90);
  paletteIndex=0;renderPalette();
}
function renderPalette(){
  $('#palette-count').textContent=paletteEntries.length+' resultados';
  $('#palette-files').classList.toggle('active',!$('#palette-input').value.startsWith('>'));$('#palette-commands').classList.toggle('active',$('#palette-input').value.startsWith('>'));
  $('#palette-results').innerHTML=paletteEntries.map((item,index)=>`<button class="palette-result${index===paletteIndex?' active':''}" data-palette-index="${index}" role="option" aria-selected="${index===paletteIndex}">${item.path?fileIcon(item.path):icon(item.icon)}<span>${esc(item.label)}</span><span class="result-meta">${esc(item.meta||'')}</span></button>`).join('')||'<div class="palette-empty">No se encontraron resultados.</div>';
  $$('.palette-result').forEach(button=>button.onclick=guard(()=>choosePalette(+button.dataset.paletteIndex)));
  $('#palette-results .active')?.scrollIntoView({block:'nearest'});
}
async function choosePalette(index){const item=paletteEntries[index];if(!item)return;closePalette();if(item.path){await openFile(item.path);if(item.line)editor.showLine(item.line);}else if(item.category)await platformUI.settings(item.category);else await perform(item.action);}

async function perform(action,anchor=null){
  if(action==='lantern')return studio?.lantern.action('start');
  if(action==='lantern-monitor')return studio?.lantern.action(platformUI.prefs['appearance.lanternMonitor']?'hide':'show');
  if(action==='debug-view')return studio?.debug();
  if(action==='home')return studio?.home();
  if(action==='profile'||action==='session')return studio?.editProfile();
  if(action==='debug-view')return setView('run');
  if(action==='open-file'){
    if(window.pywebview?.api?.choose_file){
      const chosen=await window.pywebview.api.choose_file();if(!chosen)return;
      const normalized=chosen.replaceAll('\\','/'),root=service.workspace.replaceAll('\\','/');
      if(normalized.toLowerCase().startsWith(root.toLowerCase()+'/'))return openFile(normalized.slice(root.length+1));
      const parent=normalized.slice(0,normalized.lastIndexOf('/'));if(!await changeWorkspace(parent))return;return openFile(normalized.slice(normalized.lastIndexOf('/')+1));
    }
    studio?.enter();return openPalette();
  }
  if(['new-file','extensions','run','check-file','workspace-check','platform-tools','task-picker'].includes(action))studio?.enter();
  if(platformUI){
    if(action.startsWith('plugin.'))return platformUI.pluginCommand(action.slice(7));
    switch(action){
      case 'settings':return platformUI.settings();case 'extensions':return platformUI.extensions();case 'ai-settings':return platformUI.settings('ai');
      case 'focus-layout':case 'lumen.focus.toggle':return platformUI.setFocus();
      case 'platform-tools':case 'task-picker':return platformUI.tools();case 'platform-hardware':return platformUI.hardware();
      case 'platform-terminal':case 'new-console':case 'console-info':return platformUI.terminalProfiles();
      case 'platform-snippets':return platformUI.snippets();case 'platform-completion':return platformUI.languageAction();case 'platform-hover':return platformUI.languageAction('textDocument/hover');
      case 'clear-terminal':{const term=platformUI.terminals.get(platformUI.activeTerminal);if(platformUI.showingPTY&&term){if(term.xterm)term.xterm.clear();else term.output.textContent='';return;}break;}
    }
  }
  switch(action){
    case 'new-window':return previewUI?.newWindow();case 'save-as':return previewUI?.saveAs();case 'downloads':return previewUI?.downloads();case 'group-tabs':return previewUI?.toggleGroups();
    case 'save':return saveFile();case 'new-file':return newFileDialog();case 'open-workspace':return openWorkspaceDialog();
    case 'settings':return appearanceDialog();case 'about':return aboutDialog();case 'extensions':return componentsDialog();case 'session':return sessionDialog();
    case 'close-modal':return closeModal();case 'palette':return openPalette();case 'find':return editor.openFind();
    case 'toggle-root':rootExpanded=!rootExpanded;return renderTree();
    case 'toggle-tree':return dock.toggleSide('left');
    case 'toggle-terminal':return dock.toggle('console');
    case 'toggle-ai':return dock.toggle('assistant');
    case 'layout-settings':return layoutSettingsDialog();
    case 'focus-layout':return dock.focus();
    case 'reset-layout':return dock.reset();
    case 'theme-menu':return themeMenu(anchor||$('#theme-trigger'));case 'theme-day':return applyTheme('day');case 'theme-dark':return applyTheme('dark');case 'theme-forest':return applyTheme('forest');
    case 'theme-cycle':{const themes=['day','dark','forest'];return applyTheme(themes[(themes.indexOf(document.documentElement.dataset.theme)+1)%3]);}
    case 'run':return runCurrent();case 'check-file':return runCurrent(true);case 'workspace-check':return checkWorkspace();
    case 'run-menu':return showMenu(anchor,[{label:'Ejecutar archivo activo',icon:'play',shortcut:'F5',action:'run'},{label:'Comprobar sintaxis',icon:'check',action:'check-file'},{label:'Comprobar proyecto',icon:'files',action:'workspace-check'},{separator:true},{label:'Estado de la depuración',icon:'info',run:()=>showTerminal('debug')}],'Ejecución');
    case 'task-picker':return showMenu(anchor,allFiles().filter(p=>p.startsWith('Examples/')).map(path=>({label:path.split('/').pop(),icon:'code',run:()=>openFile(path)})),'Abrir ejemplo ejecutable');
    case 'project-menu':return showMenu(anchor,[{label:'Abrir carpeta',icon:'folder-open',action:'open-workspace'},{label:'Nuevo archivo',icon:'file',action:'new-file'},{label:'Actualizar explorador',icon:'refresh',run:refreshTree},{separator:true},{label:'Comprobar proyecto',icon:'check',action:'workspace-check'}],'Proyecto');
    case 'editor-menu':return showMenu(anchor,[{label:'Guardar archivo',icon:'check',shortcut:'Ctrl S',action:'save'},{label:'Buscar en el archivo',icon:'search',shortcut:'Ctrl F',action:'find'},{label:'Eliminar espacios finales',icon:'code',run:()=>editor.trimTrailingWhitespace()},{label:'Mostrar / ocultar minimapa',icon:'split',run:()=>{settings.minimap=!settings.minimap;applySettings();}}],'Editor');
    case 'clear-terminal':return termClear();case 'new-console':termClear();termWrite('Lumen local console. Type help to see available commands.\n','term-muted');showTerminal();$('#terminal-input').focus();return;
    case 'toggle-terminal-size':return dock.toggleConsoleSize();
    case 'stop-task':if(activeJob)return api('/stop',{id:activeJob});return;
    case 'console-info':return modal('Consola local de comandos',`<p>Esta consola ejecuta comandos y muestra la salida real. No es una terminal PTY: no admite programas interactivos, editores de terminal ni sesiones persistentes de Bash.</p><p>Comandos base: <code>help</code>, <code>ls</code>, <code>cd</code>, <code>pwd</code>, <code>cat</code>, <code>stats</code>, <code>check</code>, <code>run archivo</code>, <code>git status</code>, <code>clear</code>.</p><p>Para una shell no restringida inicia <code>python app.py --allow-shell</code> y autoriza el proyecto. Las variables de entorno no persisten entre comandos. Sigue sin ser una PTY.</p><div class="modal-actions"><button class="primary-button" data-action="close-modal">Cerrar</button></div>`);
    case 'collapse-left':return dock.toggleSide('left');
    case 'collapse-right':return dock.toggleSide('right');
    case 'toggle-rail':return dock.toggleRail();
    case 'ai-settings':return aiSettingsDialog();case 'new-chat':return newChat();case 'diagnostics':return showTerminal('problems');case 'refresh-git':return setView('git');
    case 'indent-settings':return showMenu(anchor,[2,4,8].map(size=>({label:`${size} espacios`,icon:'code',run:()=>{settings.tabSize=size;applySettings();anchor.textContent=`Spaces: ${size}`;}})),'Indentación');
    case 'notifications':$('#notification-dot').classList.add('hidden');return modal('Actividad de la sesión',notifications.length?notifications.slice(0,15).map(n=>`<div class="setting-row"><span>${esc(n.message)}<small>${esc(n.time)}</small></span></div>`).join(''):'<p>No hay notificaciones en esta sesión.</p>');
    case 'window-close':{
      if(window.pywebview?.api){if([...editor.models.keys()].some(p=>editor.isDirty(p))&&!await confirmDialog('Cambios sin guardar','Cerrar la ventana descartará los cambios no guardados.','Cerrar de todas formas'))return;return window.pywebview.api.window_action('close');}
      return notify('En modo navegador, cierra la pestaña. Ctrl+C en la consola detiene el servicio Python.');
    }
    case 'window-minimize':if(window.pywebview?.api)return window.pywebview.api.window_action('minimize');return dock.focus();
    case 'window-maximize':if(window.pywebview?.api)return window.pywebview.api.window_action('maximize');if(document.fullscreenElement)return document.exitFullscreen();return document.documentElement.requestFullscreen();
  }
}

function setupEvents(){
  const nativeReady=()=>{if(window.pywebview?.api)document.documentElement.classList.add('desktop-host');};
  nativeReady();window.addEventListener('pywebviewready',nativeReady,{once:true});
  document.addEventListener('click',guard(async event=>{
    const close=event.target.closest('[data-close-file]');if(close){event.stopPropagation();return closeFile(close.dataset.closeFile);}
    const file=event.target.closest('[data-file]');if(file)return openFile(file.dataset.file,+file.dataset.line||null);
    const tab=event.target.closest('[data-tab]');if(tab)return activateFile(tab.dataset.tab);
    const directory=event.target.closest('[data-dir]');if(directory){const path=directory.dataset.dir;openFolders.has(path)?openFolders.delete(path):openFolders.add(path);renderTree();return;}
    const view=event.target.closest('[data-view]');if(view)return setView(view.dataset.view);
    const terminal=event.target.closest('[data-terminal]');if(terminal){if(platformUI){platformUI.showingPTY=false;platformUI.renderActiveTerminal();}terminalMode=terminal.dataset.terminal;return renderTerminalContent();}
    const aiAction=event.target.closest('[data-ai-action]');if(aiAction)return beginAiAction(aiAction.dataset.aiAction);
    const aiPrompt=event.target.closest('[data-ai-prompt]');if(aiPrompt){$('#ai-input').value=aiPrompt.dataset.aiPrompt;$('#ai-input').focus();return;}
    const action=event.target.closest('[data-action]');if(action)return perform(action.dataset.action,action);
  }));
  document.addEventListener('pointerdown',event=>{if(!$('#popover').classList.contains('hidden')&&!$('#popover').contains(event.target)&&!popoverAnchor?.contains(event.target))closePopover();});
  $('#modal-backdrop').addEventListener('click',event=>{if(event.target===$('#modal-backdrop'))closeModal();});
  $('#palette-backdrop').addEventListener('click',event=>{if(event.target===$('#palette-backdrop'))closePalette();});
  $('#close-palette').onclick=closePalette;$('#palette-files').onclick=()=>openPalette('');$('#palette-commands').onclick=()=>openPalette('>');
  $('#palette-input').addEventListener('input',guard(async()=>{paletteIndex=0;await updatePalette();}));
  $('#palette-input').addEventListener('keydown',guard(async event=>{
    if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();paletteIndex=(paletteIndex+(event.key==='ArrowDown'?1:-1)+paletteEntries.length)%Math.max(1,paletteEntries.length);renderPalette();}
    if(event.key==='Enter'){event.preventDefault();await updatePalette();await choosePalette(paletteIndex);}
  }));
  $('#terminal-form').addEventListener('submit',guard(async event=>{event.preventDefault();await consoleCommand($('#terminal-input').value);}));
  $('#terminal-input').addEventListener('keydown',event=>{
    if(event.key==='ArrowUp'){event.preventDefault();historyIndex=Math.max(0,historyIndex-1);event.target.value=terminalHistory[historyIndex]||'';}
    if(event.key==='ArrowDown'){event.preventDefault();historyIndex=Math.min(terminalHistory.length,historyIndex+1);event.target.value=terminalHistory[historyIndex]||'';}
  });
  $('#ai-form').addEventListener('submit',guard(async event=>{event.preventDefault();await sendAI($('#ai-input').value);}));
  $('#ai-input').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();$('#ai-form').requestSubmit();}});
  document.addEventListener('keydown',event=>{
    if($('#onboarding'))return;
    if(event.key==='Escape'){
      closePopover();if(!$('#modal-backdrop').classList.contains('hidden')){event.preventDefault();closeModal();}
      if(!$('#palette-backdrop').classList.contains('hidden')){event.preventDefault();closePalette();}return;
    }
    if(event.key==='Tab'&&!$('#modal-backdrop').classList.contains('hidden')){
      const list=[...$('#modal').querySelectorAll('button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled])')].filter(el=>el.offsetParent!==null);
      const first=list[0],last=list.at(-1);if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
    }
    const control=event.ctrlKey||event.metaKey;const key=event.key.toLowerCase();let action;
    if(control&&event.altKey&&['1','2','3'].includes(key))action=['theme-day','theme-dark','theme-forest'][+key-1];
    else if(control&&event.altKey&&key==='b')action='collapse-right';
    else if(control&&event.altKey&&key==='n')action='toggle-rail';
    else if(control&&event.altKey&&key==='l')action='lantern';
    else if(control&&event.altKey&&key==='f')action='focus-layout';
    else if(control&&event.shiftKey&&key==='n')action='new-window';
    else if(control&&key==='n')action='new-file';
    else if(control&&(key==='s'||key==='o'))action=event.shiftKey?'save-as':'save';
    else if(control&&event.altKey&&key==='l')action='lantern';
    else if(control&&key===',')action='settings';
    else if(control&&key==='b')action='toggle-tree';
    else if(control&&key==='j')action='toggle-terminal';
    else if(control&&(key==='p'||key==='k')){event.preventDefault();event.stopPropagation();openPalette(event.shiftKey?'>':'');return;}
    else if(control&&event.shiftKey&&key==='f'){event.preventDefault();event.stopPropagation();guard(()=>setView('search'))();return;}
    else if(control&&key==='c'&&activeJob&&$('#terminal-panel').contains(document.activeElement))action='stop-task';
    else if(event.key==='F5')action=event.shiftKey?'stop-task':'run';
    if(action){event.preventDefault();event.stopPropagation();guard(()=>perform(action))();}
  },true);
  window.addEventListener('beforeunload',event=>{if(editor&&[...editor.models.keys()].some(path=>editor.isDirty(path))){event.preventDefault();event.returnValue='';}});
}
async function initializeDocuments(){
  // Opening a workspace must not fabricate file history from bundled examples.
  renderTabs();renderTree();updateDocumentStatus();
}
async function start(){
  renderIcons();applyTheme(document.documentElement.dataset.theme,false);setupEvents();
  dock=new DockManager($('#workspace'),motion);
  document.addEventListener('lumen:organize',event=>layoutSettingsDialog(event.detail.panel));
  polish=installInteractions({motion,reorderFile,activateFile,closeFile:guard(closeFile)});

  try{
    const response=await fetch('/api/bootstrap',{credentials:'same-origin',signal:AbortSignal.timeout(25000)});service=await response.json();if(!response.ok)throw new Error(service.error);
    token=service.token;tree=service.tree;
    editor=new LumenEditor($('#editor-mount'),{change:()=>{renderTabs();platformUI?.documentChanged();},cursor:(line,column)=>$('#cursor-status').textContent=`Ln ${line}, Col ${column}`,save:guard(saveFile),diagnostics:updateDiagnostics});
    await editor.init(service,settings);applySettings();
    await initializeDocuments();renderTree();updatePrompt();
    scene={kind:service.babylon?'babylon':'css',setMotion(){},setTheme(){},dispose(){}};
    sceneStatus=service.babylon?'Babylon.js + Three.js · Lenon Glass':'Cristal CSS';
    await checkWorkspace(false);
    renderTerminalContent();
    platformUI=new LumenPlatform({api,notify,editor,motion,dock,modal,closeModal,confirmDialog,ensureTrust,appendChat,saveFile,watchJob,updateDiagnostics,openFile,refreshFileViews:()=>{renderTree();renderTabs();},
      isTrusted:()=>service.trusted,setTrusted:value=>{service.trusted=value;},showConsole:()=>showTerminal(),graphicsKind:()=>scene?.kind||'css',
      applyPlatformSettings:p=>{
        for(const [key,value] of Object.entries(p))if(key.startsWith('editor.'))settings[key.slice(7)]=value;
        settings.motion=p['appearance.motion'];settings.density=p['appearance.density'];applySettings();applyTheme(p['appearance.theme'],false);
      },
      setPluginCommands:items=>{for(let i=commandDefinitions.length-1;i>=0;i--)if(commandDefinitions[i][0].startsWith('plugin.'))commandDefinitions.splice(i,1);for(const item of items)commandDefinitions.push(['plugin.'+item.id,'extensions',item.title,'']);}
    });
    await platformUI.init();
    studio=new LenonStudio({api,platform:platformUI,dock,editor,motion,modal,closeModal,notify,ensureTrust,openFile,saveFile,palette:openPalette,refreshTree,service:()=>service,files:allFiles});
    await studio.init();
    previewUI=installPreview({api,editor,studio,platform:platformUI,dock,modal,closeModal,confirmDialog,notify,openFile,saveFile,refreshTree,renderTabs,closeFile,revealFile,service:()=>service,showMenu,perform});
    if(service.startup?.path){await openFile(service.startup.path);if(typeof service.startup.content==='string')editor.insertText(service.startup.content,true);}
    installExplorerMenu({api,editor,notify,modal,closeModal,confirmDialog,saveFile,openFile,refreshTree,showMenu,lantern:studio.lantern,workspace:()=>service.workspace,newWindow:path=>previewUI.newWindow(path),search:path=>studio.search(path),refreshDocuments:()=>{renderTabs();updateDocumentStatus();previewUI.activeChanged();}});
    document.documentElement.removeAttribute('data-booting');
    $('#engine-label').textContent='Local workspace';
    // Explicitly expose state for repeatable UI smoke tests; no secrets are exposed here.
    window.lumen={get theme(){return document.documentElement.dataset.theme;},get editorKind(){return editor.kind;},get graphicsKind(){return [...(studio?.scenes.values()||[])].some(s=>s.kind==='babylon')?'babylon':'css';},get graphicsAPI(){return document.querySelector('canvas[data-engine]')?.dataset.engine||'CSS';},get activeFile(){return editor.current;},get ready(){return true;},get platformReady(){return !!platformUI?.state;},get platformPage(){return platformUI?.page;},get languageServers(){return platformUI?.lspSessions.size||0;},get layout(){return dock.snapshot();},get motionEnabled(){return motion.enabled;}};
  }catch(error){document.documentElement.removeAttribute('data-booting');$('#connection-overlay').classList.remove('hidden');$('#connection-overlay p').textContent='No se pudo iniciar la interfaz: '+error.message;console.error(error);}
}
window.addEventListener('pagehide',event=>{if(!event.persisted){studio?.dispose();platformUI?.dispose();scene?.dispose();dock?.dispose();motion.dispose();polish?.dispose();}});
$('#retry-connection').onclick=()=>location.reload();
start();
