import {icon} from './icons.js';

export const DOCUMENT_TYPE='application/x-lumen-document';
export function outsideViewport(x,y,width,height){return Number.isFinite(x)&&Number.isFinite(y)&&(x<0||y<0||x>width||y>height);}
export function dropSide(x,y,rect){
  const rx=(x-rect.left)/rect.width,ry=(y-rect.top)/rect.height;
  if(ry<.2)return 'top';if(ry>.8)return 'bottom';
  if(rx<.24)return 'left';if(rx>.76)return 'right';return 'center';
}

/** A drag never closes a document or saves its unsaved buffer. */
export class DocumentDrag{
  constructor(host){
    this.host=host;this.listeners=[];
    this.overlay=document.createElement('div');this.overlay.className='document-drop-overlay';this.overlay.hidden=true;
    this.overlay.innerHTML='<div class="document-drop-hint">Soltar en un borde divide el editor · fuera de Zénit abre otra ventana</div>'+['top','left','center','right','bottom'].map(side=>`<div data-document-side="${side}">${icon(side==='center'?'file':'split')}<span>${{top:'Dividir arriba',left:'Dividir a la izquierda',center:'Abrir aquí',right:'Dividir a la derecha',bottom:'Dividir abajo'}[side]}</span></div>`).join('');
    host.panel.append(this.overlay);
    this.listen(document,'dragstart',e=>{
      const tab=e.target.closest('[data-tab]'),file=e.target.closest('.tree-row[data-file]');const path=tab?.dataset.tab||file?.dataset.file;
      if(!path)return;this.start={path,handled:false};
      const r=host.editor.models.get(path);e.dataTransfer.setData(DOCUMENT_TYPE,JSON.stringify({path,workspace:host.service().workspace,content:r?.model?.getValue()??r?.value}));e.dataTransfer.effectAllowed='copyMove';
      host.onStart?.(path);
    });
    this.listen(host.panel,'dragover',e=>{
      if(!e.dataTransfer.types.includes(DOCUMENT_TYPE))return;e.preventDefault();e.dataTransfer.dropEffect='copy';this.overlay.hidden=false;
      const side=dropSide(e.clientX,e.clientY,host.editor.mount.getBoundingClientRect());this.side=side;
      this.overlay.querySelectorAll('[data-document-side]').forEach(el=>el.classList.toggle('active',el.dataset.documentSide===side));
    });
    this.listen(host.panel,'dragleave',e=>{if(!host.panel.contains(e.relatedTarget))this.overlay.hidden=true;});
    this.listen(host.panel,'drop',e=>{
      if(!e.dataTransfer.types.includes(DOCUMENT_TYPE))return;e.preventDefault();e.stopPropagation();if(this.start)this.start.handled=true;
      const side=dropSide(e.clientX,e.clientY,host.editor.mount.getBoundingClientRect());this.overlay.hidden=true;
      const data=JSON.parse(e.dataTransfer.getData(DOCUMENT_TYPE)),internal=!!this.start;
      host.safe(()=>this.receive(data,side,internal));
    });
    this.listen(document,'drop',()=>{if(this.start)this.start.handled=true;},true);
    this.listen(document,'keydown',e=>{if(e.key==='Escape'&&this.start){this.start.cancelled=true;this.overlay.hidden=true;}},true);
    this.listen(document,'dragend',e=>{
      const start=this.start;this.start=null;this.overlay.hidden=true;host.onEnd?.();
      if(start&&!start.handled&&!start.cancelled&&e.dataTransfer.dropEffect==='none'&&outsideViewport(e.clientX,e.clientY,innerWidth,innerHeight))host.safe(()=>host.detach(start.path,{x:e.screenX-40,y:e.screenY-24}));
    });
  }
  listen(node,name,fn,capture=false){node.addEventListener(name,fn,capture);this.listeners.push(()=>node.removeEventListener(name,fn,capture));}
  async receive(data,side='center',internal=false){
    const h=this.host;if(!data?.path||data.workspace!==h.service().workspace)throw Error('Arrastra archivos de este mismo proyecto.');
    const previous=h.editor.current,existing=h.editor.models.get(data.path);
    // Within one window the live model wins over the drag snapshot.
    if(!internal&&existing&&typeof data.content==='string'&&h.editor.isDirty(data.path)&&!await h.confirmDialog('Recibir archivo','El búfer de destino tiene cambios. ¿Reemplazarlo por el de la otra ventana?','Reemplazar búfer'))return;
    await h.openFile(data.path);
    if(!internal&&typeof data.content==='string'&&data.content.length<=2_000_000)h.editor.insertText(data.content,true);
    if(side!=='center'){
      if(previous&&previous!==data.path)h.editor.activate(previous);
      h.editor.split(data.path,side);
    }
  }
  dispose(){this.listeners.forEach(fn=>fn());this.overlay.remove();}
}
