#!/usr/bin/env python3
"""Deterministic LSP protocol fixture, not a real language analysis engine."""
import json
import sys

def send(message):
    raw=json.dumps(message).encode();sys.stdout.buffer.write(b'Content-Length: '+str(len(raw)).encode()+b'\r\n\r\n'+raw);sys.stdout.buffer.flush()
while True:
    head={}
    while True:
        line=sys.stdin.buffer.readline()
        if not line:raise SystemExit
        if line in (b'\r\n',b'\n'):break
        k,_,v=line.decode().partition(':');head[k.lower()]=v.strip()
    msg=json.loads(sys.stdin.buffer.read(int(head.get('content-length','0'))));method=msg.get('method');params=msg.get('params',{})
    if method=='exit':break
    if 'id' in msg:
        result=None
        if method=='initialize':result={'capabilities':{'positionEncoding':'utf-16','textDocumentSync':1,'completionProvider':{'triggerCharacters':['.']},'hoverProvider':True,'definitionProvider':True,'documentSymbolProvider':True}}
        elif method=='textDocument/completion':result={'isIncomplete':False,'items':[{'label':'fixtureCompletion','kind':3,'insertText':'fixtureCompletion()'}]}
        elif method=='textDocument/hover':result={'contents':{'kind':'plaintext','value':'Lumen protocol fixture'}}
        elif method=='textDocument/definition':result=[{'uri':params['textDocument']['uri'],'range':{'start':{'line':0,'character':0},'end':{'line':0,'character':5}}}]
        elif method=='textDocument/documentSymbol':result=[]
        send({'jsonrpc':'2.0','id':msg['id'],'result':result})
    if method in ('textDocument/didOpen','textDocument/didChange'):
        send({'jsonrpc':'2.0','method':'textDocument/publishDiagnostics','params':{'uri':params['textDocument']['uri'],'diagnostics':[{'range':{'start':{'line':0,'character':0},'end':{'line':0,'character':1}},'severity':2,'message':'Fixture warning; no real semantic analysis.'}]}})
