"""Restricted-renderer harness: inline owned UI, real loopback API via Python.

This is NOT an end-to-end browser transport, CSP or dependency-loading test.
It does not change browser policies. Use direct navigation for those checks.
"""
from pathlib import Path
import re,json,urllib.request,http.cookiejar,base64
ROOT=Path(__file__).resolve().parents[1]

def prepare(page, base="http://127.0.0.1:8765", storage=None):
    jar=http.cookiejar.CookieJar()
    client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar),urllib.request.ProxyHandler({}))
    client.open(base + '/').read()
    def bridge(url,options):
        headers=options.get('headers',{})
        headers['Origin']=base
        req=urllib.request.Request(base+url,data=options.get('body','').encode() if options.get('body') else None,headers=headers,method=options.get('method','GET'))
        try:
            response=client.open(req,timeout=130)
            return {'status':response.status,'data':json.loads(response.read())}
        except urllib.error.HTTPError as e:
            return {'status':e.code,'data':json.loads(e.read())}
    page.expose_function('__lumenFetch',bridge)
    html=(ROOT/'web/index.html').read_text()
    html=re.sub(r'<script\b[^>]*>[\s\S]*?</script>','',html)
    html=re.sub(r'<link\b[^>]*>','',html)
    assets={f'/assets/landscape-{theme}.png':'data:image/png;base64,'+base64.b64encode((ROOT/f'web/assets/landscape-{theme}.png').read_bytes()).decode() for theme in ('day','dark','forest')}
    for path,data in assets.items(): html=html.replace('src="'+path+'"','src="'+data+'"')
    html=html.replace('</head>','<style>'+'\n'.join((ROOT/'web'/name).read_text() for name in ['style.css','refinement.css','atelier.css','platform.css'])+'</style></head>')
    page.set_content(html)
    bootstrap='''window.fetch = async (url,options={}) => {
      const r=await window.__lumenFetch(url, options);
      return {ok:r.status>=200&&r.status<300,status:r.status,json:async()=>r.data};
    };'''
    bootstrap+='window.LUMEN_ASSETS='+json.dumps(assets)+';\n'
    # Storage in this about:blank QA context is injected, not a persistence test.
    bootstrap+='Object.defineProperty(window,"localStorage",{value:{_s:{},getItem(k){return this._s[k]??null},setItem(k,v){this._s[k]=String(v)}}});\n'
    bootstrap+='Object.assign(localStorage._s,'+json.dumps(storage or {})+');\n'
    bootstrap+='\n'+(ROOT/'web/src/theme-init.js').read_text()+'\n'
    modules=[]
    for f in ['icons.js','layout-state.js','motion.js','docking.js','interactions.js','editor.js','babylon-scene.js','workbench.js','app.js']:
        s=(ROOT/'web/src'/f).read_text()
        s=re.sub(r'^import .*?;\s*$', '', s, flags=re.M)
        s=re.sub(r'^export ', '', s, flags=re.M)
        modules.append(s)
    script=bootstrap+'\n'+modules[0]+'\nconst esc=escapeHTML;\n'+'\n'.join(modules[1:])
    page.add_script_tag(content=script)
