// FileDecorationProvider badges follow the explorer without changing file contents.
export function explorerDecorations(host,extensions){
  if(!extensions.length)return {dispose(){}};
  const tree=document.getElementById('sidebar-content'),states=new Map();let disposed=false,timer,busy=false;
  const rows=()=>[...tree.querySelectorAll('[data-file],[data-dir]')].filter(row=>row.getClientRects().length).slice(0,300);
  const file=row=>row.dataset.file||row.dataset.dir;
  function paint(){
    for(const row of rows()){
      const values=[...states.values()].map(state=>state.items.get(file(row))).filter(Boolean);
      const badges=values.filter(d=>d.badge).map(d=>[...String(d.badge)].slice(0,2).join('')).join(' '),tooltip=values.map(d=>d.tooltip).filter(Boolean).join(' · ');
      let badge=row.querySelector('.extension-file-decoration');
      if(!badges){badge?.remove();row.title=file(row)+(tooltip?' · '+tooltip:'');if(!values.some(d=>d.color))row.style.removeProperty('color');}
      const theme=host.platform.extensionThemes?.find(t=>t.id===document.documentElement.dataset.extensionTheme),colorId=values.findLast(d=>d.color)?.color,colorValue=theme?.data?.colors?.[colorId];
      const fallback={'gitDecoration.modifiedResourceForeground':'#a67619','gitDecoration.deletedResourceForeground':'#d04a58','gitDecoration.untrackedResourceForeground':'#31885d','gitDecoration.addedResourceForeground':'#31885d','gitDecoration.ignoredResourceForeground':'#8290a3','gitDecoration.conflictingResourceForeground':'#d04a58'};
      const resolved=/^#[\da-f]{3,8}$/i.test(colorValue||'')?colorValue:fallback[colorId];
      if(resolved)row.style.color=resolved;else row.style.removeProperty('color');
      if(!badges)continue;
      if(!badge){badge=document.createElement('span');badge.className='extension-file-decoration';row.append(badge);}
      if(badge.textContent!==badges)badge.textContent=badges;
      const color=values.findLast(d=>d.color)?.color||'';
      badge.dataset.tone=/error|deleted|conflict/i.test(color)?'error':/warning|modified/i.test(color)?'warning':/added|untracked|success/i.test(color)?'success':'accent';
      badge.style.color=resolved||'';
      badge.title=tooltip;row.title=file(row)+(tooltip?' · '+tooltip:'');
    }
  }
  async function refresh(){
    if(disposed||host.platform.disposed)return;
    if(busy)return schedule();busy=true;
    const paths=rows().map(file);
    try{
      for(const ext of extensions){
        const state=states.get(ext.id)||{items:new Map()};states.set(ext.id,state);
        const result=await host.platform.api('/extensions/runtime/request',{id:ext.id,method:'decorations',paths,revision:state.revision});
        if(disposed)return;
        if(!result.unchanged){state.revision=result.revision;state.items=new Map((result.items||[]).map(item=>[item.path,item.decoration]));}
      }
      paint();
    }catch(error){if(!disposed)console.warn('Decoraciones de extensiones:',error.message);}
    finally{busy=false;schedule();}
  }
  function schedule(delay=1500){clearTimeout(timer);if(!disposed)timer=setTimeout(refresh,delay);}
  const observer=new MutationObserver(records=>{
    if(records.every(r=>r.target.closest?.('.extension-file-decoration')||[...r.addedNodes,...r.removedNodes].every(n=>n.nodeType===1&&n.classList.contains('extension-file-decoration'))))return;
    paint();schedule(150);
  });
  observer.observe(tree,{childList:true,subtree:true});if(extensions.length)schedule(0);
  return {dispose(){disposed=true;clearTimeout(timer);observer.disconnect();tree.querySelectorAll('.extension-file-decoration').forEach(b=>{b.parentElement.title=file(b.parentElement);b.remove();});}};
}
