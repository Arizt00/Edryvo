"""Official account clients. Tokens stay in the vendor client, never in Lumen JSON.

Codex uses its documented app-server protocol in a private CODEX_HOME. Claude
Code and Gemini CLI use their documented headless modes and isolated config.
No browser cookies, consumer-site scraping, or subscription-to-API conversion.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlparse
from .terminals import child_environment, TerminalSession

CLIENTS = {
    'codex': ('codex', 'ChatGPT · Codex', 'https://developers.openai.com/codex/cli'),
    'claude-code': ('claude', 'Claude · cuenta', 'https://code.claude.com/docs/en/setup'),
    'gemini-cli': ('gemini', 'Gemini · cuenta Google', 'https://geminicli.com/docs/get-started/installation/'),
    'copilot': ('copilot', 'GitHub Copilot', 'https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli'),
}
FLAGS = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0

def executable(provider):
    name = CLIENTS[provider][0]
    found = shutil.which(name)
    if found: return found
    # The desktop distribution exposes its official CLI here on Windows.
    if provider == 'codex' and os.name == 'nt':
        root = Path(os.environ.get('LOCALAPPDATA', '')) / 'OpenAI/Codex/bin'
        candidates = list(root.glob('*/codex.exe'))
        if candidates: return str(max(candidates, key=lambda p:p.stat().st_mtime))
    return None

def client_argv(provider):
    exe = executable(provider)
    if not exe: raise ValueError('Instala el cliente oficial desde el enlace de esta pantalla y vuelve a comprobar la conexión.')
    # Invoke npm's JS entrypoint directly: no shell interpolation and no CMD window.
    if Path(exe).suffix.lower() in ('.cmd', '.bat'):
        packages = {'codex':'@openai/codex/bin/codex.js','claude-code':'@anthropic-ai/claude-code/cli.js',
                    'gemini-cli':'@google/gemini-cli/dist/index.js','copilot':'@github/copilot/index.js'}
        script = Path(exe).parent / 'node_modules' / packages[provider]
        node = shutil.which('node')
        if node and script.is_file(): return [node, str(script)]
        raise ValueError('No se encuentra la entrada del cliente oficial. Reinstala su distribución oficial de Node.js.')
    return [exe]

class CodexAccount:
    def __init__(self, directory):
        self.home = Path(directory) / 'accounts/codex'; self.home.mkdir(parents=True, exist_ok=True)
        self.cwd = self.home / 'workspace'; self.cwd.mkdir(exist_ok=True)
        self.lock = threading.RLock(); self.write_lock = threading.Lock(); self.pending = {}; self.listeners = {}
        self.sequence = 0; self.process = None; self.login_id = None

    def start(self):
        with self.lock:
            if self.process and self.process.poll() is None: return
            env = child_environment(); env['CODEX_HOME'] = str(self.home)
            args = client_argv('codex') + ['app-server']
            for feature in ('shell_tool','unified_exec','apps','browser_use','computer_use','plugins','multi_agent','view_image','hooks'):
                args += ['-c', f'features.{feature}=false']
            args += ['-c','web_search="disabled"','-c','approval_policy="never"','-c','sandbox_mode="read-only"']
            self.process = subprocess.Popen(args, cwd=self.cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace', bufsize=1, creationflags=FLAGS)
            threading.Thread(target=self._read, args=(self.process,), daemon=True).start()
            self.rpc('initialize', {'clientInfo':{'name':'lumen_studio','title':'Lumen Studio','version':'0.5.2'}})
            self.send({'method':'initialized','params':{}})

    def send(self, message):
        with self.write_lock:
            if not self.process or self.process.poll() is not None: raise ValueError('El cliente Codex se ha cerrado. Vuelve a conectar.')
            self.process.stdin.write(json.dumps(message, ensure_ascii=True)+'\n'); self.process.stdin.flush()

    def rpc(self, method, params, timeout=20):
        # Responses are delivered by the reader without acquiring the startup lock.
        with self.write_lock:
            self.sequence += 1; ident = self.sequence; result = queue.Queue(maxsize=1); self.pending[ident] = result
        try:
            self.send({'id':ident,'method':method,'params':params})
            try: response = result.get(timeout=timeout)
            except queue.Empty: raise ValueError('Codex no ha respondido a tiempo. Puedes volver a intentarlo.') from None
            if 'error' in response: raise ValueError(str(response['error'].get('message','Error del cliente Codex'))[:500])
            return response.get('result', {})
        finally: self.pending.pop(ident, None)

    def _read(self, process):
        try:
            for line in process.stdout:
                if len(line)>2_000_000: continue
                try: msg = json.loads(line)
                except ValueError: continue
                if 'id' in msg and 'method' not in msg:
                    target = self.pending.get(msg['id'])
                    if target and target.empty(): target.put_nowait(msg)
                elif 'id' in msg:
                    # No tool approvals or elicitation are delegated to the model.
                    self.send({'id':msg['id'],'error':{'code':-32601,'message':'Lumen only accepts text and reviewable proposals.'}})
                else:
                    params = msg.get('params', {}); target = self.listeners.get(params.get('threadId'))
                    if target: target.put(msg)
        finally:
            process.stdout.close()
            for target in list(self.pending.values()):
                if target.empty(): target.put({'error':{'message':'El cliente Codex se ha cerrado.'}})

    def status(self):
        self.start(); data = self.rpc('account/read', {'refreshToken':False}); account = data.get('account') or {}
        if account.get('type')=='chatgpt': self.login_id=None
        return {'installed':True,'authenticated':account.get('type')=='chatgpt','account':account.get('email',''),
                'plan':account.get('planType',''),'loginPending':bool(self.login_id)}

    def login(self):
        self.start()
        if self.login_id:
            self.rpc('account/login/cancel', {'loginId':self.login_id})
        result = self.rpc('account/login/start', {'type':'chatgpt'})
        url = result.get('authUrl',''); parsed=urlparse(url)
        if parsed.scheme!='https' or parsed.hostname not in ('auth.openai.com','auth0.openai.com','chatgpt.com'):
            raise ValueError('El cliente no devolvió una URL oficial de inicio de sesión compatible.')
        self.login_id = result.get('loginId'); return {'url':url,'mode':'browser'}

    def logout(self):
        self.start(); self.rpc('account/logout', {}); self.login_id=None; return self.status()

    def models(self):
        if not self.status()['authenticated']: raise ValueError('Inicia sesión con ChatGPT para consultar los modelos de tu cuenta.')
        data=self.rpc('model/list',{'limit':50,'includeHidden':False})
        return {'models':[x.get('model') or x['id'] for x in data.get('data',[])],'verified':True,
                'note':'Catálogo del cliente oficial. La disponibilidad y los límites dependen de tu cuenta.'}

    def stream(self, job, messages, system, timeout):
        if not self.status()['authenticated']: raise ValueError('Inicia sesión con ChatGPT desde Ajustes → Inteligencia artificial.')
        started=self.rpc('thread/start', {'model':job.model,'cwd':str(self.cwd),'approvalPolicy':'never',
            'sandbox':'read-only','developerInstructions':system,'ephemeral':True})
        tid=started['thread']['id']; events=queue.Queue(); self.listeners[tid]=events; turn_id=None
        try:
            prompt=system+'\n\n'+'\n\n'.join(m['role'].upper()+':\n'+m['content'] for m in messages)
            turn=self.rpc('turn/start',{'threadId':tid,'input':[{'type':'text','text':prompt}]})
            turn_id=turn['turn']['id']; deadline=time.monotonic()+timeout
            while not job.cancelled.is_set():
                if time.monotonic()>deadline: raise ValueError('Tiempo de respuesta agotado. Puedes volver a intentarlo.')
                try: event=events.get(timeout=.15)
                except queue.Empty: continue
                params=event.get('params',{}); method=event.get('method')
                if method=='item/agentMessage/delta': job.append(params.get('delta',''))
                elif method=='turn/completed':
                    finished=params.get('turn',{})
                    if finished.get('status')=='failed': raise ValueError(str((finished.get('error') or {}).get('message','Codex no pudo completar la respuesta.')))
                    turn_id=None; return
                elif method=='error' and not params.get('willRetry'): raise ValueError(str((params.get('error') or {}).get('message','Error del cliente Codex.')))
        finally:
            if turn_id:
                try:self.rpc('turn/interrupt',{'threadId':tid,'turnId':turn_id},timeout=5)
                except ValueError:pass
            self.listeners.pop(tid,None)

    def shutdown(self):
        process=self.process
        if process and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=3)
            except subprocess.TimeoutExpired:process.kill()
        if process and process.stdin:process.stdin.close()

class Accounts:
    def __init__(self, prefs): self.prefs=prefs; self.codex=CodexAccount(prefs.directory)

    def environment(self, provider):
        env=child_environment(); home=self.prefs.directory/'accounts'/provider; home.mkdir(parents=True,exist_ok=True)
        if provider=='claude-code': env['CLAUDE_CONFIG_DIR']=str(home)
        if provider=='copilot': env['COPILOT_HOME']=str(home)
        if provider=='gemini-cli':
            env['GEMINI_CLI_HOME']=str(home)
            # Isolated, data-only assistant: no tools, MCP, extensions or hooks.
            config=home/'.gemini';config.mkdir(exist_ok=True)
            settings={'tools':{'core':[]},'mcpServers':{},'mcp':{'allowed':[]},'hooksConfig':{'enabled':False},
                      'general':{'enableAutoUpdate':False},'extensions':{'enabled':False}}
            policy=home/'lumen-review.toml'
            policy.write_text('[[rule]]\ntoolName = "*"\ndecision = "deny"\npriority = 999\n',encoding='utf-8')
            settings['policyPaths']=[str(policy)]
            guard=home/'review-settings.json';guard.write_text(json.dumps(settings),encoding='utf-8')
            env['GEMINI_CLI_SYSTEM_SETTINGS_PATH']=str(guard)
        for name in ('ANTHROPIC_AUTH_TOKEN','CLAUDE_CODE_OAUTH_TOKEN','GOOGLE_GENAI_USE_VERTEXAI','GOOGLE_GENAI_USE_GCA'):
            env.pop(name,None)
        return env,home

    def copilot_client(self, working_directory=None):
        from copilot import CopilotClient, RuntimeConnection
        env,home=self.environment('copilot')
        args=client_argv('copilot')
        # Use the same explicitly installed client as the account login. Never
        # download a different runtime implicitly when checking the connection.
        return CopilotClient(connection=RuntimeConnection.for_stdio(path=args[0],args=args[1:]),
            working_directory=str(working_directory or home),base_directory=str(home),env=env,use_logged_in_user=True)

    def status(self, provider):
        if provider not in CLIENTS: raise ValueError('Este proveedor utiliza API o un motor local.')
        result={'provider':provider,'installed':bool(executable(provider)),'authenticated':None,'docs':CLIENTS[provider][2]}
        if not result['installed']: return result
        if provider=='codex':result.update(self.codex.status())
        elif provider=='claude-code':
            env,home=self.environment(provider)
            try:
                p=subprocess.run(client_argv(provider)+['auth','status'],env=env,cwd=home,capture_output=True,text=True,encoding='utf-8',timeout=8,creationflags=FLAGS)
                data=json.loads(p.stdout);result.update(authenticated=data.get('loggedIn',False),account=data.get('email',''),plan=data.get('subscriptionType',''))
            except (OSError,ValueError,subprocess.TimeoutExpired):result['note']='No se pudo verificar la sesión. Actualiza el cliente oficial.'
        else:result['note']='La cuenta y su cuota se comprueban al consultar modelos o enviar la primera petición.'
        return result

    def login(self, provider, manager):
        if provider=='codex':return self.codex.login()
        if provider not in CLIENTS:raise ValueError('Proveedor sin acceso por cuenta.')
        env,home=self.environment(provider)
        args=client_argv(provider)+({'claude-code':['auth','login'],'copilot':['login'],'gemini-cli':[]}[provider])
        with manager.lock:
            if sum(not s.closed for s in manager.sessions.values())>=6:raise ValueError('Cierra una terminal antes de iniciar sesión.')
            profile={'id':'account:'+provider,'label':CLIENTS[provider][1]+' · Acceso','argv':args,'kind':'account','available':True}
            session=TerminalSession(profile,home,manager.project,100,26,environment=env)
            manager.sessions[session.id]=session
        return {'mode':'terminal','id':session.id,'profile':{k:v for k,v in profile.items() if k!='argv'},'kind':session.kind}

    def models(self, provider):
        if provider=='codex':return self.codex.models()
        if not executable(provider):raise ValueError('Instala primero el cliente oficial de este proveedor.')
        if provider=='claude-code' and self.status(provider).get('authenticated') is not True:raise ValueError('Inicia sesión en Claude Code desde este panel.')
        return {'models':['auto'],'verified':False,'note':'auto utiliza el modelo predeterminado del cliente. Su acceso se verifica al generar; no es un catálogo de modelos autorizados.'}

    def stream(self,job,messages,system,timeout):
        if job.provider=='codex':return self.codex.stream(job,messages,system,timeout)
        provider=job.provider;env,home=self.environment(provider)
        prompt=system+'\n\n'+'\n\n'.join(m['role'].upper()+':\n'+m['content'] for m in messages)
        with tempfile.TemporaryDirectory(prefix='review-',dir=home) as cwd:
            args=client_argv(provider)
            if provider=='claude-code':
                args+=['-p','--output-format','stream-json','--verbose','--include-partial-messages','--tools','',
                       '--disallowedTools','mcp__*','--strict-mcp-config','--mcp-config','{"mcpServers":{}}',
                       '--setting-sources','','--disable-slash-commands','--no-session-persistence']
            else:args+=['--output-format','stream-json','--prompt','Responde a la petición de programación adjunta por stdin.']
            if job.model!='auto':args+=['--model',job.model]
            process=subprocess.Popen(args,cwd=cwd,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                text=True,encoding='utf-8',errors='replace',bufsize=1,creationflags=FLAGS)
            events=queue.Queue();errors=[]
            def read():
                for line in process.stdout:events.put(line)
                events.put(None)
            def stderr():
                for line in process.stderr:
                    errors.append(line)
                    if len(errors)>30:errors.pop(0)
            threading.Thread(target=read,daemon=True).start();threading.Thread(target=stderr,daemon=True).start()
            try:
                process.stdin.write(prompt);process.stdin.close();deadline=time.monotonic()+timeout
                while not job.cancelled.is_set():
                    if time.monotonic()>deadline:raise ValueError('El cliente ha superado el tiempo de respuesta. Comprueba sesión y cuota.')
                    try:line=events.get(timeout=.15)
                    except queue.Empty:continue
                    if line is None:break
                    try:msg=json.loads(line)
                    except ValueError:continue
                    if provider=='claude-code':
                        event=msg.get('event',{})
                        if event.get('type')=='content_block_delta':job.append(event.get('delta',{}).get('text',''))
                        if msg.get('type')=='result':
                            if msg.get('is_error'):raise ValueError(str(msg.get('result') or msg.get('errors') or 'Comprueba tu sesión y los límites de Claude.')[:500])
                            if not job.text:job.append(msg.get('result',''))
                    elif msg.get('type')=='message' and msg.get('role')=='assistant':job.append(msg.get('content',''))
                    elif msg.get('type')=='result' and msg.get('status')=='error':raise ValueError(str(msg.get('error','Comprueba tu sesión de Google y la cuota.'))[:500])
                if not job.cancelled.is_set() and process.wait(timeout=3)!=0:
                    raise ValueError('El cliente oficial rechazó la petición. Comprueba el inicio de sesión, su versión, el modelo y la cuota de tu plan.')
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:process.wait(timeout=3)
                    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=3)
                process.stdout.close();process.stderr.close()

    def shutdown(self):self.codex.shutdown()
