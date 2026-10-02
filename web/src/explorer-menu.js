import {escapeHTML as esc} from './icons.js';
export function installExplorerMenu(host){
  let clipboard=null,lastTrash=null;
  const sidebar=document.querySelector('#sidebar-content');let focused=null;
  sidebar.addEventListener('focusin',e=>{const item=e.target.closest('[data-file],[data-dir]');if(item)focused=item;});
  sidebar.addEventListener('keydown',e=>{
    const item=e.target.closest('[data-file],[data-dir]')||focused;if(!item||e.target.matches('input,textarea'))return;
    const path=item.dataset.file||item.dataset.dir||'',parent=item.hasAttribute('data-dir')?path:path.split('/').slice(0,-1).join('/');
    const control=e.ctrlKey||e.metaKey;let action;
    if(e.key==='F2'&&path)action=()=>nameDialog('Cambiar nombre',path,'rename',path);
    if(e.key==='Delete'&&path)action=async()=>{if(await host.confirmDialog('Eliminar del proyecto',`¿Mover ${path} a la papelera de Lumen?`,'Eliminar'))await operation('delete',path);};
    if(control&&['c','x'].includes(e.key.toLowerCase())&&path)action=()=>{clipboard={path,cut:e.key.toLowerCase()==='x'};};
    if(control&&e.key.toLowerCase()==='v'&&clipboard)action=async()=>{await operation(clipboard.cut?'move':'copy',clipboard.path,(parent?parent+'/':'')+clipboard.path.split('/').pop());if(clipboard.cut)clipboard=null;};
    if(action){e.preventDefault();e.stopPropagation();safe(action);}
  });
  const safe=fn=>Promise.resolve().then(fn).catch(e=>host.notify(e.message,'error',6000));
  const affected=path=>[...host.editor.models.keys()].filter(x=>x===path||x.startsWith(path+'/'));
  const clean=async path=>{for(const p of affected(path))if(host.editor.isDirty(p)){if(!await host.confirmDialog('Cambios sin guardar',`Guarda los cambios de ${p} antes de continuar.`,'Guardar y continuar'))return false;await host.saveFile(p);}return true;};
  async function operation(action,path,destination){
    if(['rename','move','delete'].includes(action)&&!await clean(path))return;
    const opened=affected(path),result=await host.api('/platform/files/operation',{operation:action,path,destination});
    if(action==='delete')lastTrash=result.ticket;
    if(['rename','move','delete'].includes(action)){for(const p of opened)host.editor.close(p);host.refreshDocuments();}
    await host.refreshTree();
    if(action==='rename'||action==='move'){for(const p of opened)await host.openFile(result.path+p.slice(path.length));}
    if(action==='delete')host.notify('Movido a la papelera del proyecto. Usa «Deshacer eliminación» en el menú.');
  }
  function nameDialog(title,path,action,initial){host.modal(title,`<form id="file-operation"><label>Ruta dentro del proyecto<input id="file-operation-path" required value="${esc(initial)}"></label><div class="modal-actions"><button class="primary-button">${esc(title)}</button></div></form>`);document.querySelector('#file-operation').onsubmit=e=>{e.preventDefault();safe(async()=>{const value=document.querySelector('#file-operation-path').value.trim();if(action==='new'){await host.api('/save',{path:value,content:'',create:true});await host.refreshTree();await host.openFile(value);}else if(action==='mkdir')await operation('mkdir',value);else await operation(action,path,value);host.closeModal();});};}
  document.querySelector('#sidebar-content').addEventListener('contextmenu',e=>{
    const element=e.target.closest('[data-file],[data-dir]'),path=element?.dataset.file||element?.dataset.dir||'',directory=!!element?.hasAttribute('data-dir')||!path,parent=directory?path:path.split('/').slice(0,-1).join('/'),prefix=parent?parent+'/':'';
    if(element){focused=element;element.focus();}e.preventDefault();e.stopPropagation();const items=[
      {label:'Nuevo archivo…',icon:'file',run:()=>nameDialog('Nuevo archivo',path,'new',prefix)},
      {label:'Nueva carpeta…',icon:'folder',run:()=>nameDialog('Nueva carpeta',path,'mkdir',prefix)},
      {separator:true},
      ...(!directory?[{label:'Abrir',icon:'file',run:()=>host.openFile(path)},{label:'Abrir en otra ventana',icon:'plus',run:()=>host.newWindow(path)},{label:'Abrir y ejecutar con Lantern',icon:'play',run:async()=>{await host.openFile(path);await host.lantern.action('start');}}]:[]),
      {label:'Buscar en esta carpeta',icon:'search',run:()=>host.search(parent)},
      {label:'Copiar ruta',icon:'copy',run:()=>navigator.clipboard.writeText(host.workspace().replaceAll('\\','/')+(path?'/'+path:''))},
      {label:'Copiar ruta relativa',icon:'copy',run:()=>navigator.clipboard.writeText(path||'.')},
      {separator:true},
      ...(path?[{label:'Cortar',icon:'code',shortcut:'Ctrl X',run:()=>{clipboard={path,cut:true};}},{label:'Copiar',icon:'copy',shortcut:'Ctrl C',run:()=>{clipboard={path,cut:false};}}]:[]),
      ...(clipboard?[{label:'Pegar',icon:'file',shortcut:'Ctrl V',run:async()=>{await operation(clipboard.cut?'move':'copy',clipboard.path,prefix+clipboard.path.split('/').pop());if(clipboard.cut)clipboard=null;}}]:[]),
      ...(path?[{label:'Duplicar…',icon:'copy',run:()=>nameDialog('Duplicar',path,'copy',path+'.copy')},{label:'Cambiar nombre…',icon:'code',shortcut:'F2',run:()=>nameDialog('Cambiar nombre',path,'rename',path)},{label:'Eliminar',icon:'trash',shortcut:'Supr',run:async()=>{if(await host.confirmDialog('Eliminar del proyecto',`¿Mover ${path} a la papelera de Lumen? Podrás recuperarlo desde este menú.`,'Eliminar'))await operation('delete',path);}}]:[]),
      ...(lastTrash?[{label:'Deshacer eliminación',icon:'refresh',run:async()=>{await host.api('/platform/files/operation',{operation:'restore',ticket:lastTrash});lastTrash=null;await host.refreshTree();}}]:[]),
      {separator:true},{label:'Actualizar explorador',icon:'refresh',run:host.refreshTree}
    ];host.showMenu({getBoundingClientRect:()=>({left:e.clientX,right:e.clientX,bottom:e.clientY})},items,path.split('/').pop()||'Proyecto');
  });
}
