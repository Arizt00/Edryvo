// Monaco renders context menus in a ShadowRoot. Its menu stylesheet cannot
// inherit document rules, but CSS custom properties still cross that boundary.
const css = `body>.monaco-menu-container{z-index:140!important}
.monaco-menu .monaco-action-bar.vertical{background:var(--surface)!important;border:1px solid var(--border)!important;border-radius:14px!important;padding:6px!important;color:var(--text)!important;box-shadow:0 14px 40px color-mix(in srgb,var(--text) 18%,transparent)!important;max-width:calc(100vw - 24px)}
.monaco-menu .monaco-action-bar.vertical .action-item{border-radius:6px!important;margin:1px 0}
.monaco-menu .monaco-action-bar.vertical .action-menu-item{color:var(--text)!important;min-height:26px;gap:14px;padding:2px 10px!important;line-height:22px!important}
.monaco-menu .monaco-action-bar.vertical .action-item.focused{background:var(--selected)!important}
.monaco-menu .monaco-action-bar.vertical .action-label{font-family:var(--font-ui);font-size:12px;max-width:44vw;overflow:hidden;text-overflow:ellipsis}
.monaco-menu .monaco-action-bar.vertical .keybinding{color:var(--muted)!important;font-size:11px!important;margin-left:22px!important}
.monaco-menu .monaco-action-bar.vertical .action-label.separator{border-bottom-color:var(--border)!important;margin:4px 0!important;padding:0!important;height:1px!important;min-height:0!important}
.monaco-menu .monaco-action-bar.vertical .action-menu-item:has(.separator){min-height:0!important;height:9px!important;padding:0 5px!important}
.monaco-menu .monaco-action-bar.vertical .action-item:has(.separator){margin:0!important}
.monaco-menu .monaco-action-bar.vertical{max-height:calc(100vh - 32px);overflow-y:auto;scrollbar-width:thin}
@media(prefers-reduced-motion:no-preference){:host-context(:root:not([data-motion=off])) .monaco-menu{animation:zenit-menu-in 120ms ease-out}}@keyframes zenit-menu-in{from{opacity:0;translate:0 3px}to{opacity:1;translate:0 0}}`;
export function installMonacoOverlays(){
  const apply=()=>{for(const host of document.querySelectorAll('.shadow-root-host')){const root=host.shadowRoot;if(root&&!root.querySelector('[data-lumen-menu-style]')){const style=document.createElement('style');style.dataset.lumenMenuStyle='';style.textContent=css;root.append(style);}}};
  const observer=new MutationObserver(apply);observer.observe(document.body,{childList:true,subtree:true});apply();
  return {dispose(){observer.disconnect();}};
}
