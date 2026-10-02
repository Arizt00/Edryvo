/** Small DOM interactions, without a UI framework or continuous animation loop. */
export function installInteractions({motion,reorderFile,activateFile,closeFile}) {
  const tooltip=document.querySelector('#lumen-tooltip');
  let timer=null,anchor=null,draggedFile=null;
  const hideTip=()=>{clearTimeout(timer);tooltip.hidden=true;if(anchor?.getAttribute('aria-describedby')==='lumen-tooltip')anchor.removeAttribute('aria-describedby');anchor=null;};
  const revealTip=target=>{
    hideTip();if(!target||document.body.classList.contains('docking-drag'))return;
    const text=target.dataset.tooltip||target.getAttribute('title');if(!text)return;
    target.dataset.tooltip=text;target.removeAttribute('title');
    if(!target.getAttribute('aria-label')&&!target.textContent.trim())target.setAttribute('aria-label',text);
    anchor=target;
    timer=setTimeout(()=>{
      if(anchor!==target||!target.isConnected)return;
      tooltip.textContent=text;tooltip.hidden=false;target.setAttribute('aria-describedby','lumen-tooltip');
      const r=target.getBoundingClientRect(),box=tooltip.getBoundingClientRect();
      tooltip.style.left=Math.round(Math.max(8,Math.min(innerWidth-box.width-8,r.left+r.width/2-box.width/2)))+'px';
      tooltip.style.top=Math.round(r.bottom+box.height+12<innerHeight?r.bottom+8:Math.max(8,r.top-box.height-8))+'px';
      motion.enter(tooltip,2);
    },450);
  };
  document.addEventListener('pointerover',event=>{const target=event.target.closest('button[title],button[data-tooltip],.resize-handle[title]');if(target!==anchor)revealTip(target);});
  document.addEventListener('pointerout',event=>{if(anchor&&!anchor.contains(event.relatedTarget))hideTip();});
  document.addEventListener('focusin',event=>{if(event.target.matches('button'))revealTip(event.target);});
  document.addEventListener('focusout',hideTip);
  document.addEventListener('pointerdown',hideTip,true);
  document.addEventListener('keydown',event=>{if(event.key==='Escape')hideTip();});
  window.addEventListener('resize',hideTip);

  const files=document.querySelector('#file-tabs');
  files.addEventListener('dragstart',event=>{
    const tab=event.target.closest('[data-tab]');if(!tab)return;
    draggedFile=tab.dataset.tab;event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('application/x-lumen-file-tab',draggedFile);
    tab.classList.add('is-dragging');hideTip();
  });
  files.addEventListener('dragover',event=>{
    if(!draggedFile)return;event.preventDefault();event.dataTransfer.dropEffect='move';
    files.querySelectorAll('.drop-before,.drop-after').forEach(el=>el.classList.remove('drop-before','drop-after'));
    const tab=event.target.closest('[data-tab]');if(!tab||tab.dataset.tab===draggedFile)return;
    const r=tab.getBoundingClientRect();tab.classList.add(event.clientX>r.left+r.width/2?'drop-after':'drop-before');
    const bounds=files.getBoundingClientRect();if(event.clientX>bounds.right-35)files.scrollLeft+=20;else if(event.clientX<bounds.left+35)files.scrollLeft-=20;
  });
  const clearDrag=()=>{draggedFile=null;files.querySelectorAll('.is-dragging,.drop-before,.drop-after').forEach(el=>el.classList.remove('is-dragging','drop-before','drop-after'));};
  files.addEventListener('drop',event=>{if(!draggedFile)return;event.preventDefault();const tab=event.target.closest('[data-tab]');if(tab){const r=tab.getBoundingClientRect();reorderFile(draggedFile,tab.dataset.tab,event.clientX>r.left+r.width/2);}clearDrag();});
  files.addEventListener('dragend',clearDrag);
  files.addEventListener('auxclick',event=>{if(event.button===1){event.preventDefault();const tab=event.target.closest('[data-tab]');if(tab)closeFile(tab.dataset.tab);}});
  files.addEventListener('keydown',event=>{
    const current=event.target.closest('[data-tab]');if(!current)return;
    const tabs=[...files.querySelectorAll('[data-tab]')],index=tabs.indexOf(current);
    if(event.key==='Delete'){event.preventDefault();closeFile(current.dataset.tab);return;}
    if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
    event.preventDefault();
    const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;
    if(event.altKey&&event.shiftKey)reorderFile(current.dataset.tab,tabs[next].dataset.tab,event.key==='ArrowRight');
    else activateFile(tabs[next].dataset.tab);
    files.querySelector(`[data-tab="${CSS.escape(event.altKey&&event.shiftKey?current.dataset.tab:tabs[next].dataset.tab)}"]`)?.focus();
  });
  const termTabs=document.querySelector('.terminal-tabs');
  termTabs.addEventListener('keydown',event=>{
    if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
    const tabs=[...termTabs.querySelectorAll('[role="tab"]')],index=tabs.indexOf(event.target);if(index<0)return;
    event.preventDefault();const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;
    tabs[next].click();tabs[next].focus();
  });
  // Explicit ARIA names for icon-only controls, including newly rendered menus.
  const labelButtons=root=>root.querySelectorAll('button[title]').forEach(button=>{if(!button.getAttribute('aria-label')&&!button.textContent.trim())button.setAttribute('aria-label',button.title);});
  labelButtons(document);
  const observer=new MutationObserver(records=>{for(const record of records)for(const node of record.addedNodes)if(node.nodeType===1){labelButtons(node);if(node.matches('button[title]')&&!node.getAttribute('aria-label')&&!node.textContent.trim())node.setAttribute('aria-label',node.title);}});
  observer.observe(document.querySelector('#app'),{childList:true,subtree:true});
  return {dispose(){clearTimeout(timer);observer.disconnect();hideTip();}};
}
