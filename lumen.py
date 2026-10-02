#!/usr/bin/env python3
"""Local command line for an already running Lumen instance."""
from __future__ import annotations
import argparse
import http.cookiejar
import json
import urllib.parse
import urllib.request
from backend.preferences import user_data_dir


def send_command(command):
    path=user_data_dir()/'instance.json'
    try:state=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError) as e:raise ValueError('Inicia Lumen antes de enviar un comando.') from e
    base=state.get('url','');p=urllib.parse.urlparse(base)
    if p.scheme!='http' or p.hostname!='127.0.0.1' or not p.port or p.path not in ('','/') or p.username or p.password:
        raise ValueError('Registro de instancia local no válido.')
    client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),urllib.request.ProxyHandler({}))
    try:
        client.open(base,timeout=3).read()
        data=json.loads(client.open(base+'/api/bootstrap',timeout=3).read())
        req=urllib.request.Request(base+'/api/platform/ui/command',data=json.dumps({'command':command}).encode(),
            headers={'Content-Type':'application/json','X-Lumen-Token':data['token'],'Origin':base})
        return json.loads(client.open(req,timeout=3).read())
    except OSError as e:raise ValueError('La instancia registrada no responde. Vuelve a abrir Lumen.') from e


def main(argv=None):
    parser=argparse.ArgumentParser(description='Lumen · comandos de interfaz local')
    parser.add_argument('command',choices=['focus','concentracion','settings','extensions','lantern'])
    parser.add_argument('state',nargs='?',choices=['toggle','on','off'],default='toggle')
    args=parser.parse_args(argv)
    command='lumen.focus.'+args.state if args.command in ('focus','concentracion') else 'lumen.'+args.command+'.open'
    try:
        result=send_command(command);print('Comando enviado a Lumen:',result['command'])
    except ValueError as e:parser.exit(1,str(e)+'\n')

if __name__=='__main__':main()
