import {extensionReviewHTML,extensionPlanHTML,extensionProgressHTML,updateExtensionProgress} from './extension-installer.js';
import {ACCOUNT_PROVIDERS,accountPanel,bindAccount} from './accounts.js';
import {icon,escapeHTML,setFileIcons} from './icons.js';
import {languageFor} from './editor.js';
import {LiveEditSession} from './live-edit.js';
import {applyShellTheme} from './extension-theme.js';
import {requestsLiveEdit} from './ai-intent.js';
import {OrderedTerminalInput,isDeviceAttributesReply} from './terminal-input.js';

const PLATFORM_CATEGORIES=[
 ['general','globe','General','General'],['appearance','sun','Apariencia','Appearance'],['editor','code','Editor de texto','Text editor'],
 ['files','files','Archivos','Files'],['terminal','terminal','Terminales','Terminals'],['extensions','extensions','Extensiones','Extensions'],
 ['security','shield','Seguridad','Security'],['ai','sparkles','Inteligencia artificial','Artificial intelligence'],
 ['development','build','Lenguajes y herramientas','Languages and tools'],['hardware','cpu','Hardware','Hardware'],['keys','keyboard','Atajos de teclado','Keyboard shortcuts']
];
const PLATFORM_NAMES={codex:'ChatGPT · cuenta', 'claude-code':'Claude · cuenta','gemini-cli':'Gemini · cuenta',copilot:'Copilot · cuenta',emma:'Emma',ollama:'Ollama',openai:'OpenAI · API',anthropic:'Claude · API',gemini:'Gemini · API'};
const PLATFORM_OPTION_NAMES={es:['Español','Spanish'],en:['Inglés','English'],day:['Día','Day'],dark:['Oscuro','Dark'],forest:['Bosque','Forest'],comfortable:['Cómoda','Comfortable'],compact:['Compacta','Compact'],none:['Ninguno','None'],selection:['Selección','Selection'],file:['Archivo activo','Active file'],all:['Todos','All'],smooth:['Suave','Smooth'],blink:['Intermitente','Blink'],solid:['Fijo','Solid']};

/** The platform UI owns no provider credentials after the configuration request. */
export class LumenPlatform {
  constructor(host){
    this.host=host;this.api=(path,body)=>host.api('/platform'+path,body);this.prefs={};this.schema=[];this.providers=[];
    this.page=null;this.activeCategory='general';this.disposed=false;this.timers=[];this.extensionContributions={};this.contributionDisposables=[];
    this.terminals=new Map();this.activeTerminal=null;this.showingPTY=false;this.aiJob=null;this.aiGeneration=0;this.conversation=crypto.randomUUID?.()||String(Date.now());
    this.lspSessions=new Map();this.diagnosticMap=new Map();this.development={tasks:[],servers:[],associations:{}};
    this.workbench=document.createElement('section');this.workbench.id='platform-page';this.workbench.className='platform-page';this.workbench.hidden=true;
    this.workbench.setAttribute('aria-label','Zénit workbench');document.getElementById('editor-panel').appendChild(this.workbench);
    this.workbench.addEventListener('click',event=>this.click(event));
    this.lastContent=new Map();this.changeTimer=null;this.saveTimer=null;this.settingsWrite=Promise.resolve();
  }
  t(es,en){return this.prefs['general.locale']==='en'?en:es;}
  e(value){return escapeHTML(String(value??''));}
  glyph(name){return icon(name);}
  async init(){
    const [state,settings]=await Promise.all([this.api('/state'),this.api('/settings')]);this.state=state;this.commandSequence=state.commandSequence;
    this.prefs=settings.settings;this.schema=settings.schema.filter(s=>!['ai.melodyProvider','ai.melodyModel','appearance.extensionTheme'].includes(s.key));this.providers=state.providers;this.development=state.development;
    this.applyPreferences();this.createProviderBar();this.createTerminalBar();this.createStatus();this.installEvents();
    await this.loadContributions();
    this.scheduleCommands();this.scheduleHardware();
  }
  report(error){this.host.notify(error.message||String(error),'error',7000);}
  async safe(fn){try{return await fn();}catch(error){this.report(error);}}
  later(fn,ms){const timer=setTimeout(()=>{if(!this.disposed)fn();},ms);this.timers.push(timer);if(this.timers.length>300)this.timers=this.timers.slice(-200);return timer;}
  applyPreferences(){
    const p=this.prefs;this.host.applyPlatformSettings(p);document.documentElement.lang=p['general.locale'];
    document.documentElement.dataset.decorations=p['appearance.decorations']?'on':'off';
    document.documentElement.style.setProperty('--motion-layout',p['appearance.motionDuration']+'ms');
    document.documentElement.style.setProperty('--pty-font',p['terminal.fontSize']+'px');
    document.documentElement.style.setProperty('--error-color',({red:'#e33655',rose:'#df458f',amber:'#bb7109',mint:'#16885e'})[p['appearance.errorColor']]||'#e33655');
    const external=this.extensionThemes?.find(t=>t.id===p['appearance.extensionTheme']);
    applyShellTheme(external);this.host.editor.extensionTheme=external||null;
    this.host.editor.changedTheme();this.lantern?.render();
    this.translateShell();
    for(const terminal of this.terminals.values())if(terminal.xterm){terminal.xterm.options.fontSize=p['terminal.fontSize'];terminal.xterm.options.cursorBlink=p['terminal.cursorBlink'];terminal.xterm.options.scrollback=p['terminal.scrollback'];this.themeTerminal(terminal);}
    this.updateProviderBar();this.onAppearance?.();
  }
  async savePreference(key,value){
    if(key==='appearance.theme'&&this.prefs['appearance.extensionTheme'])await this.savePreference('appearance.extensionTheme','');
    const previous=this.prefs[key];this.prefs[key]=value;this.applyPreferences();
    // Serialize writes so quickly changing a slider cannot restore an older value.
    this.settingsWrite=this.settingsWrite.catch(()=>{}).then(()=>this.api('/settings',{settings:{[key]:value}}));
    try{await this.settingsWrite;this.setSaved();}catch(e){this.prefs[key]=previous;this.applyPreferences();throw e;}
  }
  setSaved(){const el=this.workbench.querySelector('#settings-save-state');if(el){el.textContent=this.t('Guardado en este equipo','Saved on this device');el.classList.remove('pending');}}
  translateShell(){
    const labels=[['[data-view="explorer"].rail-item','Explorador','Explorer'],['[data-view="search"].rail-item','Buscar','Search'],['[data-view="git"].rail-item','Control de código','Source Control'],['[data-view="run"].rail-item','Depuración','Run & Debug'],['[data-action="extensions"].rail-item','Extensiones','Extensions'],['[data-action="toggle-ai"].rail-item','Melody','Melody']];
    for(const [selector,es,en] of labels){const el=document.querySelector(selector);if(el){const span=el.lastElementChild;if(span)span.textContent=this.t(es,en);}}
    const text=(selector,es,en)=>{const el=document.querySelector(selector);if(el){const node=[...el.childNodes].find(n=>n.nodeType===Node.TEXT_NODE&&n.textContent.trim());if(el.matches('[data-terminal]')&&node)node.textContent=this.t(es,en);else el.textContent=this.t(es,en);}};
    const release=this.state.version+' · R'+this.state.revision;
    text('.brand-tagline',release,release);text('.search-placeholder','Buscar archivos, símbolos, comandos...','Search files, symbols, commands...');
    text('#editor-empty h2','Tu próxima idea empieza aquí.','Your next idea starts here.');
    text('#editor-empty [data-action="new-file"]','Nuevo archivo','New file');
    const emptyHelp=document.querySelector('#editor-empty p');if(emptyHelp)emptyHelp.innerHTML=this.t('Abre un archivo <kbd>Ctrl P</kbd> o crea algo nuevo.','Open a file <kbd>Ctrl P</kbd> or create something new.');
    text('.assistant-heading-title h2','Melody','Melody');text('.assistant-kicker','TU ESPACIO PARA PENSAR','YOUR SPACE TO THINK');
    text('.assistant-hero h3','Hola,','Hello,');text('.layout-button-label','Espacio','Layout');
    text('.ai-action-card[data-ai-action="generate"] strong','Generar','Generate');text('.ai-action-card[data-ai-action="refactor"] strong','Refactorizar','Refactor');
    text('.ai-action-card[data-ai-action="explain"] strong','Explicar','Explain');text('.ai-action-card[data-ai-action="fix"] strong','Depurar','Debug');
    const details={generate:['Código, scripts e ideas.','Code, scripts and ideas.'],refactor:['Más sencillo y claro.','Simpler, clearer code.'],explain:['Comprende tu código.','Understand your code.'],fix:['Detecta problemas reales.','Find real problems.']};
    for(const [action,words] of Object.entries(details))text(`[data-ai-action="${action}"] small`,...words);
    const input=document.getElementById('ai-input');if(input)input.placeholder=this.t('Pregunta, explica o propón un cambio...','Ask, explain or propose a change...');
    text('[data-terminal="terminal"]','Terminal','Terminal');text('[data-terminal="problems"]','Problemas','Problems');text('[data-terminal="output"]','Salida','Output');
    text('[data-terminal="debug"]','Depuración','Debug');
    const chips=document.querySelectorAll('.ai-suggestions button[data-ai-prompt]');
    const suggestions=[['¿Cómo mejoro este código?','How can I improve this code?'],['Añadir pruebas','Add tests'],['Revisar posibles errores','Review possible bugs']];
    chips.forEach((chip,i)=>{const words=suggestions[i];if(!words)return;const node=[...chip.childNodes].find(n=>n.nodeType===Node.TEXT_NODE&&n.textContent.trim());if(node)node.textContent=this.t(...words);chip.dataset.aiPrompt=this.t(...words);});
    text('.inspiration-card strong','Luz y claridad.','Light and clarity.');text('.inspiration-card small','Crea sin límites.','Build beyond.');
    const sidebar=document.getElementById('sidebar-title');if(sidebar&&['Project','Proyecto'].includes(sidebar.textContent))sidebar.textContent=this.t('Proyecto','Project');
    const subtitle=document.getElementById('assistant-subtitle');if(subtitle&&!this.aiJob)subtitle.textContent=this.t('Convierte ideas en realidad. Más simple. Más lejos.','Turn ideas into reality. Simpler. Further.');
  }
  pageTitle(kind){if(kind==='foundation')return this.t('Laboratorio','Laboratory');if(kind==='search')return this.t('Buscar','Search');if(kind==='debug')return this.t('Depuración','Debug');return kind==='settings'?this.t('Ajustes','Settings'):kind==='extensions'?this.t('Extensiones','Extensions'):kind==='tools'?this.t('Herramientas de desarrollo','Development tools'):kind==='hardware'?this.t('Sistema y rendimiento','System and performance'):kind==='snippets'?this.t('Fragmentos de código','Code snippets'):kind;}
  openPage(kind,content){
    this.extensionServices?.hide();
    const changed=this.page!==kind;
    this.previousPageFocus ||= document.activeElement;
    for(const pane of this.host.editor.panes||[]){
      for(const command of ['hideSuggestWidget','closeParameterHints'])pane.view?.trigger('lumen.page',command,{});
    }
    document.documentElement.dataset.editorCovered='true';
    if(!this.settingsOverlay){this.settingsOverlay=document.createElement('div');this.settingsOverlay.className='settings-overlay';this.settingsOverlay.hidden=true;this.settingsOverlay.setAttribute('role','dialog');this.settingsOverlay.setAttribute('aria-modal','true');this.settingsOverlay.setAttribute('aria-label','Ajustes de Zénit');document.body.append(this.settingsOverlay);this.settingsOverlay.onclick=e=>{if(e.target===this.settingsOverlay)this.closePage();};this.settingsOverlay.onkeydown=e=>{if(e.key==='Tab'){const list=[...this.settingsOverlay.querySelectorAll('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled)')].filter(x=>x.offsetParent);if(e.shiftKey&&document.activeElement===list[0]){e.preventDefault();list.at(-1)?.focus();}else if(!e.shiftKey&&document.activeElement===list.at(-1)){e.preventDefault();list[0]?.focus();}}};}
    this.settingsOverlay.hidden=kind!=='settings';document.getElementById('app').inert=kind==='settings';
    (kind==='settings'?this.settingsOverlay:document.getElementById('editor-panel')).append(this.workbench);
    document.getElementById('workspace').dataset.page=kind;this.workbench.dataset.page=kind;
    this.page=kind;this.workbench.hidden=false;document.getElementById('editor-panel').classList.add('platform-open');
    if(kind!=='settings')document.querySelectorAll('.activity-rail .rail-item').forEach(el=>el.classList.toggle('active',(el.dataset.action||el.dataset.view)===(kind==='debug'?'run':kind)));
    for(const selector of ['.editor-tabbar','.breadcrumbs','#editor-mount','#editor-empty']){const el=document.querySelector(selector);if(el)el.inert=true;}
    this.workbench.innerHTML=`<header class="platform-header"><div class="platform-title"><span class="platform-mark">${this.glyph(kind==='extensions'?'extensions':kind==='tools'?'build':(kind==='hardware'||kind==='foundation')?'cpu':kind==='search'?'search':kind==='debug'?'bug':'settings')}</span><div><span class="platform-eyebrow">ZÉNIT</span><h2>${this.pageTitle(kind)}</h2></div></div><button class="icon-button" data-platform="close-page" aria-label="${this.t('Cerrar y volver al editor','Close and return to editor')}" title="Esc">${this.glyph('close')}</button></header>${content}`;
    if(changed)this.host.motion.enter(this.workbench,4);this.workbench.querySelector('input,button')?.focus({preventScroll:true});
  }
  closePage(){
    delete document.documentElement.dataset.editorCovered;
    if(this.settingsOverlay)this.settingsOverlay.hidden=true;
    document.getElementById('app').inert=false;delete document.getElementById('workspace').dataset.page;
    document.getElementById('editor-panel').append(this.workbench);this.previousPageFocus?.focus?.({preventScroll:true});this.previousPageFocus=null;
    this.page=null;this.workbench.hidden=true;document.getElementById('editor-panel').classList.remove('platform-open');
    document.querySelectorAll('.activity-rail .rail-item').forEach(el=>el.classList.toggle('active',el.dataset.view==='explorer'));
    for(const selector of ['.editor-tabbar','.breadcrumbs','#editor-mount','#editor-empty']){const el=document.querySelector(selector);if(el)el.inert=false;}
    this.host.editor.focus();
  }
  async settings(category=this.activeCategory){
    this.activeCategory=category;
    this.openPage('settings',`<div class="settings-toolbar"><div class="platform-search">${this.glyph('search')}<input id="settings-search" placeholder="${this.t('Buscar un ajuste...','Search settings...')}" aria-label="${this.t('Buscar ajustes','Search settings')}"><kbd>Ctrl ,</kbd></div><span id="settings-save-state">${this.t('Guardado en este equipo','Saved on this device')}</span></div><div class="settings-layout"><nav class="settings-navigation" aria-label="${this.t('Categorías de ajustes','Settings categories')}">${PLATFORM_CATEGORIES.map(([id,glyph,es,en])=>`<button data-setting-category="${id}" class="${id===category?'active':''}" aria-current="${id===category?'page':'false'}">${this.glyph(glyph)}<span>${this.t(es,en)}</span></button>`).join('')}<div class="settings-nav-footer"><button data-platform="settings-export">${this.glyph('download')}${this.t('Exportar JSON','Export JSON')}</button><button data-platform="settings-import">${this.glyph('upload')}${this.t('Importar JSON','Import JSON')}</button></div></nav><div class="settings-content" id="settings-content"></div></div>`);
    await this.renderSettingsContent();
    const input=this.workbench.querySelector('#settings-search');input.oninput=()=>this.renderSettingsContent(input.value);
  }
  async renderSettingsContent(query=''){
    const content=this.workbench.querySelector('#settings-content');if(!content)return;
    const words=query.toLocaleLowerCase();const entries=this.schema.filter(s=>words?`${s.key} ${s.label.es} ${s.label.en}`.toLocaleLowerCase().includes(words):s.category===this.activeCategory||(this.activeCategory==='general'&&['appearance.theme','appearance.motion','appearance.decorations'].includes(s.key)));
    if(!query&&this.activeCategory==='development'){content.innerHTML=this.developmentSettings();this.bindDevelopment();return;}
    if(!query&&this.activeCategory==='keys'){content.innerHTML=this.keybindings();return;}
    const category=PLATFORM_CATEGORIES.find(c=>c[0]===this.activeCategory);const heading=query?this.t('Resultados','Results'):category?this.t(category[2],category[3]):'';
    content.innerHTML=`<div class="settings-section-heading"><h3>${heading}</h3><p>${query?`${entries.length} ${this.t('ajustes','settings')}`:this.categoryHint()}</p></div>${!query&&this.activeCategory==='appearance'?this.themePreviews():''}${!query&&this.activeCategory==='ai'?this.providerSettings()+'<details class="provider-advanced"><summary>'+this.t('Preferencias del asistente','Assistant preferences')+'</summary>':''}${entries.map((s,i)=>((!query&&this.activeCategory==='general'&&s.key==='appearance.theme')?'<h3 class="settings-appearance-heading">'+this.t('Apariencia','Appearance')+'</h3><p>'+this.t('Personaliza cómo se ve y se siente Zénit.','Make Zénit look and feel like yours.')+'</p>':'')+this.settingRow(s)).join('')}${!query&&this.activeCategory==='ai'?'</details>':''}${!query&&this.activeCategory==='appearance'?this.externalThemeOptions():''}${!query&&this.activeCategory==='security'?this.securitySummary():''}${!query&&this.activeCategory==='extensions'?`<button class="secondary-button wide-button" data-platform="extensions">${this.glyph('extensions')}${this.t('Abrir centro de extensiones','Open extension center')}</button>`:''}${!query&&this.activeCategory==='terminal'?`<button class="secondary-button wide-button" data-platform="terminal-profiles">${this.glyph('terminal')}${this.t('Perfiles y nueva terminal','Profiles and new terminal')}</button>`:''}${!query&&this.activeCategory==='hardware'?'<div id="settings-hardware-state" class="hardware-inline"></div>':''}<footer class="settings-content-footer"><span>Zénit 0.5.3 · ${this.t('Preferencias locales · sin sincronización en la nube','Local preferences · no cloud sync')}</span><button data-platform="settings-reset" class="text-button">${this.t('Restaurar ajustes','Reset settings')}</button></footer>`;
    content.querySelectorAll('[data-preference]').forEach(input=>input.onchange=()=>this.safe(async()=>{
      const key=input.dataset.preference;const item=this.schema.find(s=>s.key===key);
      const value=input.type==='checkbox'?input.checked:input.type==='number'?Number(input.value):typeof item.default==='number'?Number(input.value):input.value;
      await this.savePreference(key,value);
      if(key==='ai.provider'){await this.savePreference('ai.model','');this.conversation=crypto.randomUUID?.()||String(Date.now());}if(['general.locale','ai.provider'].includes(key))await this.settings(this.activeCategory);
      if(key.startsWith('extensions.'))await this.loadContributions();
    }));
    if(!query&&this.activeCategory==='ai')this.bindProviders();
    if(!query&&this.activeCategory==='hardware')this.safe(async()=>{this.hardwareState=await this.api('/hardware');const target=document.getElementById('settings-hardware-state');if(target)target.innerHTML=this.hardwareMarkup();});
  }
  categoryHint(){
    const hints={general:['El idioma afecta a los controles de Zénit. Los mensajes de compiladores y servicios externos se conservan.','Language affects Zénit controls. Compiler and external service messages are preserved.'],appearance:['Una misma composición, tres ambientes. El movimiento reducido del sistema siempre tiene prioridad.','One composition, three environments. System reduced motion always takes priority.'],editor:['Los controles marcados Monaco necesitan ese motor. El resto también funciona en el editor integrado.','Controls marked Monaco require that engine. The others also work in the base editor.'],files:['Autoguardado con control de conflictos y copia previa. Nunca sobrescribe un cambio externo sin avisarte.','Autosave retains conflict checks and backups. External changes are never silently overwritten.'],security:['La confianza de proyecto es obligatoria para ejecutar código. No hay una sandbox de sistema operativo.','Workspace trust is required to execute code. This is not an operating-system sandbox.'],ai:['Credenciales en memoria o en el almacén seguro del sistema. Nunca en los archivos del proyecto.','Credentials stay in memory or the native secure store, never in project files.'],extensions:['Open VSX y paquetes VSIX locales. La compatibilidad se revisa antes de instalar.','Open VSX and local VSIX packages. Compatibility is reviewed before installation.'],terminal:['Sesiones interactivas reales. CMD y WSL pertenecen a Windows; Bash depende de su instalación.','Real interactive sessions. CMD and WSL belong to Windows; Bash must be installed.'],hardware:['Lecturas del sistema operativo, solo cuando las activas. No se instalan drivers ni se cambian voltajes.','Operating-system readings, only when enabled. No drivers are installed or voltages changed.']};
    return this.t(...(hints[this.activeCategory]||['','']));
  }
  settingRow(s){
    const value=this.prefs[s.key],id='pref-'+s.key.replaceAll('.','-'),copilotLimit=s.key==='ai.maxOutputTokens'&&this.prefs['ai.provider']==='copilot',disabled=(s.requires==='monaco'&&this.host.editor.kind!=='monaco')||copilotLimit;
    let control;const label=s.label[this.prefs['general.locale']]||s.label.es;
    if(s.rule==='bool')control=`<label class="platform-switch"><input id="${id}" data-preference="${s.key}" type="checkbox" ${value?'checked':''} ${disabled?'disabled':''} aria-label="${this.e(label)}"><span></span></label>`;
    else if(Array.isArray(s.rule)&&!(s.rule.length===2&&s.rule.every(x=>typeof x==='number'))){control=`<select id="${id}" data-preference="${s.key}" ${disabled?'disabled':''} aria-label="${this.e(label)}">${s.rule.map(x=>`<option value="${this.e(x)}" ${value===x?'selected':''}>${this.e(PLATFORM_OPTION_NAMES[x]?this.t(...PLATFORM_OPTION_NAMES[x]):PLATFORM_NAMES[x]||x)}</option>`).join('')}</select>`;}
    else if(Array.isArray(s.rule)){control=`<input id="${id}" data-preference="${s.key}" type="number" ${disabled?'disabled':''} min="${s.rule[0]}" max="${s.rule[1]}" step="${s.key.includes('lineHeight')?'.05':s.key==='editor.fontSize'?'.5':'1'}" value="${value}" aria-label="${this.e(label)}">`;}
    else control=`<input id="${id}" data-preference="${s.key}" type="text" maxlength="400" value="${this.e(value)}" aria-label="${this.e(label)}">`;
    return `<div class="preference-row ${disabled?'unavailable':''}"><label for="${id}">${this.e(label)}<small>${disabled?' · '+(copilotLimit?this.t('no aplicado por Copilot SDK','not applied by Copilot SDK'):this.t('motor no instalado','engine not installed')):''}</small></label><div class="preference-control">${control}</div></div>`;
  }
  themePreviews(){return `<div class="platform-theme-previews">${['day','dark','forest'].map(id=>`<button class="platform-theme-card ${this.prefs['appearance.theme']===id?'active':''}" data-platform-theme="${id}"><span class="preview-window ${id}"><i></i><i></i><i></i></span><strong>${this.t(...PLATFORM_OPTION_NAMES[id])}</strong><small>${this.t('Composición Zénit','Zénit composition')}</small></button>`).join('')}</div>`;}
  externalThemeOptions(){const themes=this.extensionThemes||[];return themes.length?`<div class="extension-theme-options"><h4>${this.t('Temas instalados · todo Zénit','Installed themes · all of Zénit')}</h4>${themes.map((x,i)=>`<button class="secondary-button" data-external-theme="${i}">${this.e(x.label||x.id)}</button>`).join('')}</div>`:'';}
  securitySummary(){return `<div class="platform-notice"><span>${this.glyph('shield')}</span><div><strong>${this.t('Sin permisos invisibles','No hidden permissions')}</strong><p>${this.t('Las extensiones ejecutables requieren autorización y acceso de usuario al equipo. La IA solo edita en vivo al permitir esa petición. La confirmación de confianza no puede desactivarse.','Executable extensions require permission and run with user access to this device. Live AI editing requires permission for that request. Workspace trust cannot be disabled.')}</p><button class="text-button" data-platform="audit">${this.t('Ver registro local','View local audit')}</button><button class="text-button" data-platform="revoke-trust">${this.t('Revocar confianza del proyecto','Revoke workspace trust')}</button></div></div>`;}
  keybindings(){return `<h3>${this.t('Acciones directas','Direct actions')}</h3><div class="shortcut-table">${[['Ctrl / Cmd + Shift + N','Nueva ventana','New window'],['Ctrl / Cmd + N','Nuevo archivo','New file'],['Ctrl / Cmd + O / S','Guardar archivo','Save file'],['Ctrl / Cmd + Shift + O / S','Guardar como','Save as'],['Ctrl / Cmd + Alt + L','Lantern en el archivo activo','Lantern on active file'],['F12','Ir a definición','Go to definition'],['Ctrl / Cmd + ,','Abrir ajustes','Open settings'],['Ctrl / Cmd + Shift + P','Paleta de comandos','Command palette'],['Ctrl / Cmd + B','Contraer lateral izquierdo','Collapse left panel'],['Ctrl / Cmd + Alt + B','Contraer lateral derecho','Collapse right panel'],['Ctrl / Cmd + Alt + F','Alternar concentración','Toggle focus'],['Ctrl / Cmd + Alt + T','Nueva terminal interactiva','New interactive terminal'],['Ctrl / Cmd + Alt + E','Extensiones','Extensions'],['Ctrl / Cmd + Space','Completado LSP (si hay servidor)','LSP completion (server required)'],['Ctrl / Cmd + Alt + 1 / 2 / 3','Día / oscuro / bosque','Day / dark / forest'],['F5 / Shift + F5','Ejecutar / detener tarea','Run / stop task']].map(([key,es,en])=>`<div><span>${this.t(es,en)}</span><kbd>${key}</kbd></div>`).join('')}</div><div class="platform-notice"><code>lumen focus</code><p>${this.t('El mismo comando entra y sale del modo concentración. En la consola de Zénit: focus, /focus o concentracion.','The same command enters and exits focus mode. In the Zénit console: focus, /focus or concentracion.')}</p></div>`;}
  async extensions(mode='installed',query=''){
    this.extensionMode=mode;this.extensionQuery=query;
    this.openPage('extensions',`<div class="extension-hero"><span class="platform-eyebrow">OPEN VSX</span><h3>${this.t('Más posibilidades. El mismo Zénit.','More possibilities. The same Zénit.')}</h3><p>${this.t('Busca en Open VSX o importa un VSIX. Revisa sus capacidades antes de instalar.','Search Open VSX or import a VSIX. Review its capabilities before installing.')}</p><div class="extension-hero-actions"><button class="secondary-button" data-platform="extension-import">${this.glyph('upload')}${this.t('Importar VSIX','Import VSIX')}</button><button class="secondary-button export-vsix" data-platform="extension-export">${this.glyph('download')}${this.t('Exportar VSIX','Export VSIX')}</button><button class="text-button" data-platform="extension-updates">${this.glyph('refresh')}${this.t('Buscar actualizaciones','Check updates')}</button></div></div><div class="extension-toolbar"><div class="segmented-control"><button data-extension-mode="installed" class="${mode==='installed'?'active':''}">${this.t('Instaladas','Installed')}</button><button data-extension-mode="browse" class="${mode==='browse'?'active':''}">${this.t('Explorar','Explore')}</button></div><form id="extension-search-form" class="platform-search">${this.glyph('search')}<input id="extension-search" value="${this.e(query)}" placeholder="${this.t('Buscar extensiones...','Search extensions...')}" aria-label="${this.t('Buscar extensiones','Search extensions')}"><button class="icon-button" aria-label="${this.t('Buscar','Search')}">${this.glyph('arrow-right')}</button></form></div><div class="extension-catalog-summary" id="extension-catalog-summary" aria-live="polite"></div><div class="extension-results" id="extension-results"><div class="platform-loading">${this.t('Cargando catálogo...','Loading catalog...')}</div></div><footer class="extension-footer">${this.glyph('shield')}<span>${this.t('Extensiones declarativas y ejecutables · API preview. Compatibilidad parcial con VS Code.','Declarative and executable extensions · preview API. Partial VS Code compatibility.')}</span></footer>`);
    this.workbench.querySelector('#extension-search-form').onsubmit=event=>{event.preventDefault();this.safe(()=>this.extensions(this.extensionMode,document.getElementById('extension-search').value));};
    const request=++this.extensionRequest||1;this.extensionRequest=request;
    try{
      const result=await this.api(mode==='installed'?'/extensions':'/extensions/search?q='+encodeURIComponent(query));
      if(this.page!=='extensions'||this.extensionRequest!==request)return;
      this.renderExtensionResults(mode==='installed'&&query?result.extensions.filter(x=>[x.displayName,x.name,x.description,x.id].join(' ').toLowerCase().includes(query.toLowerCase())):result.extensions,mode);
      this.extensionSearchState={request,offset:result.extensions.length,total:result.total??result.extensions.length};this.renderCatalogSummary();
      if(mode==='installed'&&this.prefs['extensions.checkUpdatesOnOpen']&&result.extensions.length)this.safe(()=>this.extensionUpdates());
    }catch(error){const container=document.getElementById('extension-results');if(container)container.innerHTML=`<div class="platform-empty">${this.glyph('cloud-off')}<h3>${this.t('El catálogo no está disponible','Catalog unavailable')}</h3><p>${this.e(error.message)}</p><button class="secondary-button" data-platform="extension-import">${this.t('Importar paquete local','Import local package')}</button></div>`;}
  }
  renderCatalogSummary(error=''){
    const summary=document.getElementById('extension-catalog-summary');if(!summary||this.page!=='extensions')return;
    const state=this.extensionSearchState,more=this.extensionMode==='browse'&&state.offset<state.total;
    summary.innerHTML=`<span>${this.e(error||`${this.extensionItems.length} ${this.extensionItems.length===1?this.t('extensión','extension'):this.t('extensiones','extensions')}${this.extensionMode==='browse'?' / '+state.total:''}`)}</span>${more?`<button class="text-button" id="extension-more" ${state.loading?'disabled':''}>${state.loading?this.t('Cargando…','Loading…'):error?this.t('Reintentar','Retry'):this.t('Cargar más','Load more')}${this.glyph('chevron-down')}</button>`:''}`;
    summary.querySelector('button')?.addEventListener('click',()=>this.loadMoreExtensions());
  }
  async loadMoreExtensions(){
    const state=this.extensionSearchState;if(!state||state.loading)return;state.loading=true;this.renderCatalogSummary();
    try{
      const result=await this.api('/extensions/search?q='+encodeURIComponent(this.extensionQuery)+'&offset='+state.offset);
      if(this.page!=='extensions'||state!==this.extensionSearchState)return;
      const ids=new Set(this.extensionItems.map(x=>x.id));this.renderExtensionResults([...this.extensionItems,...result.extensions.filter(x=>!ids.has(x.id))],this.extensionMode);
      state.offset+=result.extensions.length;state.total=result.extensions.length?result.total:state.offset;state.loading=false;this.renderCatalogSummary();
    }catch(error){if(state!==this.extensionSearchState)return;state.loading=false;this.renderCatalogSummary(error.message);}
  }
  extensionLogo(item){
    const alt=this.e(item.displayName||item.name||'Extensión');
    if(item.icon?.startsWith('data:image/'))return `<img class="extension-package-icon" src="${this.e(item.icon)}" alt="${alt}" loading="lazy">`;
    return `<span class="extension-icon-fallback" ${item.iconUrl?`data-package-icon="${this.e(item.iconUrl)}"`:''} aria-label="${alt}">${this.e((item.displayName||item.name||'EX').slice(0,2).toUpperCase())}</span>`;
  }
  loadExtensionIcons(container){
    this.extensionIconObserver?.disconnect();
    this.extensionIconObserver=new IntersectionObserver(entries=>{for(const entry of entries){if(!entry.isIntersecting)continue;const node=entry.target;this.extensionIconObserver.unobserve(node);this.api('/extensions/icon?url='+encodeURIComponent(node.dataset.packageIcon)).then(({icon})=>{if(!node.isConnected||!icon?.startsWith('data:image/'))return;const image=document.createElement('img');image.className='extension-package-icon';image.alt=node.getAttribute('aria-label');image.src=icon;image.onerror=()=>image.replaceWith(node);node.replaceWith(image);}).catch(()=>{});}}, {root:container.closest('.platform-workspace'),rootMargin:'180px'});
    container.querySelectorAll('[data-package-icon]').forEach(node=>this.extensionIconObserver.observe(node));
  }
  renderExtensionResults(items,mode){
    const container=document.getElementById('extension-results');if(!container)return;
    this.extensionItems=items;
    if(!items.length){container.innerHTML=`<div class="platform-empty">${this.glyph('extensions')}<h3>${this.t('Un espacio para tus herramientas.','A space for your tools.')}</h3><p>${this.t('Todavía no hay extensiones aquí. Explora el registro o importa el paquete de ejemplo incluido.','No extensions here yet. Explore the registry or import the included sample package.')}</p><button class="primary-button" data-extension-mode="browse">${this.t('Explorar Open VSX','Explore Open VSX')}</button></div>`;return;}
    container.innerHTML=`<div class="extension-grid">${items.map(item=>`<article class="extension-card"><div class="extension-card-top"><div class="extension-logo">${this.extensionLogo(item)}</div><div><h4>${this.e(item.displayName||item.name)}</h4><span>${this.e(item.publisher||item.namespace||item.id?.split('.')[0])} · ${this.e(item.version)}</span></div></div><p>${this.e(item.description||this.t('Sin descripción.','No description.'))}</p><div class="extension-card-tags"><span>${mode==='installed'?this.e(item.compatibility==='partial'?this.t('Compatibilidad parcial','Partial compatibility'):this.t('Declarativa','Declarative')):this.t('Pendiente de revisión','Needs review')}</span>${mode==='installed'?`<span class="${item.enabled?'status-positive':''}">${item.enabled?this.t('Activa','Enabled'):this.t('Inactiva','Disabled')}</span>`:''}</div><div class="extension-card-actions">${mode==='installed'?`<button class="secondary-button small-button" data-extension-inspect="${this.e(item.id)}">${this.t('Reinstalar paquete','Reinstall package')}</button>${(this.extensionThemes||[]).map((theme,index)=>theme.owner===item.id?`<button class="secondary-button small-button" data-external-theme="${index}">${this.t('Aplicar tema','Apply theme')} · ${this.e(theme.label)}</button>`:'').join('')}<button class="secondary-button small-button" data-extension-toggle="${this.e(item.id)}" data-enabled="${!item.enabled}">${item.enabled?this.t('Desactivar','Disable'):this.t('Activar','Enable')}</button><button class="icon-button" data-extension-remove="${this.e(item.id)}" aria-label="${this.t('Desinstalar','Uninstall')}">${this.glyph('trash')}</button>`:`<button class="primary-button small-button" data-extension-inspect="${this.e(item.id)}">${this.t('Revisar','Review')} ${this.glyph('arrow-right')}</button>`}</div></article>`).join('')}</div>`;
    this.loadExtensionIcons(container);
  }
  async importExtension(){
    if(window.pywebview?.api?.choose_extension){const path=await window.pywebview.api.choose_extension();if(path)return this.reviewExtension({path});return;}
    this.host.modal(this.t('Importar extensión local','Import local extension'),`<p>${this.t('Introduce la ruta absoluta del paquete .vsix o .zip. Se inspecciona antes de instalar; no se ejecuta su código.','Enter the absolute path of a .vsix or .zip package. It is inspected before installation; its code is not executed.')}</p><form id="extension-import-form"><label class="field-label" for="extension-local-path">${this.t('Ruta del paquete','Package path')}</label><input id="extension-local-path" required placeholder="C:\\Downloads\\extension.vsix"><div class="modal-actions"><button class="primary-button" type="submit">${this.t('Inspeccionar','Inspect')}</button></div></form>`);
    document.getElementById('extension-import-form').onsubmit=event=>{event.preventDefault();this.safe(()=>this.reviewExtension({path:document.getElementById('extension-local-path').value}));};
  }
  async reviewExtension(request){
    const generation=this.extensionReviewGeneration=(this.extensionReviewGeneration||0)+1;
    this.host.modal(this.t(request.ticket?'Revisando dependencias':'Revisando paquete',request.ticket?'Reviewing dependencies':'Reviewing package'),extensionProgressHTML((...args)=>this.t(...args),request.id||request.path?.split(/[\\/]/).pop()||this.reviewedExtension?.id));
    let jobId;
    try{
      const job=await this.api('/extensions/review/start',request);jobId=job.id;
      const cancel=document.getElementById('extension-review-cancel');if(cancel)cancel.onclick=()=>{this.extensionReviewGeneration++;this.host.closeModal();this.safe(()=>this.api('/extensions/review/cancel',{id:jobId}));};
      let status;
      while(true){
        if(generation!==this.extensionReviewGeneration||!document.getElementById('extension-review-progress')){await this.api('/extensions/review/cancel',{id:jobId});return;}
        status=await this.api('/extensions/review?id='+encodeURIComponent(jobId));
        if(status.done)break;
        updateExtensionProgress(document,status,(...args)=>this.t(...args));
        await new Promise(resolve=>setTimeout(resolve,300));
      }
      if(status.error)throw new Error(status.error);
      if(generation!==this.extensionReviewGeneration||!document.getElementById('extension-review-progress')){await this.api('/extensions/review/cancel',{id:jobId});return;}
      const info=status.result;if(!info.plan)this.reviewedExtension=info;
      this.host.modal(this.t(info.plan?'Plan de instalación':'Revisión de extensión',info.plan?'Installation plan':'Extension review'),info.plan?extensionPlanHTML(info,(...args)=>this.t(...args)):extensionReviewHTML(info,(...args)=>this.t(...args),this.extensionLogo(info)),{wide:true});
      const prepare=document.getElementById('extension-prepare-plan');if(prepare)prepare.onclick=()=>this.safe(()=>this.reviewExtension({ticket:info.ticket,includePacks:!!document.getElementById('extension-include-packs')?.checked}));
      document.getElementById('cancel-extension-review').onclick=()=>this.safe(async()=>{await this.api('/extensions/discard',info.plan?{plan:info.plan}:{ticket:info.ticket});this.host.closeModal();});
      document.getElementById('confirm-extension-install').onclick=async()=>{
        const install=document.getElementById('confirm-extension-install'),cancel=document.getElementById('cancel-extension-review'),label=document.getElementById('extension-install-status');
        if(install.disabled)return;install.disabled=true;cancel.disabled=true;label.textContent=this.t('Instalando y guardando el paquete…','Installing and saving the package…');
        let result;try{result=await this.api('/extensions/install',{...(info.plan?{plan:info.plan}:{ticket:info.ticket}),consent:true});}
        catch(error){label.textContent=error.message;label.classList.add('status-error');install.disabled=false;cancel.disabled=false;return;}
        this.host.closeModal();this.host.notify(this.t(info.plan?'Plan instalado.':'Extensión instalada.',info.plan?'Plan installed.':'Extension installed.'));
        for(const warning of result.warnings||[])this.host.notify(warning,'error');
        await this.safe(async()=>{await this.loadContributions();await this.extensions('installed');});
      };
    }catch(error){
      if(generation!==this.extensionReviewGeneration)return;
      this.host.modal(this.t('No se pudo revisar el paquete','Package review failed'),`<div class="extension-review-error" role="alert">${this.glyph('cloud-off')}<p>${this.e(error.message)}</p></div><div class="modal-actions"><button class="secondary-button" id="extension-review-close">${this.t('Cerrar','Close')}</button><button class="primary-button" id="extension-review-retry">${this.t('Volver a intentar','Retry')}</button></div>`);
      document.getElementById('extension-review-close').onclick=()=>this.host.closeModal();
      document.getElementById('extension-review-retry').onclick=()=>this.safe(()=>this.reviewExtension(request));
    }
  }
  async exportExtensions(){
    const {extensions}=await this.api('/extensions');
    this.host.modal(this.t('Exportar extensión','Export extension'),extensions.length?`<p>${this.t('Selecciona el paquete que quieres guardar.','Choose the package to save.')}</p><div class="export-extension-list">${extensions.map(x=>`<button class="secondary-button" data-save-vsix="${this.e(x.id)}">${this.glyph('download')}${this.e(x.displayName||x.id)} <small>${this.e(x.version)}</small></button>`).join('')}</div>`:`<p>${this.t('Todavía no hay extensiones instaladas para exportar.','There are no installed extensions to export.')}</p>`);
    document.querySelectorAll('[data-save-vsix]').forEach(b=>b.onclick=()=>this.safe(async()=>{b.disabled=true;try{const result=await this.api('/extensions/export',{id:b.dataset.saveVsix});const raw=atob(result.data),bytes=Uint8Array.from(raw,c=>c.charCodeAt(0)),url=URL.createObjectURL(new Blob([bytes],{type:'application/octet-stream'})),a=document.createElement('a');a.href=url;a.download=result.filename;a.click();this.later(()=>URL.revokeObjectURL(url),1000);this.host.closeModal();}finally{b.disabled=false;}}));
  }
  async extensionUpdates(){
    const data=await this.api('/extensions/updates');
    this.host.modal(this.t('Actualizaciones disponibles','Available updates'),data.updates.length?data.updates.map(x=>`<div class="setting-row"><span>${this.e(x.id)}<small>${this.e(x.installed)} → ${this.e(x.latest)}</small></span>${x.different?`<button class="secondary-button" data-review-update="${this.e(x.id)}">${this.t('Revisar','Review')}</button>`:`<span>${this.t('Sin cambios','No changes')}</span>`}</div>`).join(''):`<p>${this.t('No hay extensiones instaladas.','No installed extensions.')}</p>`);
    document.querySelectorAll('[data-review-update]').forEach(button=>button.onclick=()=>this.safe(()=>this.reviewExtension({id:button.dataset.reviewUpdate})));
  }
  async loadContributions(){
    const data=await this.api('/extensions/contributions');this.extensionContributions=data;
    setFileIcons(data.iconThemes?.[0]);this.host.refreshFileViews?.();
    this.host.editor.configureLanguages?.(data.languages,this.development.associations);this.renderExtensionThemes(data.themes||[]);
    try{data.errors.push(...await this.host.editor.configureGrammars?.(data.grammars||[])||[]);}
    catch(error){data.errors.push({id:'textmate',error:error.message});this.host.notify('No se pudo cargar el resaltado TextMate local: '+error.message,'error');}
    for(const d of this.contributionDisposables)d.dispose?.();this.contributionDisposables=[];
    if(window.monaco){
      for(const language of new Set(data.snippets.map(x=>x.language)))this.contributionDisposables.push(monaco.languages.registerCompletionItemProvider(language,{provideCompletionItems:(model,position)=>{const w=model.getWordUntilPosition(position),range={startLineNumber:position.lineNumber,endLineNumber:position.lineNumber,startColumn:w.startColumn,endColumn:w.endColumn};return {suggestions:data.snippets.filter(x=>x.language===language).map(x=>({range,label:x.prefix,detail:x.name,kind:monaco.languages.CompletionItemKind.Snippet,insertText:x.body,insertTextRules:monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet}))};}}));
    }
    this.host.setPluginCommands(data.commands.map(c=>({id:c.id,title:c.title})));return data;
  }
  renderExtensionThemes(themes){
    this.extensionThemes=themes;this.applyPreferences();
  }
  async applyExtensionTheme(index){
    const theme=this.extensionThemes[index];if(!theme)return;
    await this.savePreference('appearance.extensionTheme',theme.id);
    this.host.notify(this.t('Tema aplicado a todo Zénit: ','Theme applied throughout Zénit: ')+theme.label);
  }
  async pluginCommand(id){const command=this.extensionContributions.commands?.find(c=>c.id===id);if(!command)return;if(command.kind==='openSettings')return this.settings(command.category);return this.reviewCode(command.body);}
  async snippets(){
    const snippets=this.extensionContributions.snippets||[];
    this.openPage('snippets',`<div class="platform-scroll"><p>${this.t('Fragmentos declarados por extensiones activas.','Snippets contributed by enabled extensions.')}</p>${snippets.length?snippets.map((s,i)=>`<button class="snippet-row" data-insert-snippet="${i}">${this.glyph('code')}<span><strong>${this.e(s.name)}</strong><small>${this.e(s.language)} · ${this.e(s.prefix)}</small></span>${this.glyph('arrow-right')}</button>`).join(''):`<div class="platform-empty">${this.glyph('code')}<p>${this.t('No hay fragmentos instalados.','No installed snippets.')}</p></div>`}</div>`);
  }
  providerSettings(){
    const selected=this.prefs['ai.provider'];const info=this.providers.find(p=>p.id===selected);const needsKey=['openai','anthropic','gemini'].includes(selected);
    return `<div class="provider-settings"><div class="provider-grid">${Object.entries(PLATFORM_NAMES).map(([id,name])=>{const state=this.providers.find(p=>p.id===id);return `<button class="provider-card ${selected===id?'selected':''}" data-provider="${id}"><span class="provider-monogram">${name[0]}</span><strong>${name}</strong><small>${state?.credential?this.t('Credencial disponible','Credential available'):id==='emma'?this.t('Motor local de Emma','Emma local engine'):id==='ollama'?this.t('Servidor local','Local server'):ACCOUNT_PROVIDERS.has(id)?this.t('Iniciar sesión con tu cuenta','Sign in with your account'):this.t('Configurar credencial','Set up credential')}</small></button>`;}).join('')}</div><div class="provider-detail"><div class="provider-detail-heading"><h4>${PLATFORM_NAMES[selected]}</h4><span class="capability-badge">${this.t('Chat + contexto + revisión','Chat + context + review')}</span></div><p>${selected==='emma'?this.t('Usa el motor y el modelo local de tu carpeta de Emma. La sesión de Zénit es independiente de sus conversaciones y recuerdos; no necesita copiar credenciales. La primera respuesta carga el modelo.','Uses the engine and local model in your Emma folder. Zénit has its own session, separate from Emma conversations and memories. No copied credentials. The first response loads the model.'):selected==='openai'?this.t('Integración mediante la API de OpenAI, no mediante la sesión web de ChatGPT.','Integrated through the OpenAI API, not your ChatGPT web session.'):ACCOUNT_PROVIDERS.has(selected)?this.t('Acceso mediante el cliente oficial. Usa Iniciar sesión para vincular tu cuenta; su plan determina la disponibilidad.','Official client access. Sign in to connect your account; your plan determines availability.'):selected==='copilot'?this.t('Usa el SDK oficial y Copilot CLI autenticada. El adaptador no concede permisos para ejecutar herramientas.','Uses the official SDK and authenticated Copilot CLI. The adapter does not grant permission to execute tools.'):selected==='ollama'?this.t('Conecta un modelo instalado en el servidor local indicado arriba.','Connect a model installed in the local server configured above.'):this.t('Conexión nativa a la API del proveedor. No se emula el servicio con otro modelo.','Native provider API connection. No substitution with another model.')}</p>${accountPanel(this,selected)}${needsKey?`<form id="provider-credential-form"><label class="field-label" for="provider-key">${this.t('Credencial de API','API credential')}</label><div class="credential-field"><input type="password" id="provider-key" autocomplete="new-password" placeholder="${info?.credential?this.t('Ya hay una credencial. Escribe otra para sustituirla.','Credential available. Enter a new one to replace it.'):this.t('Solo se envía al backend local','Sent only to the local backend')}" required><button class="secondary-button" type="submit">${this.t('Guardar','Save')}</button></div><label class="checkbox-note"><input type="checkbox" id="provider-remember">${this.t('Recordar en el almacén seguro del sistema, si está disponible.','Remember in the native secure store, when available.')}</label><p class="muted-small">${this.t('Sin marcar: solo esta sesión. No se guarda en JSON ni en localStorage.','Unchecked: this session only. Never saved in JSON or localStorage.')}</p></form>`:''}<div class="provider-detail-actions"><button class="secondary-button" id="provider-fetch-models">${this.glyph('refresh')}${this.t('Consultar modelos','Fetch models')}</button>${needsKey?`<button class="text-button" id="provider-forget-key">${this.t('Olvidar credencial','Forget credential')}</button>`:''}<span id="provider-validation-state" role="status"></span></div><div id="provider-model-results"></div></div></div>`;
  }
  bindProviders(){
    bindAccount(this);const form=document.getElementById('provider-credential-form');if(form)form.onsubmit=event=>{event.preventDefault();this.safe(async()=>{
      const field=document.getElementById('provider-key'),key=field.value;field.value='';
      await this.api('/ai/credential',{provider:this.prefs['ai.provider'],key,remember:document.getElementById('provider-remember').checked});
      this.providers=(await this.api('/ai/providers')).providers;await this.renderSettingsContent();this.host.notify(this.t('Credencial guardada sin incluirla en el proyecto.','Credential saved outside the project.'));
    });};
    const forget=document.getElementById('provider-forget-key');if(forget)forget.onclick=()=>this.safe(async()=>{await this.api('/ai/forget',{provider:this.prefs['ai.provider']});this.providers=(await this.api('/ai/providers')).providers;await this.renderSettingsContent();});
    const button=document.getElementById('provider-fetch-models');if(button)button.onclick=()=>this.safe(async()=>{
      button.disabled=true;const status=document.getElementById('provider-validation-state');status.textContent=this.t('Consultando...','Fetching...');
      try{
        const result=await this.api('/ai/models',{provider:this.prefs['ai.provider'],consent:true});
        if(!document.getElementById('provider-model-results'))return;
        status.textContent=result.note||(result.verified?this.t('Catálogo verificado; generación pendiente','Catalog verified; generation not yet tested'):this.t('Modelo del cliente; acceso pendiente de comprobar','Client model; access not yet verified'));
        document.getElementById('provider-model-results').innerHTML=`<label class="field-label" for="provider-model-select">${this.t('Modelo disponible','Available model')}</label><select id="provider-model-select"><option value="">${this.t('Selecciona un modelo','Select a model')}</option>${result.models.map(id=>`<option value="${this.e(id)}" ${id===this.prefs['ai.model']?'selected':''}>${id==='auto'?this.t('Predeterminado de la cuenta','Account default'):this.e(id)}</option>`).join('')}</select>`;
        document.getElementById('provider-model-select').onchange=event=>{if(event.target.value)this.safe(()=>this.savePreference('ai.model',event.target.value));};
      }catch(error){status.textContent=error.message;throw error;}finally{button.disabled=false;}
    });
  }
  createProviderBar(){
    const bar=document.createElement('div');bar.className='ai-provider-bar';bar.id='ai-provider-bar';
    bar.innerHTML=`<span class="provider-status-dot" aria-hidden="true"></span><select id="active-ai-provider" aria-label="Proveedor de IA">${Object.entries(PLATFORM_NAMES).map(([id,name])=>`<option value="${id}">${name}</option>`).join('')}</select><button id="active-ai-model" class="ai-model-selector"></button><button class="icon-button" id="ai-cancel-generation" hidden aria-label="Detener respuesta">${this.glyph('stop')}</button>`;
    const heading=document.querySelector('.assistant-heading');heading.after(bar);
    bar.querySelector('select').onchange=e=>this.safe(async()=>{await this.savePreference('ai.provider',e.target.value);await this.savePreference('ai.model','');this.conversation=crypto.randomUUID?.()||String(Date.now());});
    document.getElementById('active-ai-model').onclick=()=>this.safe(()=>this.settings('ai'));
    document.getElementById('ai-cancel-generation').onclick=()=>this.safe(()=>this.cancelAI());this.updateProviderBar();
  }
  updateIdentity(){
    const name=this.prefs['ai.provider']==='emma'?'Emma':'Melody';
    const select=document.getElementById('assistant-identity');if(select)select.value=name.toLowerCase();
    const title=document.querySelector('.assistant-heading-title h2');if(title)title.textContent=name;
    document.getElementById('assistant-panel')?.setAttribute('aria-label',name);
    const note=document.querySelector('.melody-disclaimer');if(note)note.textContent=name+this.t(' puede cometer errores. Verifica sus respuestas.',' can make mistakes. Check its responses.');
  }
  async switchIdentity(identity){
    if(this.aiJob)await this.api('/ai/cancel',{id:this.aiJob});
    const current=this.prefs['ai.provider'];
    if(identity==='emma'&&current!=='emma'){
      await this.savePreference('ai.melodyProvider',current);await this.savePreference('ai.melodyModel',this.prefs['ai.model']);
      await this.savePreference('ai.provider','emma');await this.savePreference('ai.model','');
      try{const data=await this.api('/ai/models',{provider:'emma',consent:true});if(data.models[0])await this.savePreference('ai.model',data.models[0]);}catch(error){this.report(error);}
    }else if(identity==='melody'&&current==='emma'){
      await this.savePreference('ai.provider',this.prefs['ai.melodyProvider']||'codex');await this.savePreference('ai.model',this.prefs['ai.melodyModel']||'');
    }
    this.conversation=crypto.randomUUID?.()||String(Date.now());this.updateProviderBar();
  }
  updateProviderBar(){this.updateIdentity();const select=document.getElementById('active-ai-provider');if(select)select.value=this.prefs['ai.provider']||'openai';const label=document.getElementById('active-ai-model');if(label){label.textContent=this.prefs['ai.model']||this.t('Configurar modelo','Configure model');label.title=this.prefs['ai.model']||this.t('Abrir ajustes de IA','Open AI settings');}}
  async sendAI(question,{edit=false}={}){
    if(this.aiStarting)return;
    if(this.aiJob||!question.trim())return;
    if(!this.prefs['ai.model']){await this.settings('ai');this.host.notify(this.t('Selecciona el proveedor y un modelo real antes de enviar.','Choose a provider and an actual model before sending.'));return;}
    const editor=this.host.editor,provider=this.prefs['ai.provider'],model=this.prefs['ai.model'],mode=this.prefs['ai.context'];
    const live=edit===true||requestsLiveEdit(question);
    const content=editor.getValue();const file=editor.current||'';
    if(live&&!file)throw new Error('Abre o crea un archivo antes de autorizar la edición.');
    if(content.length>64000)throw new Error(this.t('Selecciona un fragmento menor de 64000 caracteres.','Select less than 64000 characters.'));
    const consent=await this.host.confirmDialog(this.t('Revisar envío al modelo','Review model request'),this.t(
      `Destino: ${PLATFORM_NAMES[provider]} · ${model}. Se enviarán tu pregunta y ${content.length} caracteres ${content?'de '+file:'de código'}. El proveedor puede aplicar sus propias condiciones y costes. No se enviará el resto del proyecto. ${live?'Has solicitado edición: confirmarás el archivo antes de aplicar cambios en vivo.':'Esta petición es de consulta y no modificará tus archivos.'}`,
      `Destination: ${PLATFORM_NAMES[provider]} · ${model}. Your question and ${content.length} characters ${content?'from '+file:'of code'} will be sent. Provider terms and charges may apply. The rest of the project will not be sent. ${live?'You requested editing: confirm the file before live changes begin.':'This request is read-only and will not modify your files.'}`),this.t('Enviar esta petición','Send this request'));
    if(!consent)return;
    if(file!==editor.current||content!==editor.getValue())throw new Error('El archivo cambió durante la confirmación. Vuelve a enviar la petición con el contexto actual.');
    if(live&&!await this.host.confirmDialog('Autorizar edición en vivo',`La IA podrá reemplazar, añadir y borrar código solamente en ${file} para esta petición. Podrá continuar mientras trabajas en otro archivo. Si modificas o cierras ${file}, se detendrá. Se suspende el autoguardado de ese archivo y Ctrl+Z permite deshacer.`, 'Permitir esta edición'))return;
    if(file!==editor.current||content!==editor.getValue())throw new Error('El archivo cambió. Repite la petición.');
    const userQuestion=question;
    if(live)question+='\n\nEDICIÓN EN VIVO AUTORIZADA: devuelve el contenido COMPLETO del archivo en un único bloque de código con triple acento grave. Sin explicaciones dentro del bloque. El usuario verá los tokens aplicarse a su búfer.';
    const snapshot={path:editor.current,text:editor.getValue(),version:editor.view?.getModel?.()?.getVersionId()};this.aiSnapshot=snapshot;
    const generation=++this.aiGeneration;
    if(this.aiStarting||this.aiJob)return;this.aiStarting=true;let result;try{result=await this.api('/ai/start',{provider,model,question,content,path:file,consent:true,conversation:this.conversation});}finally{this.aiStarting=false;}
    this.aiJob=result.id;document.getElementById('ai-input').value='';document.querySelector('.send-button').disabled=true;document.getElementById('ai-cancel-generation').hidden=false;
    document.querySelector('.provider-status-dot').classList.add('generating');
    this.host.appendChat(userQuestion,'user',this.t('TÚ','YOU'));
    const element=this.host.appendChat('', 'assistant',`${PLATFORM_NAMES[provider]} · ${model}`);const stream=document.createElement('div');stream.className='ai-stream';element.appendChild(stream);
    let offset=0,text='',completed=false;this.liveEditing=live;this.liveEditingPath=live?file:null;if(live)clearTimeout(this.saveTimer);
    const liveSession=live?new LiveEditSession(editor,snapshot):null;
    if(live){document.getElementById('ai-edit-file').disabled=true;document.querySelector('.ai-live-control small').textContent='Editando en vivo · '+file;}
    try{
      while(!this.disposed&&this.aiJob===result.id&&generation===this.aiGeneration){
        const update=await this.api('/ai/job?id='+encodeURIComponent(result.id)+'&offset='+offset);offset=update.offset;text+=update.delta||'';liveSession?.apply(text);if(live)this.host.refreshFileViews();
        stream.textContent=text||update.message||this.t('Esperando al proveedor… Puedes detener la respuesta.','Waiting for provider… You can stop the response.');
        const messages=document.getElementById('chat-messages');messages.scrollTop=messages.scrollHeight;
        if(update.done){
          completed=!update.error&&!update.cancelled;
          element.remove();
          if(text){const answer=this.host.appendChat(text,'assistant',`${PLATFORM_NAMES[provider]} · ${model}`);this.addReviewButtons(answer,text,snapshot);}
          if(update.error)this.host.appendChat(update.error,'assistant',this.t('ERROR DEL PROVEEDOR','PROVIDER ERROR'));
          if(update.cancelled)this.host.appendChat(this.t('Generación cancelada. El proveedor puede haber procesado parte de la petición.','Generation cancelled. The provider may have processed part of the request.'),'assistant',this.t('CANCELADA','CANCELLED'));
          break;
        }
        await new Promise(resolve=>setTimeout(resolve,160));
      }
    }catch(error){await this.api('/ai/cancel',{id:result.id}).catch(()=>{});stream.textContent=error.message;throw error;}
    finally{liveSession?.dispose();if(live&&completed){this.host.notify(liveSession.complete?`Edición finalizada en ${file}. Revisa el archivo antes de guardarlo; Ctrl+Z permite deshacer.`:'La respuesta no contiene un archivo completo. Revisa los cambios parciales o usa Ctrl+Z.');}this.liveEditing=false;this.liveEditingPath=null;document.querySelector('.ai-live-control small').textContent='Preguntar no modifica tu archivo.';this.aiJob=null;document.querySelector('.send-button').disabled=false;document.getElementById('ai-edit-file').disabled=false;document.getElementById('ai-cancel-generation').hidden=true;document.querySelector('.provider-status-dot').classList.remove('generating');}
  }
  async cancelAI(){if(this.aiJob)await this.api('/ai/cancel',{id:this.aiJob});}
  async clearAI(){if(this.aiJob)await this.cancelAI();this.aiGeneration++;this.aiJob=null;document.getElementById('ai-cancel-generation').hidden=true;document.querySelector('#ai-form .send-button').disabled=false;await this.api('/ai/clear',{});this.conversation=crypto.randomUUID?.()||String(Date.now());}
  addReviewButtons(element,text,snapshot){
    const blocks=[...text.matchAll(/```[^\n]*\n([\s\S]*?)```/g)];
    for(const [index,pre] of [...element.querySelectorAll('pre')].entries()){
      const block=blocks[index]?.[1];if(block===undefined)continue;
      const button=document.createElement('button');button.className='review-code-button';button.innerHTML=this.glyph('split')+this.t('Revisar antes de aplicar','Review before applying');
      button.onclick=()=>this.safe(()=>this.reviewCode(block,snapshot));pre.after(button);
    }
  }
  async reviewCode(proposed,snapshot=null){
    const editor=this.host.editor;if(!editor.current)throw new Error(this.t('Abre un archivo primero.','Open a file first.'));
    snapshot=snapshot||{path:editor.current,text:editor.getValue()};
    if(editor.current!==snapshot.path||editor.getValue()!==snapshot.text)throw new Error(this.t('El archivo cambió desde que se preparó esta propuesta. Revísalo de nuevo con el contexto actual.','The file changed since this proposal was prepared. Review again with the current context.'));
    this.host.modal(this.t('Revisión de código','Code review'),`<p>${this.e(snapshot.path)} · ${this.t('Se modificará el búfer, no el disco. Guarda después de revisar.','Only the editor buffer will change. Review before saving.')}</p><div class="code-review-grid"><section><h4>${this.t('Archivo actual','Current file')}</h4><pre>${this.e(snapshot.text)}</pre></section><section><h4>${this.t('Propuesta','Proposed code')}</h4><pre>${this.e(proposed)}</pre></section></div><div class="platform-notice warning"><p>${this.t('Un bloque puede ser solo un fragmento. Sustituir el archivo reemplaza TODO su contenido.','A code block may be only a fragment. Replacing the file replaces ALL its content.')}</p></div><div class="modal-actions"><button class="secondary-button" id="review-insert">${this.t('Insertar en el cursor','Insert at cursor')}</button><button class="primary-button" id="review-replace">${this.t('Reemplazar archivo','Replace file')}</button></div>`,{wide:true});
    const apply=(replace)=>{
      if(editor.current!==snapshot.path||editor.getValue()!==snapshot.text)throw new Error(this.t('El búfer cambió. Se ha cancelado la aplicación.','Buffer changed. Application cancelled.'));
      this.host.closeModal();this.closePage();editor.insertText(proposed,replace);this.host.notify(this.t('Propuesta aplicada al búfer. Puedes deshacerla antes de guardar.','Proposal applied to the buffer. Undo is available before saving.'));
    };
    document.getElementById('review-insert').onclick=()=>this.safe(()=>apply(false));document.getElementById('review-replace').onclick=()=>this.safe(()=>apply(true));
  }
  createTerminalBar(){
    this.sessionbar=document.createElement('div');this.sessionbar.className='pty-session-bar';this.sessionbar.hidden=true;
    this.sessionbar.innerHTML=`<button class="pty-console-button">${this.glyph('terminal')}${this.t('Tareas','Tasks')}</button><div class="pty-session-tabs"></div><button class="icon-button pty-new" aria-label="${this.t('Nueva terminal','New terminal')}">${this.glyph('plus')}</button>`;
    this.ptyMount=document.createElement('div');this.ptyMount.className='pty-mount';this.ptyMount.hidden=true;
    const panel=document.getElementById('terminal-panel');panel.append(this.sessionbar,this.ptyMount);
    this.sessionbar.querySelector('.pty-console-button').onclick=()=>this.useConsole();this.sessionbar.querySelector('.pty-new').onclick=()=>this.safe(()=>this.terminalProfiles());
    this.terminalObserver=new ResizeObserver(()=>{const t=this.terminals.get(this.activeTerminal);if(t?.fit&&this.showingPTY){try{t.fit.fit();this.resizeTerminal(t);}catch(_){}}});this.terminalObserver.observe(this.ptyMount);
  }
  async terminalProfiles(){
    const data=await this.api('/terminals/profiles');data.profiles.sort((a,b)=>Number(b.id===this.prefs['terminal.defaultProfile'])-Number(a.id===this.prefs['terminal.defaultProfile']));this.detectedProfiles=data.profiles;
    this.host.modal(this.t('Abrir una terminal','Open a terminal'),`<p>${this.t('Sesiones persistentes con los permisos de tu usuario. No se ejecutan dentro de una sandbox.','Persistent sessions with your user permissions. They do not run in a sandbox.')}</p><div class="terminal-profile-list">${data.profiles.map(p=>`<button class="terminal-profile" data-open-terminal="${this.e(p.id)}" ${!data.interactiveAvailable?'disabled':''}><span class="terminal-profile-glyph">${this.glyph('terminal')}</span><span><strong>${this.e(p.label)}${p.id===this.prefs['terminal.defaultProfile']?' · '+this.t('predeterminada','default'):''}</strong><small>${this.e(p.argv[0])}</small></span><span class="capability-badge">${p.kind.toUpperCase()}</span>${this.glyph('arrow-right')}</button>`).join('')}</div>${!data.profiles.length?`<p>${this.t('No se detectaron shells compatibles.','No compatible shells detected.')}</p>`:''}${!data.interactiveAvailable?`<div class="platform-notice warning"><p>${this.t('Falta pywinpty para el terminal ConPTY de Windows. Instala requirements-desktop.txt.','pywinpty is required for ConPTY on Windows. Install requirements-desktop.txt.')}</p></div>`:''}<div class="platform-notice"><p>${this.t('CMD y PowerShell aparecen en Windows si están disponibles. WSL enumera las distribuciones instaladas, incluida Kali. CMake se administra en Herramientas: no es una shell.','CMD and PowerShell appear on Windows when available. WSL lists installed distributions, including Kali. CMake is managed in Tools: it is not a shell.')}</p></div>`);
    document.querySelectorAll('[data-open-terminal]').forEach(button=>button.onclick=()=>this.safe(()=>this.openTerminal(button.dataset.openTerminal)));
  }
  loadTerminalEngine(){
    if(this.TerminalCtor||!this.state.xterm)return;
    return this.terminalEngineLoading ||= this.loadTerminalEngineOnce().catch(error=>{this.terminalEngineLoading=null;throw error;});
  }
  async loadTerminalEngineOnce(){
    const load=src=>new Promise((resolve,reject)=>{const script=document.createElement('script');script.src=src;script.onload=resolve;script.onerror=()=>reject(new Error('Terminal renderer could not load'));document.head.append(script);});
    if(window.require?.config&&window.define?.amd){
      window.require.config({paths:{'lumen-xterm':'/vendor/xterm/xterm','lumen-fit':'/vendor/xterm-fit/addon-fit'}});
      const mods=await new Promise((resolve,reject)=>window.require(['lumen-xterm','lumen-fit'],(x,f)=>resolve([x,f]),reject));
      this.TerminalCtor=mods[0].Terminal;this.FitCtor=mods[1].FitAddon;
    }else{
      await load('/vendor/xterm/xterm.js');await load('/vendor/xterm-fit/addon-fit.js');
      this.TerminalCtor=window.Terminal;this.FitCtor=window.FitAddon.FitAddon;
    }
    if(!document.getElementById('xterm-style')){const link=document.createElement('link');link.id='xterm-style';link.rel='stylesheet';link.href='/vendor/xterm/xterm.css';document.head.append(link);}
  }
  async openTerminal(profileId){
    this.host.closeModal();if(!await this.host.ensureTrust())return;
    const result=await this.api('/terminals/create',{profile:profileId,consent:true,cols:100,rows:26});
    return this.attachTerminal(result);
  }
  async attachTerminal(result){
    const terminal={...result,offset:0,closed:false};this.terminals.set(result.id,terminal);
    terminal.input=new OrderedTerminalInput(async data=>{const response=await this.api('/terminals/write',{id:result.id,data});if(response.closed)terminal.closed=true;});
    terminal.mount=document.createElement('div');terminal.mount.className='pty-session';terminal.mount.dataset.sessionId=result.id;this.ptyMount.append(terminal.mount);
    try{await this.loadTerminalEngine();}catch(error){this.host.notify(this.t('Motor xterm no disponible; consola interactiva básica activa.','xterm unavailable; basic interactive console active.'));}
    if(this.TerminalCtor){
      terminal.xterm=new this.TerminalCtor({fontFamily:this.prefs['editor.fontFamily'],fontSize:this.prefs['terminal.fontSize'],cursorBlink:this.prefs['terminal.cursorBlink'],scrollback:this.prefs['terminal.scrollback'],allowProposedApi:false,convertEol:false});
      terminal.fit=new this.FitCtor();terminal.xterm.loadAddon(terminal.fit);terminal.xterm.open(terminal.mount);this.themeTerminal(terminal);
      terminal.xterm.onData(data=>{
        // Windows GDB/readline treats DA replies from ConPTY (including a
        // second view replaying its history) as text in the command prompt.
        // Keep cursor replies, control keys, paste and ordinary shell input.
        if(terminal.profile.kind==='hacker'&&terminal.profile.label.startsWith('GDB · ')&&isDeviceAttributesReply(data))return;
        if(!terminal.closed)this.safe(()=>terminal.input.write(data));
      });
      terminal.xterm.attachCustomKeyEventHandler(event=>{if((event.ctrlKey||event.metaKey)&&event.altKey&&['f','t'].includes(event.key.toLowerCase()))return false;return true;});
    }else{
      terminal.mount.classList.add('pty-basic');terminal.mount.innerHTML=`<div class="pty-basic-note">${this.t('PTY real · Vista básica. Instala xterm para programas de pantalla completa.','Real PTY · Basic view. Install xterm for full-screen applications.')}</div><pre class="pty-basic-output" role="log"></pre><form class="pty-basic-input"><span>❯</span><input aria-label="${this.t('Entrada de terminal','Terminal input')}" spellcheck="false" autocomplete="off"><button type="button" class="text-button pty-interrupt">Ctrl C</button><button class="icon-button" aria-label="${this.t('Enviar','Send')}">${this.glyph('send')}</button></form>`;
      terminal.output=terminal.mount.querySelector('pre');const input=terminal.mount.querySelector('input');
      terminal.mount.querySelector('form').onsubmit=event=>{event.preventDefault();const data=input.value+'\r';input.value='';this.safe(()=>terminal.input.write(data));};
      terminal.mount.querySelector('.pty-interrupt').onclick=()=>this.safe(()=>terminal.input.write('\u0003'));
      input.onkeydown=event=>{if(event.ctrlKey&&['c','d'].includes(event.key.toLowerCase())){event.preventDefault();this.safe(()=>terminal.input.write(event.key.toLowerCase()==='c'?'\u0003':'\u0004'));}};
    }
    this.selectTerminal(result.id);this.pollTerminal(terminal);return result;
  }
  themeTerminal(terminal){if(!terminal.xterm)return;const css=getComputedStyle(document.documentElement),get=k=>css.getPropertyValue('--'+k).trim();terminal.xterm.options.theme={background:get('terminal-bg'),foreground:get('terminal-text')||get('text'),cursor:get('accent'),selectionBackground:get('selection'),black:get('bg'),red:get('danger'),green:get('success'),yellow:get('syntax-string'),blue:get('syntax-function'),magenta:get('syntax-keyword'),cyan:get('syntax-type'),white:get('text')};}
  selectTerminal(id){
    this.activeTerminal=id;this.showingPTY=true;this.host.dock.show('console');this.renderActiveTerminal();
    this.later(()=>{const terminal=this.terminals.get(id);if(terminal?.fit){terminal.fit.fit();this.resizeTerminal(terminal);}terminal?.xterm?.focus();terminal?.mount.querySelector('input')?.focus();},80);
  }
  renderActiveTerminal(){
    this.sessionbar.hidden=!this.terminals.size;this.ptyMount.hidden=!this.showingPTY;
    if(this.showingPTY){document.getElementById('terminal-scroll').classList.add('hidden');document.getElementById('terminal-content').classList.add('hidden');document.querySelector('.terminal-signature').classList.add('hidden');}
    const tabs=this.sessionbar.querySelector('.pty-session-tabs');tabs.innerHTML=[...this.terminals.values()].map(t=>`<div class="pty-tab ${this.activeTerminal===t.id&&this.showingPTY?'active':''}"><button data-pty-select="${t.id}">${this.glyph('terminal')}<span>${this.e(t.profile.label)}${t.closed?' · '+this.t('cerrada','closed'):''}</span></button><button class="pty-tab-close" data-pty-close="${t.id}" aria-label="${this.t('Cerrar terminal','Close terminal')}">${this.glyph('close')}</button></div>`).join('');
    tabs.querySelectorAll('[data-pty-select]').forEach(b=>b.onclick=()=>this.selectTerminal(b.dataset.ptySelect));tabs.querySelectorAll('[data-pty-close]').forEach(b=>b.onclick=()=>this.safe(()=>this.closeTerminal(b.dataset.ptyClose)));
    for(const t of this.terminals.values())t.mount.hidden=t.id!==this.activeTerminal;
  }
  useConsole(){this.showingPTY=false;this.ptyMount.hidden=true;this.host.showConsole();this.renderActiveTerminal();}
  async resizeTerminal(terminal){if(terminal.closed||!terminal.xterm)return;try{await this.api('/terminals/resize',{id:terminal.id,cols:terminal.xterm.cols,rows:terminal.xterm.rows});}catch(_){}}
  async pollTerminal(terminal){
    if(this.disposed||!this.terminals.has(terminal.id))return;
    try{
      const data=await this.api('/terminals/read?id='+terminal.id+'&offset='+terminal.offset);terminal.offset=data.offset;
      if(data.data){if(terminal.xterm)terminal.xterm.write(data.data);else{terminal.output.textContent=(terminal.output.textContent+this.stripTerminal(data.data)).slice(-180000);terminal.output.scrollTop=terminal.output.scrollHeight;}}
      if(data.closed){terminal.closed=true;terminal.input.close();this.renderActiveTerminal();return;}
    }catch(error){terminal.closed=true;terminal.input.close(error);if(terminal.output)terminal.output.textContent+='\n'+error.message;this.renderActiveTerminal();return;}
    this.later(()=>this.pollTerminal(terminal),document.hidden?1000:80);
  }
  stripTerminal(text){return text.replace(/\x1b\][^\x07]*(?:\x07|\x1b\\)/g,'').replace(/\x1b\[[0-?]*[ -/]*[@-~]/g,'').replace(/\r/g,'');}
  async closeTerminal(id){
    const t=this.terminals.get(id);if(!t)return;
    if(!t.closed&&this.prefs['terminal.confirmClose']&&!await this.host.confirmDialog(this.t('Cerrar terminal','Close terminal'),this.t('Se terminarán la shell y sus procesos asociados.','The shell and its child processes will be terminated.'),this.t('Cerrar sesión','Close session')))return;
    t.input.close();await this.api('/terminals/close',{id});t.xterm?.dispose();t.mount.remove();this.terminals.delete(id);
    if(this.activeTerminal===id){const next=this.terminals.keys().next().value;if(next)this.selectTerminal(next);else this.useConsole();}
    this.renderActiveTerminal();
  }
  developmentSettings(){
    return `<h3>${this.t('Una configuración, tus herramientas.','One configuration, your tools.')}</h3><p class="platform-lead">${this.t('Define ejecutables por argumentos, tareas de compilación y servidores LSP. Guardar esta configuración no ejecuta ningún programa. Las rutas pertenecen al sistema en el que se está ejecutando Python.','Define argument-based commands, build tasks and LSP servers. Saving does not execute anything. Paths belong to the system running Python.')}</p><div class="platform-notice">${this.glyph('code')}<p>${this.t('Puedes editar cualquier archivo de texto. El análisis, autocompletado y compilado dependen de las herramientas reales de cada lenguaje. No se simula un compilador universal.','Any text file can be edited. Analysis, completion and compilation require the real tools for each language. There is no simulated universal compiler.')}</p></div><div class="development-actions"><button class="secondary-button" data-development-template="cmake">CMake</button><button class="secondary-button" data-development-template="cpp">C / C++ · clangd</button><button class="secondary-button" data-development-template="python">Python · pylsp</button><button class="secondary-button" data-platform="tools">${this.glyph('build')}${this.t('Detectar herramientas','Detect tools')}</button></div><form id="development-form"><label class="field-label" for="development-json">development.json</label><textarea id="development-json" class="configuration-json" spellcheck="false" aria-label="JSON de tareas y lenguajes">${this.e(JSON.stringify(this.development,null,2))}</textarea><p class="form-hint">${this.t('Variables:','Variables:')} <code>\${workspaceFolder}</code> <code>\${file}</code> <code>\${fileBasenameNoExtension}</code>. ${this.t('Las asociaciones asignan sufijos a un identificador de lenguaje.','Associations map file suffixes to a language identifier.')}</p><button class="primary-button" type="submit">${this.glyph('check')}${this.t('Validar y guardar','Validate and save')}</button></form>`;
  }
  bindDevelopment(){
    const form=this.workbench.querySelector('#development-form');if(!form)return;
    form.onsubmit=event=>{event.preventDefault();this.safe(async()=>{this.development=await this.api('/development',JSON.parse(document.getElementById('development-json').value));this.state.development=this.development;await this.loadContributions();this.host.notify(this.t('Configuración validada. Ningún ejecutable se ha iniciado.','Configuration validated. No executable was started.'));});};
    form.parentElement.querySelectorAll('[data-development-template]').forEach(button=>button.onclick=()=>{
      this.safe(async()=>{const textarea=document.getElementById('development-json'),config=JSON.parse(textarea.value);config.tasks??=[];config.servers??=[];config.associations??={};
        const add=(key,entry)=>{if(!config[key].some(x=>x.id===entry.id))config[key].push(entry);};
        if(button.dataset.developmentTemplate==='cmake'){add('tasks',{id:'cmake.configure',label:'CMake · configure',argv:['cmake','-S','${workspaceFolder}','-B','${workspaceFolder}/build']});add('tasks',{id:'cmake.build',label:'CMake · build',argv:['cmake','--build','${workspaceFolder}/build']});}
        if(button.dataset.developmentTemplate==='cpp')add('servers',{id:'clangd',label:'C / C++ · clangd',argv:['clangd'],languages:['c','cpp']});
        if(button.dataset.developmentTemplate==='python')add('servers',{id:'pylsp',label:'Python · pylsp',argv:['pylsp'],languages:['python']});
        textarea.value=JSON.stringify(config,null,2);textarea.focus();
      });
    });
  }
  async tools(refresh=false){
    this.openPage('tools',`<div class="platform-loading">${this.t('Consultando el sistema...','Checking this system...')}</div>`);
    const result=await this.api('/tools'+(refresh?'?refresh=1':''));if(this.page!=='tools')return;this.toolsState=result;this.development=result.config;
    const packages=Object.entries(result.packages).filter(([,managers])=>result.managers.some(m=>managers[m]));
    this.openPage('tools',`<div class="platform-content tools-content"><div class="section-heading"><div><span class="platform-eyebrow">${this.e(result.platform)} · LOCAL</span><h3>${this.t('Herramientas, no suposiciones.','Tools, not assumptions.')}</h3><p>${this.t('Estas rutas se han encontrado en PATH. No se ha ejecutado cada compilador para mostrar esta lista.','These paths were found in PATH. Compilers have not been executed merely to show this list.')}</p></div><button class="icon-button" data-platform="tools-refresh" title="${this.t('Volver a detectar','Refresh detection')}">${this.glyph('refresh')}</button></div><div class="tools-summary"><span><strong>${result.tools.filter(x=>x.available).length}</strong>${this.t('herramientas detectadas','tools detected')}</span><span><strong>${this.development.tasks.length}</strong>${this.t('tareas definidas','configured tasks')}</span><span><strong>${this.lspSessions.size}</strong>${this.t('servidores activos','active servers')}</span></div><div class="tool-sections"><section><h4>${this.t('Tareas del proyecto','Project tasks')}</h4>${this.development.tasks.length?this.development.tasks.map(task=>`<div class="tool-task"><div><strong>${this.e(task.label)}</strong><code>${this.e(task.argv.join(' '))}</code></div><button class="icon-button" data-task-run="${this.e(task.id)}" title="${this.t('Revisar y ejecutar','Review and run')}">${this.glyph('play')}</button></div>`).join(''):`<p class="muted-copy">${this.t('Define tareas CMake, compiladores o intérpretes en ajustes.','Configure CMake tasks, compilers or interpreters in settings.')}</p>`}<button class="text-button" data-setting-category="development">${this.t('Configurar tareas','Configure tasks')} ${this.glyph('arrow-right')}</button></section><section><h4>${this.t('Inteligencia de lenguajes · LSP','Language intelligence · LSP')}</h4>${this.development.servers.map(server=>{const active=[...this.lspSessions.values()].find(s=>s.profile===server.id);return `<div class="tool-task"><div><strong>${this.e(server.label)}</strong><small>${this.e(server.languages.join(' · '))}</small></div><button class="secondary-button small-button" ${active?`data-lsp-stop="${active.id}"`:`data-lsp-start="${this.e(server.id)}"`}>${active?this.t('Detener','Stop'):this.t('Iniciar','Start')}</button></div>`;}).join('')||`<p class="muted-copy">${this.t('Ningún servidor configurado. No se inicia código de terceros sin autorización.','No server configured. Third-party code never starts without approval.')}</p>`}<button class="text-button" data-setting-category="development">${this.t('Configurar servidores','Configure servers')} ${this.glyph('arrow-right')}</button></section></div><section class="detected-tools"><h4>${this.t('Herramientas instaladas','Installed tools')}</h4><div class="tool-grid">${result.tools.map(tool=>`<div class="tool-entry ${tool.available?'available':''}"><span class="state-dot"></span><div><strong>${this.e(tool.label)}</strong><small title="${this.e(tool.path||'')}">${this.e(tool.path||this.t('No encontrado','Not found'))}</small></div></div>`).join('')}</div></section><section class="tool-installer"><h4>${this.t('Instalar con tu gestor de paquetes','Install with your package manager')}</h4><p>${this.t('Genera un plan revisable. El gestor puede pedir licencias, red o permisos de administrador. No se instala nada al abrir esta pantalla.','Generate a reviewable plan. The package manager may request licences, network or administrator privileges. Nothing is installed by opening this page.')}</p>${result.managers.length?`<form id="tool-plan-form"><select id="tool-package" aria-label="Paquete">${packages.map(([id])=>`<option>${this.e(id)}</option>`).join('')}</select><select id="tool-manager" aria-label="Gestor">${result.managers.map(id=>`<option>${this.e(id)}</option>`).join('')}</select><button class="secondary-button">${this.glyph('download')}${this.t('Preparar instalación','Prepare installation')}</button></form>`:`<p class="muted-copy">${this.t('No se ha detectado winget, Homebrew, apt, dnf ni pacman. Instala la herramienta desde su distribuidor y configura su ruta absoluta.','No winget, Homebrew, apt, dnf or pacman detected. Install the tool from its publisher and configure its absolute path.')}</p>`}</section></div>`);
    const form=this.workbench.querySelector('#tool-plan-form');if(form)form.onsubmit=event=>{event.preventDefault();this.safe(()=>this.installPlan(document.getElementById('tool-package').value,document.getElementById('tool-manager').value));};
  }
  async installPlan(packageId,manager){
    const plan=await this.api('/tools/plan',{package:packageId,manager});this.host.modal(this.t('Revisar instalación','Review installation'),`<p>${this.e(plan.note)}</p><pre class="review-command">${this.e(plan.command)}</pre><p>${this.t('Puedes copiar el comando o colocarlo en una terminal. Se enviará SIN pulsar Enter: revisa el destino y ejecútalo tú. No se eleva el IDE.','Copy the command or place it in a terminal. It is sent WITHOUT Enter: review the destination and run it yourself. The IDE does not elevate itself.')}</p><div class="modal-actions"><button class="secondary-button" id="plan-copy">${this.t('Copiar','Copy')}</button><button class="primary-button" id="plan-terminal">${this.t('Preparar en terminal','Prepare in terminal')}</button></div>`);
    document.getElementById('plan-copy').onclick=()=>this.safe(async()=>{await navigator.clipboard.writeText(plan.command);this.host.notify(this.t('Comando copiado.','Command copied.'));});
    document.getElementById('plan-terminal').onclick=()=>this.safe(async()=>{
      this.host.closeModal();let terminal=this.terminals.get(this.activeTerminal);
      if(!terminal||terminal.closed){const profiles=await this.api('/terminals/profiles');const first=profiles.profiles.find(p=>p.available!==false);if(!first)throw new Error(this.t('No hay una terminal disponible.','No terminal available.'));const created=await this.openTerminal(first.id);if(!created)return;terminal=this.terminals.get(created.id);}
      this.selectTerminal(terminal.id);
      if(terminal.xterm)await terminal.input.write(plan.command);else{terminal.mount.querySelector('input').value=plan.command;terminal.mount.querySelector('input').focus();}
    });
  }
  async runTask(id){
    const task=this.development.tasks.find(x=>x.id===id);if(!task)return;
    if(!await this.host.ensureTrust())return;
    if(!await this.host.confirmDialog(this.t('Ejecutar tarea','Run task'),task.label+'\n'+JSON.stringify(task.argv),this.t('Ejecutar','Run')))return;
    this.useConsole();const result=await this.api('/tasks/run',{id,file:this.host.editor.current||'',consent:true});await this.host.watchJob(result.job);
  }
  async startLSP(profile,automatic=false){
    if(!await this.host.ensureTrust())return;
    const config=this.development.servers.find(x=>x.id===profile);if(!config)return;
    if(!automatic&&!await this.host.confirmDialog(this.t('Iniciar servidor de lenguaje','Start language server'),this.t('Este programa tendrá los permisos de tu usuario y podrá leer el proyecto. LSP no es una caja de aislamiento.\n','This executable runs with your user permissions and can read the project. LSP is not a sandbox.\n')+JSON.stringify(config.argv),this.t('Autorizar e iniciar','Approve and start')))return;
    const s=await this.api('/lsp/start',{profile,consent:true});s.offset=0;s.documents=new Map();s.disposables=[];s.syncChain=Promise.resolve();this.lspSessions.set(s.id,s);
    this.registerLSP(s);await this.syncLSP(s);this.pollLSP(s);this.updateSystemStatus();if(this.page==='tools')await this.tools();
  }
  uriFor(s,path){return s.rootUri.replace(/\/$/,'')+'/'+path.split('/').map(encodeURIComponent).join('/');}
  activeLSP(path=this.host.editor.current){return [...this.lspSessions.values()].find(s=>s.languages.includes(languageFor(path||'')));}
  async syncLSP(s){
    s.syncChain=s.syncChain.catch(()=>{}).then(async()=>{
      for(const [path,record] of this.host.editor.models){if(!s.languages.includes(languageFor(path)))continue;
        const text=path===this.host.editor.current?this.host.editor.getValue():record.value,previous=s.documents.get(path),uri=this.uriFor(s,path);
        if(!previous){await this.api('/lsp/notify',{id:s.id,method:'textDocument/didOpen',params:{textDocument:{uri,languageId:languageFor(path),version:1,text}}});s.documents.set(path,{text,version:1});}
        else if(previous.text!==text){const version=previous.version+1,sync=s.capabilities.textDocumentSync,kind=typeof sync==='number'?sync:sync?.change;
          const change={text};if(kind===2){const lines=previous.text.split('\n');change.range={start:{line:0,character:0},end:{line:lines.length-1,character:lines.at(-1).length}};change.rangeLength=previous.text.length;}
          if(kind!==0)await this.api('/lsp/notify',{id:s.id,method:'textDocument/didChange',params:{textDocument:{uri,version},contentChanges:[change]}});
          s.documents.set(path,{text,version});
        }
      }
      for(const path of [...s.documents.keys()])if(!this.host.editor.models.has(path)){await this.api('/lsp/notify',{id:s.id,method:'textDocument/didClose',params:{textDocument:{uri:this.uriFor(s,path)}}});s.documents.delete(path);}
    });return s.syncChain;
  }
  async requestLSP(method,position,path=this.host.editor.current,extra={}){
    const s=this.activeLSP(path);if(!s)throw new Error(this.t('Configura e inicia un servidor LSP para este lenguaje.','Configure and start an LSP server for this language.'));
    await this.syncLSP(s);const params={...extra,textDocument:{uri:this.uriFor(s,path)}};if(position)params.position=position;
    return (await this.api('/lsp/request',{id:s.id,method,params})).result;
  }
  registerLSP(s){
    if(this.host.editor.kind!=='monaco')return;
    const m=window.monaco,pathOf=model=>[...this.host.editor.models.entries()].find(([,r])=>r.model===model)?.[0];
    for(const lang of s.languages){
      if(s.capabilities.completionProvider)s.disposables.push(m.languages.registerCompletionItemProvider(lang,{triggerCharacters:s.capabilities.completionProvider.triggerCharacters||[],provideCompletionItems:async(model,position)=>{
        const path=pathOf(model);if(!path)return {suggestions:[]};try{const result=await this.requestLSP('textDocument/completion',{line:position.lineNumber-1,character:position.column-1},path),items=Array.isArray(result)?result:result?.items||[],word=model.getWordUntilPosition(position);
          return {suggestions:items.slice(0,300).map(item=>{const edit=item.textEdit,r=edit?.range||edit?.replace;return {label:item.label,detail:item.detail||'',kind:Math.max(0,(item.kind||1)-1),insertText:edit?.newText??item.insertText??item.label,insertTextRules:item.insertTextFormat===2?m.languages.CompletionItemInsertTextRule.InsertAsSnippet:undefined,range:r?{startLineNumber:r.start.line+1,startColumn:r.start.character+1,endLineNumber:r.end.line+1,endColumn:r.end.character+1}:{startLineNumber:position.lineNumber,endLineNumber:position.lineNumber,startColumn:word.startColumn,endColumn:word.endColumn},sortText:item.sortText,filterText:item.filterText};})};
        }catch(_){return {suggestions:[]};}
      }}));
      if(s.capabilities.hoverProvider)s.disposables.push(m.languages.registerHoverProvider(lang,{provideHover:async(model,pos)=>{try{const result=await this.requestLSP('textDocument/hover',{line:pos.lineNumber-1,character:pos.column-1},pathOf(model));if(!result)return null;const c=result.contents,text=Array.isArray(c)?c.map(x=>typeof x==='string'?x:x.value).join('\n\n'):typeof c==='string'?c:c?.value||'';return {contents:[{value:text,isTrusted:false,supportHtml:false}]};}catch(_){return null;}}}));
      if(s.capabilities.definitionProvider)s.disposables.push(m.languages.registerDefinitionProvider(lang,{provideDefinition:async(model,pos)=>{try{const result=await this.requestLSP('textDocument/definition',{line:pos.lineNumber-1,character:pos.column-1},pathOf(model));const locations=[];for(const item of (Array.isArray(result)?result:result?[result]:[])){const uri=item.uri||item.targetUri,path=this.relativeURI(s,uri),r=item.range||item.targetSelectionRange;if(!path||!r)continue;locations.push({uri:this.host.editor.models.get(path)?.model?.uri||m.Uri.parse('file:///'+path),range:{startLineNumber:r.start.line+1,startColumn:r.start.character+1,endLineNumber:r.end.line+1,endColumn:r.end.character+1}});}return locations;}catch(_){return [];}}}));
      if(s.capabilities.inlayHintProvider)s.disposables.push(m.languages.registerInlayHintsProvider(lang,{provideInlayHints:async(model,range)=>{try{const result=await this.requestLSP('textDocument/inlayHint',null,pathOf(model),{range:{start:{line:range.startLineNumber-1,character:range.startColumn-1},end:{line:range.endLineNumber-1,character:range.endColumn-1}}});return {hints:(result||[]).map(h=>({position:{lineNumber:h.position.line+1,column:h.position.character+1},label:typeof h.label==='string'?h.label:h.label.map(p=>p.value).join(''),kind:h.kind,paddingLeft:h.paddingLeft,paddingRight:h.paddingRight,tooltip:typeof h.tooltip==='string'?h.tooltip:h.tooltip?.value})),dispose(){}};}catch(_){return {hints:[],dispose(){}};}}}));
      if(s.capabilities.semanticTokensProvider?.legend)s.disposables.push(m.languages.registerDocumentSemanticTokensProvider(lang,{getLegend:()=>s.capabilities.semanticTokensProvider.legend,releaseDocumentSemanticTokens(){},provideDocumentSemanticTokens:async(model)=>{try{const result=await this.requestLSP('textDocument/semanticTokens/full',null,pathOf(model));return result?{data:new Uint32Array(result.data),resultId:result.resultId}:null;}catch(_){return null;}}}));
    }
  }
  relativeURI(s,uri){const prefix=s.rootUri.replace(/\/$/,'')+'/';if(typeof uri!=='string'||!uri.startsWith(prefix))return null;try{return decodeURIComponent(uri.slice(prefix.length));}catch(_){return null;}}
  async pollLSP(s){
    if(this.disposed||!this.lspSessions.has(s.id))return;
    try{const result=await this.api('/lsp/events?id='+s.id+'&after='+s.offset);s.offset=result.sequence;
      for(const event of result.events)if(event.method==='textDocument/publishDiagnostics'){
        const p=event.params,path=this.relativeURI(s,p.uri);if(!path)continue;const record=s.documents.get(path);if(p.version!=null&&record&&p.version<record.version)continue;
        const diagnostics=(p.diagnostics||[]).slice(0,500);this.diagnosticMap.set(path,diagnostics);
        if(this.host.editor.kind==='monaco'){const model=this.host.editor.models.get(path)?.model;if(model)window.monaco.editor.setModelMarkers(model,'lumen-lsp',diagnostics.map(d=>({message:String(d.message||''),severity:({1:8,2:4,3:2,4:1})[d.severity]||2,startLineNumber:d.range.start.line+1,startColumn:d.range.start.character+1,endLineNumber:d.range.end.line+1,endColumn:d.range.end.character+1})));}
      }
      this.refreshDiagnostics();if(result.closed){await this.stopLSP(s.id,false);this.host.notify(this.t('El servidor de lenguaje ha terminado.','Language server exited.'),'warning');return;}
    }catch(error){await this.stopLSP(s.id,false);this.report(error);return;}
    this.later(()=>this.pollLSP(s),document.hidden?1500:400);
  }
  refreshDiagnostics(){this.host.editor.externalDiagnostics=[...(this.diagnosticMap.get(this.host.editor.current)||[])].map(d=>({message:String(d.message||''),severity:d.severity===1?8:d.severity===2?4:2,startLineNumber:d.range.start.line+1,startColumn:d.range.start.character+1}));this.host.updateDiagnostics(this.host.editor.diagnostics());}
  async stopLSP(id,remote=true){const s=this.lspSessions.get(id);if(!s)return;s.disposables.forEach(d=>d.dispose());this.lspSessions.delete(id);if(remote)await this.api('/lsp/stop',{id});for(const path of s.documents.keys()){this.diagnosticMap.delete(path);const model=this.host.editor.models.get(path)?.model;if(model&&window.monaco)window.monaco.editor.setModelMarkers(model,'lumen-lsp',[]);}this.refreshDiagnostics();this.updateSystemStatus();if(this.page==='tools')await this.tools();}
  async languageAction(method='textDocument/completion'){
    const ed=this.host.editor;if(!ed.current)return;
    if(method==='textDocument/completion'&&ed.kind==='monaco'){ed.view.trigger('keyboard','editor.action.triggerSuggest',{});return;}
    const position=ed.kind==='monaco'?{line:ed.view.getPosition().lineNumber-1,character:ed.view.getPosition().column-1}:(()=>{const lines=ed.input.value.slice(0,ed.input.selectionStart).split('\n');return {line:lines.length-1,character:lines.at(-1).length};})();
    const result=await this.requestLSP(method,position);
    if(method==='textDocument/completion'){
      const items=(Array.isArray(result)?result:result?.items||[]).slice(0,80),path=ed.current,snapshot=ed.getValue(),selection=ed.getSelection();
      this.host.modal(this.t('Sugerencias del servidor','Language server suggestions'),`<div class="lsp-result-list">${items.map((item,i)=>`<button data-lsp-item="${i}"><strong>${this.e(item.label)}</strong><small>${this.e(item.detail||'')}</small></button>`).join('')||this.t('Sin sugerencias.','No suggestions.')}</div>`);
      document.querySelectorAll('[data-lsp-item]').forEach(button=>button.onclick=()=>{const item=items[Number(button.dataset.lspItem)],text=item.textEdit?.newText??item.insertText??item.label;this.reviewCode(String(text),{path,text:snapshot,selection});});
    }else this.host.modal(this.t('Respuesta del servidor','Language server response'),`<pre class="lsp-response">${this.e(JSON.stringify(result,null,2))}</pre>`);
  }
  autoLanguageServer(){
    if(!this.host.isTrusted?.()||!this.prefs['editor.autoLanguageServer']||!this.prefs['editor.completion'])return;
    const language=languageFor(this.host.editor.current||'');if(this.activeLSP())return;
    const config=this.development?.servers?.find(x=>x.languages.includes(language));if(!config)return;
    this.languageAttempts??=new Set();if(this.languageAttempts.has(config.id))return;
    this.languageAttempts.add(config.id);
    // Trust is established by the existing workspace dialog; never bypass it.
    this.safe(()=>this.startLSP(config.id,true));
  }
  documentChanged(){
    if(this.disposed)return;this.autoLanguageServer();this.lantern?.changed();if(this.liveEditingPath===this.host.editor.current){clearTimeout(this.saveTimer);return;}clearTimeout(this.changeTimer);this.changeTimer=this.later(()=>{for(const s of this.lspSessions.values())this.safe(()=>this.syncLSP(s));this.refreshDiagnostics();},220);
    clearTimeout(this.syntaxTimer);const ed=this.host.editor,path=ed.current,text=ed.getValue();
    if(path&&text.length<250000)this.syntaxTimer=this.later(async()=>{try{const result=await this.api('/diagnostics',{path,content:text});if(this.disposed||ed.models.get(path)?.value!==text)return;ed.setDiagnostics(path,result.diagnostics);}catch(_){}},700);
    clearTimeout(this.saveTimer);const live=this.lantern?.state.active;if(this.prefs['files.autoSave']&&!live&&ed.isDirty())this.saveTimer=this.later(()=>{if(this.prefs['files.autoSave']&&ed.current===path&&this.liveEditingPath!==path&&ed.isDirty())this.safe(()=>this.host.saveFile(path,{automatic:true}));},live?1100:this.prefs['files.autoSaveDelay']);
  }
  async checkSaved(path){
    if(!/\.(c|cpp|cc|cxx|cs|rs|go|java|nc|n)$/i.test(path)||this.lantern?.state.active)return;
    const ed=this.host.editor,snapshot=ed.models.get(path)?.value;
    try{const result=await this.api('/diagnostics/check',{path});if(!result.job)return;let output='',offset=0;
      for(let i=0;i<100&&!this.disposed;i++){const state=await this.host.api('/job?id='+result.job+'&offset='+offset);offset=state.offset;output+=state.output;if(state.done){if(ed.models.get(path)?.value===snapshot){const parsed=await this.api('/diagnostics/output',{path,output});ed.setDiagnostics(path,parsed.diagnostics,'lumen-build');}break;}await new Promise(r=>setTimeout(r,240));}
    }catch(_){}
  }
  async afterSave(path){this.checkSaved(path);for(const s of this.lspSessions.values())if(s.documents.has(path)){await this.syncLSP(s);await this.api('/lsp/notify',{id:s.id,method:'textDocument/didSave',params:{textDocument:{uri:this.uriFor(s,path)}}});}}
  createStatus(){
    this.systemStatus=document.createElement('button');this.systemStatus.className='status-item platform-system-status';this.systemStatus.dataset.platform='hardware';this.systemStatus.title=this.t('Sistema y rendimiento','System and performance');document.querySelector('.status-spacer').before(this.systemStatus);
    this.focusStatus=document.createElement('button');this.focusStatus.className='status-item focus-indicator';this.focusStatus.dataset.platform='focus';this.focusStatus.hidden=true;document.querySelector('.status-spacer').before(this.focusStatus);this.updateSystemStatus();
  }
  updateSystemStatus(){
    if(!this.systemStatus)return;const metric=this.hardwareState;
    const value=this.prefs['hardware.enabled']&&metric?.processRSS?`${Math.round(metric.processRSS/1048576)} MB`:this.t('Sistema','System');
    this.systemStatus.innerHTML=this.glyph('cpu')+`<span>${value}</span>`+(this.lspSessions.size?`<span class="lsp-status">LSP ${this.lspSessions.size}</span>`:'');
    const focused=this.host.dock.snapshot().preset==='focus';this.focusStatus.hidden=!focused;this.focusStatus.innerHTML=this.glyph('focus')+`<span>${this.t('Concentración','Focus')}</span>`;document.documentElement.classList.toggle('lumen-focus-active',focused);
  }
  setFocus(state='toggle'){const focused=this.host.dock.snapshot().preset==='focus';if(state==='toggle'||(state==='on'&&!focused)||(state==='off'&&focused)){if(!focused&&this.page)this.closePage();this.host.dock.focus();}this.updateSystemStatus();}
  hardwareMarkup(){
    const data=this.hardwareState,p=this.prefs;const format=bytes=>bytes==null?'—':(bytes/1073741824).toFixed(1)+' GB';
    return `<div class="hardware-overview"><div class="hardware-chip">${this.glyph('cpu')}<span>${this.e(data?.system||'LOCAL')} · ${this.e(data?.machine||'')}</span></div><h3>${this.t('Tu sistema. Datos reales.','Your system. Real measurements.')}</h3><p>${this.t('Lectura mediante las API del sistema operativo. Sin controladores propios, cambios de frecuencia ni acceso privilegiado.','Read-only operating-system APIs. No custom drivers, clock changes or privileged access.')}</p><div class="hardware-metrics">${[[this.t('CPU del sistema','System CPU'),data?.cpuPercent==null?'—':data.cpuPercent.toFixed(1)+'%'],[this.t('RAM utilizada','Memory in use'),format(data?.memoryUsed)],[this.t('RAM del servicio Python','Python service memory'),data?.processRSS==null?'—':Math.round(data.processRSS/1048576)+' MB']].map(([label,value])=>`<div><span>${label}</span><strong>${p['hardware.enabled']?value:'—'}</strong></div>`).join('')}</div><p class="form-hint">${p['hardware.enabled']?this.t('El proceso mostrado es el servicio Python, no la suma de todos los procesos del navegador. La disponibilidad de GPU depende de nvidia-smi.','The process measurement covers Python, not all browser processes. GPU information depends on nvidia-smi.'):this.t('La lectura está desactivada. Actívala expresamente en ajustes.','Monitoring is off. Enable it explicitly in settings.')}</p>${data?.gpus?.length?`<div class="gpu-list">${data.gpus.map(g=>`<div><strong>${this.e(g.name)}</strong><span>${this.e(g.utilization)}% · ${this.e(g.memoryUsedMiB)} / ${this.e(g.memoryTotalMiB)} MiB</span></div>`).join('')}</div>`:''}<div class="hardware-capabilities"><span>${this.t('Editor','Editor')}: ${this.e(this.host.editor.kind)}</span><span>${this.t('Gráficos','Graphics')}: ${this.e(this.host.graphicsKind())}</span><span>PTY: ${this.state.xterm?'xterm.js':this.t('visor básico','basic view')}</span></div></div>`;
  }
  async hardware(){this.hardwareState=await this.api('/hardware');this.openPage('hardware',`<div class="platform-content">${this.hardwareMarkup()}<button class="secondary-button" data-setting-category="hardware">${this.glyph('sliders')}${this.t('Configurar lecturas','Configure monitoring')}</button></div>`);}
  async scheduleHardware(){
    if(this.disposed)return;
    if(this.prefs['hardware.enabled']&&!document.hidden){try{this.hardwareState=await this.api('/hardware');this.updateSystemStatus();if(this.page==='hardware'){const div=this.workbench.querySelector('.hardware-overview');if(div)div.outerHTML=this.hardwareMarkup();}}catch(_){} }
    this.later(()=>this.scheduleHardware(),Math.max(1000,this.prefs['hardware.interval']||2500));
  }
  async scheduleCommands(){
    if(this.disposed)return;
    try{const data=await this.api('/ui/events?after='+this.commandSequence);this.commandSequence=data.sequence;for(const event of data.events){if(event.command.startsWith('zenit.'))await this.extensionServices?.event(event);else if(event.command.startsWith('lumen.focus.'))this.setFocus(event.command.split('.').at(-1));else if(event.command==='lumen.settings.open')this.settings();else if(event.command==='lumen.extensions.open')this.extensions();else if(event.command==='lumen.lantern.open')this.safe(()=>this.lantern.action('start'));}this.updateSystemStatus();}catch(error){console.warn('Workbench events:',error.message);}this.later(()=>this.scheduleCommands(),document.hidden?1800:500);
  }
  async click(event){
    const target=event.target.closest('button');if(!target)return;
    const d=target.dataset;
    return this.safe(async()=>{
      if(d.settingCategory)return this.settings(d.settingCategory);
      if(d.provider){await this.savePreference('ai.provider',d.provider);await this.savePreference('ai.model','');this.conversation=crypto.randomUUID?.()||String(Date.now());return this.renderSettingsContent();}
      if(d.externalTheme!=null)return this.applyExtensionTheme(Number(d.externalTheme));
      if(d.platformTheme){await this.savePreference('appearance.theme',d.platformTheme);return this.renderSettingsContent();}
      if(d.extensionMode)return this.extensions(d.extensionMode);
      if(d.extensionInspect)return this.reviewExtension({id:d.extensionInspect});
      if(d.extensionToggle){await this.api('/extensions/toggle',{id:d.extensionToggle,enabled:d.enabled==='true'});await this.loadContributions();return this.extensions();}
      if(d.extensionRemove){if(await this.host.confirmDialog(this.t('Desinstalar extensión','Uninstall extension'),d.extensionRemove,this.t('Desinstalar','Uninstall'))){await this.api('/extensions/remove',{id:d.extensionRemove,consent:true});await this.loadContributions();return this.extensions();}return;}
      if(d.taskRun)return this.runTask(d.taskRun);
      if(d.lspStart)return this.startLSP(d.lspStart);
      if(d.lspStop)return this.stopLSP(d.lspStop);
      if(d.insertSnippet!=null){const snippet=this.extensionContributions.snippets[Number(d.insertSnippet)];if(snippet)return this.reviewCode(snippet.body);return;}
      switch(d.platform){
        case 'close-page':return this.closePage();case 'extensions':return this.extensions();case 'extension-import':return this.importExtension();case 'extension-updates':return this.extensionUpdates();case 'extension-export':return this.exportExtensions();
        case 'tools':return this.tools();case 'tools-refresh':return this.tools(true);case 'terminal-profiles':return this.terminalProfiles();case 'hardware':return this.hardware();case 'focus':return this.setFocus();
        case 'settings-export':{const data=JSON.stringify(this.prefs,null,2),blob=new Blob([data],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='lumen-settings.json';a.click();this.later(()=>URL.revokeObjectURL(url),1000);return;}
        case 'settings-import':{const file=document.createElement('input');file.type='file';file.accept='.json';file.onchange=()=>this.safe(async()=>{const chosen=file.files[0];if(!chosen)return;if(chosen.size>150000)throw new Error('JSON demasiado grande.');const settings=JSON.parse(await chosen.text());const result=await this.api('/settings',{settings});this.prefs=result.settings;this.applyPreferences();await this.loadContributions();this.settings();});file.click();return;}
        case 'settings-reset':{if(await this.host.confirmDialog(this.t('Restaurar ajustes','Reset settings'),this.t('Se restaurarán las preferencias del IDE. Tus archivos, claves y extensiones no se borran.','IDE preferences will be reset. Your files, keys and extensions are kept.'),this.t('Restaurar','Reset'))){const result=await this.api('/settings',{reset:true});this.prefs=result.settings;this.applyPreferences();await this.loadContributions();this.settings();}return;}
        case 'audit':{const result=await this.api('/audit');this.host.modal(this.t('Registro local de permisos','Local permission audit'),`<pre class="lsp-response">${this.e(result.lines.join('\n')||this.t('Sin eventos.','No events.'))}</pre>`);return;}
        case 'revoke-trust':{await this.host.api('/trust',{trusted:false});this.host.setTrusted(false);this.workspaceChanged();this.host.notify(this.t('Confianza revocada. Terminales y servidores detenidos.','Trust revoked. Terminals and servers stopped.'));return;}
      }
    });
  }
  installEvents(){
    this.globalClick=event=>{if(!this.workbench.contains(event.target)&&event.target.closest('[data-platform],[data-setting-category]'))this.click(event);};document.addEventListener('click',this.globalClick);
    this.keyHandler=event=>{
      if(event.defaultPrevented)return;const ctrl=event.ctrlKey||event.metaKey,key=event.key.toLowerCase();
      if(ctrl&&event.altKey&&['t','e'].includes(key)){event.preventDefault();event.stopPropagation();this.safe(()=>key==='t'?this.terminalProfiles():this.extensions());}
      else if(ctrl&&key===' '&&document.getElementById('editor-mount').contains(event.target)){event.preventDefault();this.safe(()=>this.languageAction());}
      else if(event.key==='Escape'&&this.page&&document.getElementById('modal-backdrop').classList.contains('hidden')&&document.getElementById('palette-backdrop').classList.contains('hidden')){event.preventDefault();this.closePage();}
    };document.addEventListener('keydown',this.keyHandler);
  }
  workspaceChanged(){
    clearTimeout(this.saveTimer);clearTimeout(this.changeTimer);for(const t of this.terminals.values()){t.input.close();t.xterm?.dispose();t.mount.remove();}this.terminals.clear();this.activeTerminal=null;this.showingPTY=false;this.renderActiveTerminal();
    for(const s of this.lspSessions.values())s.disposables.forEach(d=>d.dispose());this.lspSessions.clear();this.diagnosticMap.clear();this.lastContent.clear();this.aiGeneration++;this.aiJob=null;this.conversation=crypto.randomUUID?.()||String(Date.now());this.closePage();this.updateSystemStatus();
  }
  dispose(){this.disposed=true;this.timers.forEach(clearTimeout);clearTimeout(this.saveTimer);clearTimeout(this.changeTimer);clearTimeout(this.syntaxTimer);this.terminalObserver?.disconnect();document.removeEventListener('click',this.globalClick);document.removeEventListener('keydown',this.keyHandler);for(const t of this.terminals.values()){t.input.close();t.xterm?.dispose();}for(const s of this.lspSessions.values())s.disposables.forEach(d=>d.dispose());this.contributionDisposables.forEach(d=>d.dispose());}
}
