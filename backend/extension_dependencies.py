"""Validate installed required dependencies before a single host is started."""
from pathlib import Path
from .extensions import localized_manifest

def dependency_graph(store,eid):
    store.refresh_index();items={key.casefold():value for key,value in store.installed.items()}
    states={};ordered=[];stack=[]
    def visit(key):
        key=key.casefold()
        if states.get(key)=='done':return
        if states.get(key)=='visiting':raise ValueError('Dependencias circulares: '+' → '.join([*stack,key]))
        item=items.get(key)
        if not item:raise ValueError('Falta la dependencia '+key+'. Revisa el paquete y sus dependencias.')
        if not item.get('enabled'):raise ValueError('La dependencia '+item['id']+' está desactivada. Su estado se conserva; actívala explícitamente.')
        if len(states)>=32:raise ValueError('La activación admite hasta 32 dependencias.')
        root=(store.root/item['directory']/'extension').resolve()
        if not root.is_relative_to(store.root.resolve()):raise ValueError('Ruta de extensión no válida.')
        manifest=localized_manifest(root,store.prefs.get('general.locale'))
        states[key]='visiting';stack.append(item['id'])
        required=manifest.get('extensionDependencies',[])
        if not isinstance(required,list) or any(not isinstance(x,str) for x in required):raise ValueError('Dependencias declaradas no válidas.')
        for dependency in required:visit(dependency)
        stack.pop();states[key]='done'
        ordered.append({'id':item['id'],'root':str(root),'manifest':manifest})
    visit(eid)
    return ordered
