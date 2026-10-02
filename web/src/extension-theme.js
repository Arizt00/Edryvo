// Only color values from an extension may enter the shell; never arbitrary CSS.
export function themePalette(theme) {
  const colors=Object.fromEntries(Object.entries(theme.data?.colors||{}).filter(([,v])=>typeof v==='string'&&/^#(?:[\da-f]{3,4}|[\da-f]{6}|[\da-f]{8})$/i.test(v)).map(([k,v])=>[k,v.length<6?'#'+[...v.slice(1)].map(c=>c+c).join(''):v]));
  const dark=theme.uiTheme!=='vs'&&theme.uiTheme!=='hc-light';
  const pick=(keys,fallback)=>keys.split('|').map(k=>colors[k]).find(Boolean)||fallback;
  const bg=pick('editor.background',dark?'#1e1e1e':'#ffffff'),text=pick('editor.foreground|foreground',dark?'#d4d4d4':'#242424');
  const surface=pick('sideBar.background|editorWidget.background',bg),accent=pick('focusBorder|button.background|activityBarBadge.background',dark?'#8eabff':'#405dde');
  const border=pick('panel.border|widget.border|sideBar.border',dark?'#444444':'#d4d4d4');
  const palette={bg:pick('workbench.background|editorGroup.emptyBackground',bg),surface,editor:bg,header:pick('titleBar.activeBackground',surface),rail:pick('activityBar.background',surface),card:surface,field:pick('input.background',surface),text,secondary:pick('sideBar.foreground|foreground',text),muted:pick('descriptionForeground|editorLineNumber.foreground',text),accent,'accent-bright':accent,'accent-soft':pick('list.inactiveSelectionBackground',surface),selected:pick('list.activeSelectionBackground|tab.activeBackground',surface),hover:pick('list.hoverBackground',surface),line:pick('editor.lineHighlightBackground',bg),border,'border-strong':pick('focusBorder',border),selection:pick('editor.selectionBackground',accent.slice(0,7)+'33'),'terminal-bg':pick('terminal.background',bg),'terminal-text':pick('terminal.foreground',text),folder:pick('symbolIcon.folderForeground',accent),'logo-light':accent,'logo-dark':accent,success:pick('terminal.ansiGreen','#70aa78'),danger:pick('errorForeground|editorError.foreground','#de5967'),warning:pick('editorWarning.foreground','#c9a05a'),glass:surface.slice(0,7)+'af','glass-edge':border,'inset':'inset 0 1px 0 '+border.slice(0,7)+'55'};
  for(const [token,scopes] of Object.entries({keyword:['keyword','storage'],type:['entity.name.type','support.type'],string:['string'],number:['constant.numeric'],comment:['comment'],function:['entity.name.function','support.function']})){
    const entry=[...(theme.data?.tokenColors||[])].reverse().find(e=>(Array.isArray(e.scope)?e.scope:String(e.scope||'').split(',')).some(s=>scopes.some(x=>s.trim()===x))&&/^#[\da-f]{6}$/i.test(e.settings?.foreground||''));
    palette['syntax-'+token]=entry?.settings.foreground||text;
  }
  return {palette,colors,dark};
}
export function applyShellTheme(theme,root=document.documentElement){
  for(const key of (root.dataset.extensionTokens||'').split(' ').filter(Boolean))root.style.removeProperty('--'+key);
  delete root.dataset.extensionTheme;delete root.dataset.extensionTokens;
  if(!theme)return;
  const {palette,dark}=themePalette(theme);
  for(const [key,value] of Object.entries(palette))root.style.setProperty('--'+key,value);
  root.dataset.extensionTokens=Object.keys(palette).join(' ');root.dataset.extensionTheme=theme.id;root.dataset.theme=dark?'dark':'day';
}
