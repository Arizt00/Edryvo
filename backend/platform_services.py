"""Authenticated platform routes, composed without changing legacy API contracts."""
from __future__ import annotations
import json
import threading
import time
from .preferences import Preferences
from .extensions import ExtensionStore
from .terminals import TerminalManager
from .hardware import HardwareMonitor
from .toolchains import Toolchains
from .lsp import LanguageServers
from .providers import AIRouter
from .studio import StudioState
from .debug_manager import DebugManager
from .runtimes import Runtimes
from .preview import WebPreview
from .lantern import Lantern
from .diagnostics import inspect_buffer, output_diagnostics
from .downloads import Downloads
from .extension_runtime import ExtensionRuntime
from .hacker import Hacker
from .updates import Updates
from .buffers import Buffers


class PlatformServices:
    def __init__(self,app,directory=None):
        self.app=app;self.prefs=Preferences(directory);self.extensions=ExtensionStore(self.prefs)
        self.terminals=TerminalManager(self.prefs,app.project);self.tools=Toolchains(self.prefs,app.runner)
        self.lsp=LanguageServers(self.prefs,self.tools);self.ai=AIRouter(self.prefs);self.hardware=HardwareMonitor(self.prefs)
        self.command_seq=0;self.command_events=[];self.command_lock=threading.Lock()
        self.studio=StudioState(self.prefs.directory)
        self.runtimes=Runtimes(self.prefs);self.preview=WebPreview();self.debugger=DebugManager(self.runtimes,app.runner)
        self.lantern=Lantern(self.runtimes,app.runner,self.preview)
        self.downloads=Downloads(self.prefs.directory);self.extension_runtime=ExtensionRuntime(self.extensions)
        self.hacker=Hacker(self);self.updates=Updates(self.prefs,self.downloads)
        self.buffers=Buffers()
    def state(self):
        web=self.app.project/'web/vendor'
        return {'version':'0.5.2','preferences':self.prefs.export(),'providers':self.ai.vault.state(),
                'xterm':(web/'xterm/xterm.js').is_file() and (web/'xterm-fit/addon-fit.js').is_file(),
                'installedExtensions':len(self.extensions.installed),'dataDirectory':str(self.prefs.directory),
                'development':self.tools.discover_servers(),'commandSequence':self.command_seq}
    def _trusted(self):
        if not self.app.workspace.trusted:raise PermissionError('El proyecto no es de confianza. Autorízalo antes de continuar.')
    def _terminal(self,sid):
        session=self.terminals.get(sid)
        if session.profile.get('kind')!='account':self._trusted()
        return session
    def get(self,path,query):
        q=lambda key,default='':query.get(key,[default])[0]
        if path=='/state':return self.state()
        if path=='/hacker':return self.hacker.tools()
        if path=='/updates':return self.updates.snapshot()
        if path=='/buffers':return self.buffers.snapshot()
        if path=='/settings':return self.prefs.describe()
        if path=='/studio':return self.studio.export()
        if path=='/debug':return self.debugger.snapshot()
        if path=='/lantern':return self.lantern.snapshot()
        if path=='/lantern/template':return self.lantern.template(q('language'))
        if path=='/downloads':return self.downloads.snapshot()
        if path=='/extensions/runtime':return self.extension_runtime.snapshot()
        if path=='/extensions/review':return self.extensions.review_status(q('id'))
        if path=='/extensions/updates':return self.extensions.updates()
        if path=='/languages':return self.runtimes.status()
        if path=='/extensions':return {'extensions':self.extensions.list()}
        if path=='/extensions/search':return self.extensions.search(q('q'),int(q('offset','0')))
        if path=='/extensions/contributions':return self.extensions.contributions()
        if path=='/terminals/profiles':return self.terminals.profiles()
        if path=='/terminals':return {'sessions':self.terminals.list()}
        if path=='/terminals/read':return self._terminal(q('id')).read(int(q('offset','0')))
        if path=='/tools':return self.tools.detect(q('refresh')=='1')
        if path=='/hardware':return self.hardware.sample()
        if path=='/ai/providers':return {'providers':self.ai.vault.state()}
        if path=='/ai/account':return self.ai.accounts.status(q('provider'))
        if path=='/ai/job':return self.ai.get(q('id')).state(int(q('offset','0')))
        if path=='/lsp/events':self._trusted();return self.lsp.get(q('id')).poll(int(q('after','0')))
        if path=='/ui/events':
            after=int(q('after','0'))
            with self.command_lock:return {'events':[x for x in self.command_events if x['seq']>after],'sequence':self.command_seq}
        if path=='/audit':
            p=self.prefs.directory/'audit.jsonl'
            return {'lines':p.read_text(encoding='utf-8').splitlines()[-150:] if p.exists() else []}
        raise FileNotFoundError('Ruta de plataforma desconocida.')
    def post(self,path,body):
        ws=self.app.workspace
        if path=='/buffers':return self.buffers.update(ws,body)
        if path=='/hacker/start':return self.hacker.start(ws,body.get('path',''),body.get('content'),body.get('mode'))
        if path=='/hacker/attach':return self.hacker.attach(ws,body.get('job'))
        if path=='/updates/check':return self.updates.check(body.get('download') is True)
        if path=='/updates/download':return self.updates.download()
        if path=='/files/operation':
            from .file_actions import perform
            return perform(ws,body)
        if path=='/downloads/start':return self.downloads.start(body.get('url',''),body.get('name',''),body.get('sha256',''))
        if path=='/downloads/pause':return self.downloads.pause(body.get('id'))
        if path=='/downloads/resume':return self.downloads.resume(body.get('id'))
        if path=='/extensions/runtime/start':return self.extension_runtime.start(ws,body.get('id'),body.get('consent'))
        if path=='/extensions/runtime/stop':return self.extension_runtime.stop(body.get('id'),forget=True)
        if path=='/extensions/runtime/restore':return self.extension_runtime.restore(ws)
        if path=='/extensions/runtime/request':return self.extension_runtime.request(ws,body)
        if path=='/lantern/start':
            if self.debugger.snapshot()['status'] in ('running','paused'):self.debugger.stop()
            return self.lantern.start(ws,body.get('path',''),body.get('content'),body.get('version'))
        if path=='/lantern/buffer':return self.lantern.buffer(ws,body.get('path',''),body.get('content'),body.get('version'))
        if path=='/lantern/stop':return self.lantern.stop()
        if path=='/lantern/restart':self._trusted();return self.lantern.restart()
        if path=='/diagnostics':return inspect_buffer(ws,self.runtimes,body.get('path',''),body.get('content',''))
        if path=='/diagnostics/check':
            if not ws.trusted:return {'skipped':'workspace-trust'}
            if self.lantern.snapshot()['active']:return {'skipped':'lantern'}
            plan=self.runtimes.plan(ws,body.get('path',''),check=True)
            return self.app.runner.start(plan['commands'],ws.root,timeout=20) if plan['commands'] else {'output':''}
        if path=='/diagnostics/output':return {'diagnostics':output_diagnostics(str(body.get('output',''))[:512000],str(body.get('path','')))}
        if path=='/studio':return self.studio.update(body)
        if path=='/languages/config':return self.runtimes.save(body)
        if path=='/preview':return self.preview.start(ws,body.get('path',''),body.get('buffers'))
        if path=='/debug/start':
            self.lantern.stop()
            return self.debugger.start(ws,body.get('path',''),body.get('breakpoints',[]))
        if path=='/debug/command':self._trusted();return self.debugger.command(body.get('command'))
        if path=='/debug/input':self._trusted();return self.debugger.input(body.get('text'))
        if path=='/settings':
            result=self.prefs.update(body.get('settings',{}),body.get('reset') is True)
            if not self.prefs.get('security.terminals'):self.terminals.shutdown()
            if not self.prefs.get('security.cloudAI'):
                for j in list(self.ai.jobs.values()):
                    if not j.done and j.provider not in ('ollama','emma'):j.cancel()
            return result
        if path=='/extensions/inspect':
            return self.extensions.inspect_local(body['path']) if 'path' in body else self.extensions.inspect_remote(body.get('id',''),body.get('version','latest'))
        if path=='/extensions/review/start':return self.extensions.start_review(body)
        if path=='/extensions/review/cancel':return self.extensions.review_status(body.get('id'),cancel=True)
        if path=='/extensions/install':return self.extensions.install(body.get('ticket',''),body.get('consent'))
        if path=='/extensions/discard':self.extensions.discard(body.get('ticket',''));return {'discarded':True}
        if path=='/extensions/toggle':
            self.extension_runtime.stop(body.get('id'))
            return self.extensions.update_state(body.get('id'),body.get('enabled'))
        if path=='/extensions/remove':
            if body.get('consent') is not True:raise PermissionError('Confirma la desinstalación.')
            self.extension_runtime.stop(body.get('id'))
            return self.extensions.update_state(body.get('id'),remove=True)
        if path=='/extensions/updates':return self.extensions.updates()
        if path=='/extensions/export':return self.extensions.export_package(body.get('id'))
        if path=='/terminals/create':return self.terminals.create(ws,body.get('profile'),body.get('consent'),body.get('cols',100),body.get('rows',26))
        if path=='/terminals/write':
            terminal=self._terminal(body.get('id'));written=terminal.write(body.get('data',''))
            return {'ok':written,'closed':terminal.closed}
        if path=='/terminals/resize':self._terminal(body.get('id')).resize(body.get('cols',100),body.get('rows',26));return {'ok':True}
        if path=='/terminals/close':self.terminals.get(body.get('id')).close();return {'closed':True}
        if path=='/development':return self.tools.save(body)
        if path=='/tasks/run':return self.tools.run(ws,body.get('id'),body.get('file',''),body.get('consent'))
        if path=='/tools/plan':return self.tools.plan(body.get('package'),body.get('manager'))
        if path=='/lsp/start':return self.lsp.start(ws,body.get('profile'),body.get('consent'))
        if path=='/lsp/request':self._trusted();return self.lsp.request(body.get('id'),body.get('method'),body.get('params',{}))
        if path=='/lsp/notify':self._trusted();return self.lsp.notify(body.get('id'),body.get('method'),body.get('params',{}))
        if path=='/lsp/stop':return self.lsp.stop(body.get('id'))
        if path=='/ai/credential':return self.ai.vault.set(body.get('provider'),body.get('key'),body.get('remember') is True)
        if path=='/ai/account/login':
            if not self.prefs.get('security.terminals'):raise PermissionError('Activa las terminales para iniciar el cliente oficial.')
            result=self.ai.accounts.login(body.get('provider'),self.terminals)
            if result.get('mode')=='browser':
                import webbrowser
                threading.Thread(target=webbrowser.open,args=(result['url'],),daemon=True).start()
            return result
        if path=='/ai/account/logout':
            if body.get('provider')!='codex':raise ValueError('Cierra la sesión desde el cliente oficial de este proveedor.')
            return self.ai.accounts.codex.logout()
        if path=='/ai/forget':return self.ai.vault.delete(body.get('provider'))
        if path=='/ai/models':return self.ai.models(body.get('provider'),body.get('consent'))
        if path=='/ai/start':return self.ai.start(body)
        if path=='/ai/cancel':self.ai.get(body.get('id')).cancel();return {'cancelled':True}
        if path=='/ai/clear':
            self.ai.clear_history()
            return {'cleared':True}
        if path=='/ui/command':
            allowed={'lumen.focus.toggle','lumen.focus.on','lumen.focus.off','lumen.settings.open','lumen.extensions.open','lumen.lantern.open'}
            command=body.get('command')
            if command not in allowed:raise ValueError('Comando de interfaz no admitido.')
            with self.command_lock:
                self.command_seq+=1;self.command_events.append({'seq':self.command_seq,'command':command});self.command_events=self.command_events[-100:]
            return {'queued':True,'sequence':self.command_seq,'command':command}
        raise FileNotFoundError('Operación de plataforma desconocida.')
    def workspace_changed(self):
        self.buffers.clear()
        self.extension_runtime.shutdown()
        self.lantern.stop();self.debugger.stop();self.preview.stop()
        self.terminals.shutdown();self.lsp.shutdown()
        for job in list(self.ai.jobs.values()):
            if not job.done:job.cancel()
        self.ai.clear_history()
    def shutdown(self):
        self.updates.shutdown()
        self.workspace_changed();self.ai.shutdown();self.extensions.shutdown();self.downloads.shutdown()
        self.hacker.shutdown()
