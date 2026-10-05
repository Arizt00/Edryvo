"""Reviewed, bounded dependency graphs and atomic package-index installation."""
import os
import secrets
import shutil
import time
from .preferences import atomic_json

MAX_PLAN_PACKAGES = 32


class ExtensionInstallPlans:
    def prepare_plan(self, ticket, include_packs=False, progress=lambda **kw: None, cancelled=lambda: False):
        if type(include_packs) is not bool:
            raise ValueError('Selección de paquetes no válida.')
        with self.lock:
            self._expire();self.refresh_index()
            item=self.pending.get(ticket)
            if not item:raise ValueError('La revisión ha caducado. Revisa el paquete de nuevo.')
            root=dict(item[2])
            preparing=getattr(self,'preparing_plans',set())
            if ticket in preparing or any(p['rootTicket']==ticket for p in self.plans.values()):
                raise ValueError('Este paquete ya tiene un plan pendiente.')
            self.preparing_plans=preparing;preparing.add(ticket)
            installed={key.casefold():value for key,value in self.installed.items()}
        acquired=[];ordered=[];states={};existing={};path=[]
        def update(**values):
            if cancelled():raise InterruptedError('Revisión cancelada.')
            # Downloading a large child must not expire the already reviewed parent.
            with self.lock:
                for key in [ticket,*acquired]:
                    if key in self.pending:
                        _,folder,result=self.pending[key];self.pending[key]=(time.monotonic(),folder,result)
            progress(package=path[-1] if path else root['id'],packagesReady=len(ordered),**values)
        def visit(info):
            key=info['id'].casefold()
            if states.get(key)=='done':return
            if states.get(key)=='visiting':raise ValueError('Dependencias circulares: '+' → '.join([*path,info['id']]))
            if len(states)>=MAX_PLAN_PACKAGES:raise ValueError('El plan supera los 32 paquetes. Revisa un grupo más pequeño.')
            states[key]='visiting';path.append(info['id'])
            for dependency in info.get('dependencies',[]):
                if not dependency['required'] and not include_packs:continue
                dep_key=dependency['id'].casefold()
                if dep_key==root['id'].casefold() or states.get(dep_key)=='visiting':
                    raise ValueError('Dependencias circulares: '+' → '.join([*path,dependency['id']]))
                if dep_key in installed:
                    value=installed[dep_key]
                    existing[dep_key]={'id':value['id'],'version':value['version'],'enabled':bool(value.get('enabled'))}
                    continue
                if states.get(dep_key)=='done':continue
                update(phase='metadata',received=0,total=0,dependency=dependency['id'])
                child=self.inspect_remote(dependency['id'],progress=update,cancelled=cancelled)
                acquired.append(child['ticket']);visit(child)
            path.pop();states[key]='done';ordered.append(info)
        try:
            visit(root);update(phase='ready',received=0,total=0)
            result={'plan':secrets.token_urlsafe(24),'id':root['id'],'displayName':root['displayName'],
                'includePacks':include_packs,'packages':[{k:v for k,v in x.items() if k!='ticket'} for x in ordered],
                'existing':list(existing.values()),'size':sum(x['size'] for x in ordered),
                'unpackedSize':sum(x['unpackedSize'] for x in ordered)}
            with self.lock:
                if ticket not in self.pending:raise ValueError('Se cerró la revisión del paquete principal.')
                self.plans[result['plan']]={'created':time.monotonic(),'rootTicket':ticket,
                    'tickets':[x['ticket'] for x in ordered],'result':result}
            return result
        except Exception:
            for child in acquired:self.discard(child)
            raise
        finally:
            with self.lock:self.preparing_plans.discard(ticket)

    def discard_plan(self, key):
        with self.lock:
            plan=self.plans.pop(key,None)
            if plan:
                for ticket in plan['tickets']:self.discard(ticket)

    def install_plan(self, key, consent=False):
        if consent is not True:raise PermissionError('Revisa los paquetes, tamaños y licencias antes de instalar el plan.')
        with self.lock,self.index_transaction():
            self._expire();plan=self.plans.get(key)
            if not plan:raise ValueError('El plan ha caducado. Revisa las dependencias de nuevo.')
            items=[self.pending.get(ticket) for ticket in plan['tickets']]
            if not all(items):raise ValueError('Un paquete del plan ha caducado. Revisa las dependencias de nuevo.')
            next_index=dict(self.installed);moved=[];receipts=[];added=[];reused=[]
            try:
                for ticket,(_,folder,info) in zip(plan['tickets'],items):
                    current=next((x for k,x in next_index.items() if k.casefold()==info['id'].casefold()),None)
                    # Preserve another window's install and a user's disabled dependency.
                    if current and ticket!=plan['rootTicket']:
                        reused.append(current['id']);continue
                    result={k:v for k,v in info.items() if k!='ticket'}
                    target=self.root/(result['id']+'-'+result['sha256'][:16]);result['directory']=target.name
                    if not target.exists():os.replace(folder,target);moved.append((target,folder))
                    receipt=target/'.lumen-install.json';receipts.append((receipt,receipt.read_bytes() if receipt.exists() else None))
                    atomic_json(receipt,result)
                    if current and current['id']!=result['id']:next_index.pop(current['id'],None)
                    next_index[result['id']]=result;added.append(result)
                atomic_json(self.index,next_index)
            except Exception:
                for receipt,raw in reversed(receipts):
                    if raw is None:receipt.unlink(missing_ok=True)
                    else:receipt.write_bytes(raw)
                for target,folder in reversed(moved):os.replace(target,folder)
                raise
            previous=self.installed;self.installed=next_index
            self.plans.pop(key,None)
            for ticket in plan['tickets']:self.discard(ticket)
            for old in previous.values():
                new=next((x for k,x in next_index.items() if k.casefold()==old['id'].casefold()),None)
                if new and old.get('directory')!=new.get('directory'):self._remove_payload(old)
            warnings=[]
            for result in added:
                try:self.prefs.audit('extension.install',extension=result['id'],plan=plan['result']['id'])
                except OSError:warnings.append('Se instaló '+result['id']+', pero no se pudo guardar su registro de auditoría.')
            return {'installed':added,'reused':reused,'extensions':self.list(),'warnings':warnings}
