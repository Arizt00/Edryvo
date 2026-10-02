"""Explorer operations with workspace boundaries and a recoverable local trash."""
import json
from pathlib import Path
import shutil
import time
import uuid
from .preferences import atomic_json

def target(ws, name, exists=True):
    result=ws.resolve(name,must_exist=exists)
    if result==ws.root or any(part in ('.git','.lumen') for part in result.relative_to(ws.root).parts):
        raise ValueError('Esta carpeta pertenece al sistema del proyecto.')
    for item in (result,*result.parents):
        if hasattr(item,'is_junction') and item.is_junction():raise ValueError('No se operan uniones de Windows.')
    return result

def perform(ws, body):
    operation=body.get('operation');name=body.get('path','')
    with ws.lock:
        if operation=='restore':
            ticket=body.get('ticket','')
            if not isinstance(ticket,str) or len(ticket)!=32 or any(c not in '0123456789abcdef' for c in ticket):raise ValueError('Identificador no válido.')
            folder=ws.private_dir('trash')/ticket
            from .uninstall import no_links
            no_links(folder);no_links(folder/'content');no_links(folder/'metadata.json')
            data=json.loads((folder/'metadata.json').read_text(encoding='utf-8'))
            destination=target(ws,data['path'],False)
            if destination.exists():raise ValueError('Ya existe un archivo en la ubicación original.')
            destination.parent.mkdir(parents=True,exist_ok=True)
            (folder/'content').rename(destination);(folder/'metadata.json').unlink();folder.rmdir()
            return {'path':data['path']}
        source=target(ws,name,operation!='mkdir')
        if operation=='mkdir':source.mkdir();return {'path':name}
        if operation=='delete':
            ticket=uuid.uuid4().hex;folder=ws.private_dir('trash')/ticket;folder.mkdir()
            atomic_json(folder/'metadata.json',{'path':name,'deletedAt':time.time()})
            source.rename(folder/'content')
            return {'ticket':ticket,'path':name,'recoverable':True}
        if operation in ('rename','copy','move'):
            destination=target(ws,body.get('destination',''),False)
            if destination.exists():raise ValueError('Ya existe un archivo con ese nombre.')
            if destination.is_relative_to(source):raise ValueError('Una carpeta no se puede mover dentro de sí misma.')
            if not destination.parent.is_dir():raise ValueError('La carpeta de destino no existe.')
            if operation=='copy':
                if source.is_dir():
                    for item in source.rglob('*'):target(ws,item.relative_to(ws.root).as_posix())
                    shutil.copytree(source,destination)
                else:shutil.copy2(source,destination)
            else:source.rename(destination)
            return {'path':destination.relative_to(ws.root).as_posix()}
        raise ValueError('Operación de archivo desconocida.')
