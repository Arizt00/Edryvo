#!/usr/bin/env python3
"""Optional real-system verification; uses isolated temporary folders, not user projects."""
from pathlib import Path
import sys,tempfile,shutil,time,json,os
r=Path(__file__).resolve().parents[1];sys.path.insert(0,str(r))
from backend.server import Application
exe=shutil.which('clangd');assert exe
with tempfile.TemporaryDirectory(prefix='lumen04-clangd-') as td:
 td=Path(td);ws=td/'project';ws.mkdir();text='struct Point { int x; int y; };\nint main() {\n  Point p{};\n  p.x = 1;\n  return p.y;\n}\n';f=ws/'main.cpp';f.write_text(text)
 app=Application(r,ws,data_dir=td/'config');app.workspace.trusted=True
 try:
  app.features.tools.save({'tasks':[],'servers':[{'id':'clangd-qa','label':'clangd actual','argv':[exe,'--background-index=false'],'languages':['cpp']}],'associations':{}})
  session=app.features.lsp.start(app.workspace,'clangd-qa',True);sid=session['id']
  app.features.lsp.notify(sid,'textDocument/didOpen',{'textDocument':{'uri':f.as_uri(),'languageId':'cpp','version':1,'text':text}})
  for _ in range(50):
   if any(e['method']=='textDocument/publishDiagnostics' for e in app.features.lsp.get(sid).poll(0)['events']):break
   time.sleep(.1)
  result=app.features.lsp.request(sid,'textDocument/completion',{'textDocument':{'uri':f.as_uri()},'position':{'line':3,'character':4},'context':{'triggerKind':2,'triggerCharacter':'.'}})['result']
  items=result if isinstance(result,list) else result.get('items',[]);labels=[x.get('filterText',x['label']) for x in items];assert 'x' in labels and 'y' in labels and 'main' not in labels,labels
  events=app.features.lsp.get(sid).poll(0);print(json.dumps({'executable':exe,'labels':labels,'capabilities':list(session['capabilities']),'diagnosticEvents':sum(x['method']=='textDocument/publishDiagnostics' for x in events['events'])},indent=2))
  Path(os.environ.get('LUMEN_CLANGD_REPORT', 'clangd_results.json')).write_text(json.dumps({'passed':True,'server':'clangd real executable','executable':exe,'language':'C++','checked':['initialize','didOpen','semantic member completion x/y'],'completionLabels':labels,'scope':'Backend LSP transport. Not a Monaco integration check; not all LSP features.'},indent=2))
 finally:app.features.shutdown();app.runner.shutdown()
