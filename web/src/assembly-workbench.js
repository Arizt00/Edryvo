import {icon,escapeHTML as esc} from './icons.js';

/** Results belong to a specific buffer and architecture. Editing invalidates them. */
export class AssemblyWorkbench{
  constructor(profiles){this.profiles=profiles;this.host=profiles.host;this.architecture='x86_64';this.steps=0;this.sequence=0;this.exampleIndex=0;this.decimal=false;}
  async load(){if(this.catalog)return;this.catalog=await this.host.platform.api('/simulation');this.paint();}
  paint(){
    const container=this.profiles.tools,text=this.host.editor.getValue?.()||'',path=this.host.editor.current||'';
    const fingerprint=path+'\0'+text+'\0'+this.architecture;
    if(this.fingerprint!==fingerprint){this.fingerprint=fingerprint;this.result=null;this.previousRegisters={};this.steps=0;this.sequence++;}
    this.host.editor.assemblyArchitecture=this.architecture;
    const architecture=this.catalog?.architectures.find(x=>x.id===this.architecture);
    const examples=architecture?.examples||[];
    container.innerHTML=`<header class="profile-tool-heading asm-heading"><div class="asm-title"><strong>${icon('cpu')} Laboratorio ASM</strong><small>LLVM · CPU emulada · búfer sin guardar</small></div><div class="asm-controls"><select aria-label="Arquitectura ASM">${(this.catalog?.architectures||[{id:'x86_64',label:'Detectando herramientas…'}]).map(a=>`<option value="${a.id}" ${a.id===this.architecture?'selected':''}>${esc(a.label)}</option>`).join('')}</select><button class="secondary-button" data-asm="step" ${!path||this.busy?'disabled':''}>${icon('arrow-right')} Paso</button><button class="primary-button" data-asm="run" ${!path||this.busy?'disabled':''}>${icon('play')} Simular</button><button class="icon-button" data-asm="reset" title="Reiniciar simulación">${icon('refresh')}</button>${this.profiles.placement('profile-assembly')}</div><div class="asm-example-row"><select aria-label="Ejemplo ASM">${examples.map((x,i)=>`<option value="${i}" ${i===this.exampleIndex?'selected':''}>${esc(x.label)}</option>`).join('')}</select><button class="secondary-button" data-asm="example" ${!path||!architecture?'disabled':''}>Cargar ejemplo</button><small>El archivo original se guarda cuando tú lo decides.</small></div></header><div class="asm-result" role="status">${this.resultMarkup()}</div>`;
    this.profiles.bindPlacement();
    container.querySelector('[aria-label="Arquitectura ASM"]').onchange=e=>{this.architecture=e.target.value;this.exampleIndex=0;this.paint();};
    container.querySelector('[aria-label="Ejemplo ASM"]').onchange=e=>{this.exampleIndex=Number(e.target.value);};
    container.querySelectorAll('[data-asm]').forEach(button=>button.onclick=()=>this.profiles.safe(async()=>{
      const action=button.dataset.asm;
      if(action==='reset'){this.result=null;this.previousRegisters={};this.steps=0;this.paint();return;}
      if(action==='format'){this.decimal=!this.decimal;this.paint();return;}
      if(action==='example'){if(text.trim()&&!await this.host.platform.host.confirmDialog('Cargar ejemplo ASM','Sustituir el búfer actual por el ejemplo de '+architecture.label+'. Puedes deshacerlo con Ctrl+Z.','Cargar ejemplo'))return;this.host.editor.insertText(examples[this.exampleIndex]?.source||architecture.example,true);this.paint();return;}
      if(!await this.host.ensureTrust())return;
      const seq=++this.sequence;this.busy=true;this.paint();
      try{const result=await this.host.platform.api('/simulation/run',{architecture:this.architecture,source:this.host.editor.getValue(),steps:action==='step'?Math.min(++this.steps,10000):10000});if(seq===this.sequence){this.previousRegisters=this.result?.registers||{};this.result=result;this.steps=result.executed||0;}}
      finally{this.busy=false;this.paint();}
    }));
    if(!this.catalog)this.profiles.safe(()=>this.load());
  }
  resultMarkup(){
    if(this.busy)return '<div class="lab-empty">Ensamblando y ejecutando…</div>';
    const r=this.result;if(!r)return '<div class="lab-empty"><strong>Observa cada instrucción</strong><p>Abre un archivo ASM, elige su arquitectura y simula. Paso ejecuta una instrucción adicional desde el estado inicial; los resultados se reinician cuando cambia el búfer.</p></div>';
    if(r.status==='error')return '<pre class="lab-error">'+esc(r.error)+'</pre>';
    return `<div class="asm-status"><span class="lab-badge">${esc({complete:'Finalizada',paused:'En pausa',fault:'Error de CPU'}[r.status]||r.status)}</span><span>${r.executed} instrucciones · PC <code>${esc(r.pc)}</code></span><button class="secondary-button" data-asm="format" aria-pressed="${this.decimal}">${this.decimal?'Decimal':'Hexadecimal'}</button></div>${r.error?'<pre class="lab-error">'+esc(r.error)+'</pre>':''}<div class="asm-grid"><section><h4>Registros <small>Se resaltan los cambios</small></h4><dl>${Object.entries(r.registers||{}).map(([key,value])=>`<div class="${key in this.previousRegisters&&this.previousRegisters[key]!==value?'changed':''}"><dt>${key}</dt><dd title="${esc(value)}">${esc(this.decimal?BigInt(value).toString():value)}</dd></div>`).join('')}</dl></section><section><h4>Instrucciones</h4><div class="asm-instructions">${(r.instructions||[]).map(i=>`<div class="${i.address===r.pc?'current':''}"><code>${esc(i.address)}</code><code>${esc(i.bytes)}</code><code>${esc(i.text)}</code></div>`).join('')}</div></section></div><details><summary>Memoria de pila · 64 bytes · 0x20ffc0</summary><pre>${esc(r.memory)}</pre></details><small class="lab-note">${esc(r.note)}</small>`;
  }
}
