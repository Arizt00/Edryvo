import {icon,escapeHTML as esc} from './icons.js';
import {parseCSV,numericSummary,cssColors,contrast,opaqueHex} from './workspace-data.js';
import {AssemblyWorkbench} from './assembly-workbench.js';
const styles={general:['code','Desarrollo general'],web:['globe','Desarrollo web'],data:['cpu','Ciencia de datos'],design:['palette','Diseño y UI'],assembly:['cpu','Ensamblador · ASM']};
const $=s=>document.querySelector(s);

/** Persistent profiles add working tools without overwriting custom dock positions. */
export class WorkspaceProfiles{
  constructor(host){
    this.host=host;this.disposed=false;this.previewEnabled=false;this.width='100%';this.delimiter=',';this.filter='';this.sequence=0;
    this.bar=document.createElement('section');this.bar.className='workspace-profile-bar';this.bar.setAttribute('aria-label','Estilo de trabajo');
    this.bar.innerHTML=`<label>${icon('layout')}<select id="workspace-style" aria-label="Estilo de trabajo">${Object.entries(styles).map(([key,[,name]])=>`<option value="${key}">${name}</option>`).join('')}</select></label><div class="workspace-profile-actions"></div><button class="icon-button profile-tool-toggle" aria-label="Mostrar herramientas del estilo" title="Mostrar u ocultar herramientas">${icon('sliders')}</button><button class="icon-button profile-detach" title="Desacoplar espacio de desarrollo" aria-label="Desacoplar espacio de desarrollo">${icon('arrow-up-right')}</button>`;
    $('#editor-mount').before(this.bar);
    this.tools=document.createElement('section');this.tools.className='workspace-profile-tools';this.tools.setAttribute('aria-label','Herramientas del estilo');$('#editor-mount').after(this.tools);
    this.bar.querySelector('select').onchange=e=>this.safe(async()=>{await host.studio.save({workspaceStyle:e.target.value});this.apply();});
    this.bar.querySelector('.profile-tool-toggle').onclick=()=>{this.tools.hidden=!this.tools.hidden;this.bar.querySelector('.profile-tool-toggle').setAttribute('aria-expanded',String(!this.tools.hidden));};
    this.bar.querySelector('.profile-detach').onclick=()=>this.safe(()=>host.desktop.detach(this.detachedPanel||'profile',host.editor.current||''));
    const changed=host.editor.callbacks.change;host.editor.callbacks.change=(...args)=>{changed?.(...args);this.changed();};
    const active=host.preview.activeChanged.bind(host.preview);host.preview.activeChanged=(...args)=>{active(...args);this.changed();};
    host.studio.workspaces=this;this.apply();
  }
  safe(fn){return this.host.platform.safe(fn);}
  apply(style){
    this.previewEnabled=false;
    this.style=style||this.host.studio.profile.workspaceStyle||'general';this.bar.querySelector('select').value=this.style;document.documentElement.dataset.workspaceStyle=this.style;this.tools.dataset.style=this.style;
    const action=(name,label,glyph)=>`<button class="text-button" data-profile-action="${name}">${icon(glyph)}<span>${label}</span></button>`;
    this.bar.querySelector('.workspace-profile-actions').innerHTML=({general:action('run','Ejecutar','play')+action('debug-view','Depurar','bug')+action('forge-window','Forge','build'),web:action('preview','Vista web','globe')+action('run','Ejecutar','play'),data:action('table','Explorar CSV','files')+action('run','Ejecutar Python','play'),design:action('palette','Colores y contraste','palette')+action('preview','Vista de componente','globe'),assembly:action('assembly','Laboratorio ASM','cpu')})[this.style];
    this.bar.querySelectorAll('[data-profile-action]').forEach(b=>b.onclick=()=>this.safe(async()=>{const op=b.dataset.profileAction;if(op==='preview'){this.previewEnabled=true;this.tools.hidden=false;await this.paintPreview();}else if(op==='table'||op==='palette'||op==='assembly'){this.previewEnabled=false;this.tools.hidden=false;this.paint();}else await this.host.perform(op,b);}));
    this.tools.hidden=this.detached||this.style==='general';this.bar.querySelector('.profile-tool-toggle').hidden=this.style==='general';this.paint();
  }
  setDetached(detached,panel){this.detached=detached;this.detachedPanel=detached?panel:null;this.tools.hidden=detached||this.style==='general';const button=this.bar.querySelector('.profile-detach');button.title=detached?'Volver a acoplar el espacio':'Desacoplar espacio de desarrollo';button.setAttribute('aria-label',button.title);button.innerHTML=icon(detached?'dock-left':'arrow-up-right');if(!detached)this.changed();}
  placement(panel='profile'){const child=this.host.desktop.query.has('panel');return `<button class="icon-button profile-surface-detach" data-surface-panel="${panel}" title="${child?'Volver a Zénit':'Desacoplar en ventana'}" aria-label="${child?'Volver a Zénit':'Desacoplar en ventana'}">${icon(child?'dock-left':'arrow-up-right')}</button>`;}
  bindPlacement(){this.tools.querySelectorAll('[data-surface-panel]').forEach(b=>b.onclick=()=>this.safe(()=>this.host.desktop.detach(b.dataset.surfacePanel,this.host.editor.current||'')));}
  changed(){clearTimeout(this.timer);this.timer=setTimeout(()=>this.paint(),350);}
  paint(){
    if(this.disposed||this.detached)return;const path=this.host.editor.current||'',text=this.host.editor.getValue?.()||'';
    this.tools.setAttribute('aria-label',styles[this.style][1]+' · '+(path||'sin archivo'));
    if(this.style==='general')return;
    if(this.style==='assembly'){this.assembly??=new AssemblyWorkbench(this);this.assembly.paint();return;}
    if(this.style==='web'){
      if(this.previewEnabled&&!this.tools.hidden&&/\.(html?|css)$/i.test(path))this.safe(()=>this.paintPreview());
      else this.tools.innerHTML='<div class="profile-empty">'+icon('globe')+'<div><strong>Tu página junto al código</strong><p>Abre HTML o CSS y pulsa Vista web. Verás el búfer sin guardarlo, con tamaños de móvil, tableta y escritorio.</p></div></div>';
    }
    if(this.style==='data'){
      if(!/\.(csv|tsv)$/i.test(path)){this.tools.innerHTML='<div class="profile-empty">'+icon('cpu')+'<div><strong>Explora tus datos</strong><p>Abre un CSV o TSV para filtrar filas y calcular estadísticas. Los scripts Python se ejecutan con la terminal integrada.</p></div></div>';return;}
      if(path.endsWith('.tsv'))this.delimiter='\t';
      try{this.table=parseCSV(text,this.delimiter);this.paintTable();}catch(e){this.tools.innerHTML='<p class="profile-error" role="status">'+esc(e.message)+'</p>';}
    }
    if(this.style==='design'){if(this.previewEnabled&&!this.tools.hidden&&/\.(html?|css)$/i.test(path))this.safe(()=>this.paintPreview());else this.paintDesign(text,path);}
  }
  paintTable(){
    const {header,rows}=this.table,visible=rows.filter(row=>!this.filter||row.join(' ').toLocaleLowerCase().includes(this.filter.toLocaleLowerCase()));
    this.tools.innerHTML=`<header class="profile-tool-heading"><strong>${rows.length} filas · ${header.length} columnas</strong><label>Separador <select aria-label="Separador CSV">${[[',','Coma'],[';','Punto y coma'],['\t','Tabulación']].map(([value,name])=>`<option value="${esc(value)}" ${this.delimiter===value?'selected':''}>${name}</option>`).join('')}</select></label><input class="profile-table-filter" placeholder="Filtrar filas…" aria-label="Filtrar filas" value="${esc(this.filter)}"><small>${visible.length} coincidencias · primeras 300</small>${this.placement()}</header><div class="profile-table-scroll"><table><thead><tr>${header.map(h=>'<th>'+esc(h)+'</th>').join('')}</tr></thead><tbody>${visible.slice(0,300).map(row=>'<tr>'+header.map((_,i)=>'<td>'+esc(row[i]??'')+'</td>').join('')+'</tr>').join('')}</tbody></table></div><footer class="profile-statistics">${header.map((name,i)=>{const s=numericSummary(visible,i);return s?`<span><strong>${esc(name)}</strong> n=${s.count} · media ${s.mean.toLocaleString('es',{maximumFractionDigits:3})} · mín ${s.min} · máx ${s.max}</span>`:'';}).join('')||'Sin columnas numéricas en esta selección.'}</footer>`;this.bindPlacement();
    this.tools.querySelector('select').onchange=e=>{this.delimiter=e.target.value;this.paint();};
    const input=this.tools.querySelector('input');input.oninput=()=>{this.filter=input.value;const selection=input.selectionStart;this.paintTable();const next=this.tools.querySelector('input');next.focus();next.setSelectionRange(selection,selection);};
  }
  paintDesign(text,path){
    const colors=cssColors(text),a=opaqueHex(this.foreground||colors[0]||'#202038'),b=opaqueHex(this.background||colors[1]||'#ffffff'),ratio=contrast(a,b);
    this.tools.innerHTML=`<header class="profile-tool-heading"><strong>Colores del búfer · ${colors.length}</strong><button class="secondary-button" id="profile-insert-colors" ${!colors.length||! /\.css$/i.test(path)?'disabled':''}>Insertar variables CSS</button></header><div class="profile-design-content"><div class="profile-color-list">${colors.map(c=>`<button class="profile-color-chip" data-color="${c}" title="Usar ${c} como color de texto"><i style="background:${c}"></i><code>${c}</code></button>`).join('')||'<p>Escribe colores hexadecimales en CSS o HTML para construir tu paleta.</p>'}</div><div class="profile-contrast"><label>Texto <input type="color" aria-label="Color de texto" value="${a.slice(0,7)}"></label><label>Fondo <input type="color" aria-label="Color de fondo" value="${b.slice(0,7)}"></label><span class="profile-color-example" style="color:${a};background:${b}">Zénit Aa</span><strong>Contraste ${ratio.toFixed(2)}:1</strong><small>${ratio>=4.5?'AA para texto normal':ratio>=3?'AA para texto grande':'Contraste bajo'}</small></div></div>`;
    this.tools.querySelectorAll('[data-color]').forEach(el=>el.onclick=()=>{this.foreground=el.dataset.color;this.paintDesign(text,path);});
    this.tools.querySelectorAll('input').forEach((el,i)=>el.oninput=()=>{this[i===0?'foreground':'background']=el.value;this.paintDesign(text,path);});
    $('#profile-insert-colors').onclick=()=>{const ed=this.host.editor,value=ed.getValue(),block=':root {\n'+colors.map((c,i)=>'  --color-'+(i+1)+': '+c+';').join('\n')+'\n}\n\n';ed.insertText(block+value,true);};
  }
  async paintPreview(){
    const path=this.host.editor.current;if(!path||! /\.(html?|css)$/i.test(path))throw Error('Abre HTML o CSS para previsualizarlo.');
    if(!await this.host.ensureTrust())return;const seq=++this.sequence;
    const shared=new Map([...this.host.desktop.remoteBuffers.values()].map(r=>[r.path,{path:r.path,content:r.text}]));
    for(const r of this.host.editor.models.values())shared.set(r.path,{path:r.path,content:r.model?.getValue()??r.value});
    const buffers=[...shared.values()];
    const result=await this.host.platform.api('/preview',{path,buffers});if(seq!==this.sequence||this.disposed)return;
    this.tools.innerHTML=`<header class="profile-tool-heading"><strong>${esc(result.path)}</strong><div>${[['100%','Escritorio'],['768px','Tableta'],['390px','Móvil']].map(([value,name])=>`<button class="text-button ${value===this.width?'active':''}" data-preview-width="${value}">${name}</button>`).join('')}${this.placement('preview')}<button class="icon-button" id="profile-preview-close" aria-label="Cerrar vista web">${icon('close')}</button></div></header><div class="profile-preview-scroll"><iframe title="Vista web aislada" sandbox="allow-scripts allow-same-origin allow-forms" referrerpolicy="no-referrer" src="${esc(result.url)}" style="width:${this.width}"></iframe></div>`;this.bindPlacement();
    this.tools.querySelectorAll('[data-preview-width]').forEach(el=>el.onclick=()=>{this.width=el.dataset.previewWidth;this.tools.querySelector('iframe').style.width=this.width;this.tools.querySelectorAll('[data-preview-width]').forEach(b=>b.classList.toggle('active',b===el));});
    $('#profile-preview-close').onclick=()=>{this.previewEnabled=false;this.tools.hidden=true;};
  }
  dispose(){this.disposed=true;clearTimeout(this.timer);this.sequence++;}
}
