// Qt injects anonymous UMD libraries into the document when its native bridge
// loads. Finish that injection before Monaco installs the document's AMD loader.
export function waitForQtBridge(host=window,timeoutMs=15000){
  if(!host.navigator.userAgent.includes('QtWebEngine')||typeof host.pywebview?.api?.status==='function')return Promise.resolve();
  return new Promise((resolve,reject)=>{
    const cleanup=()=>{host.clearTimeout(timer);host.removeEventListener('pywebviewready',ready);};
    const ready=()=>{cleanup();if(typeof host.pywebview?.api?.status==='function')resolve();else reject(new Error('El puente nativo de Qt no expuso su API.'));};
    const timer=host.setTimeout(()=>{cleanup();reject(new Error('El puente nativo de Qt no está disponible.'));},timeoutMs);
    host.addEventListener('pywebviewready',ready,{once:true});
  });
}
