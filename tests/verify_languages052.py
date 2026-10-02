import sys,tempfile,time,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.server import Application
base=Path(tempfile.mkdtemp(prefix='lumen-languages-'));base.mkdir(exist_ok=True);ws=base/'workspace';ws.mkdir(exist_ok=True)
samples={
'hello.py':'x=2\nx+=3\nprint("LUMEN_TEST",x)\n',
'hello.js':'let x = 2;\nx += 3;\nconsole.log("LUMEN_TEST", x);\n',
'hello.c':'#include <stdio.h>\nint main(void) {\n int x=2;\n x+=3;\n printf("LUMEN_TEST %d\\n",x);\n return 0;\n}\n',
'hello.cpp':'#include <iostream>\nint main() {\n int x=2;\n x+=3;\n std::cout << "LUMEN_TEST " << x << std::endl;\n return 0;\n}\n',
'hello.rs':'fn main() {\n let mut x = 2;\n x += 3;\n println!("LUMEN_TEST {}",x);\n}\n',
'Hello.java':'public class Hello {\n public static void main(String[] args) {\n  int x=2;\n  x+=3;\n  System.out.println("LUMEN_TEST " + x);\n }\n}\n',
'hello.cs':'int x=2;\nx+=3;\nSystem.Console.WriteLine("LUMEN_TEST " + x);\n',
'hello.n':'use <io:output>;\nhelloCompacto {\n to main {\n println("LUMEN_TEST 5");\n }\n fa:\n return true;\n}\n',
'index.html':'<!doctype html><link rel="stylesheet" href="/style.css"><h1>Lumen</h1>',
'style.css':'h1{color:red}',
}
for name,text in samples.items():(ws/name).write_text(text,encoding='utf-8')
app=Application(ROOT,ws,data_dir=base/'profile');app.workspace.trusted=True;rt=app.features.runtimes;d=app.features.debugger
report=[]
def wait(pred,timeout=30):
 deadline=time.monotonic()+timeout
 while time.monotonic()<deadline:
  if pred():return
  time.sleep(.04)
 raise AssertionError('timeout '+str(d.snapshot()))
try:
 for name in list(samples)[:8]:
  record={'file':name};report.append(record)
  try:
   plan=rt.plan(app.workspace,name);job=app.runner.jobs[app.runner.start(plan['commands'],ws)['job']];wait(lambda:job.done,120)
   record['run']={'code':job.code or 0,'output':job.output[-2400:]};print('RUN',name,job.code,job.output[-450:],flush=True)
   if job.code:continue
   points=[3] if name.endswith(('.py','.js')) else [5] if name.endswith(('.c','.cpp','.java')) else [4]
   d.start(app.workspace,name,points);wait(lambda:d.snapshot()['status'] in ('paused','error','finished'),60)
   record['debug_entry']=d.snapshot();print('DEBUG',name,json.dumps(d.snapshot(),ensure_ascii=True)[-1800:],flush=True)
   if d.snapshot()['status']=='paused':
    initial=d.snapshot().get('line');d.command('next');wait(lambda:d.snapshot()['status'] in ('error','finished') or d.snapshot()['status']=='paused' and d.snapshot().get('line')!=initial,30)
    record['debug_step']=d.snapshot();print('STEP',name,json.dumps(d.snapshot(),ensure_ascii=True)[-1000:],flush=True)
    for _ in range(8):
     if d.snapshot()['status']!='paused':break
     d.command('continue');time.sleep(.3);wait(lambda:d.snapshot()['status'] in ('paused','error','finished'),20)
    record['debug_final']=d.snapshot()
  except Exception as exc:record['error']=str(exc);print('ERROR',name,str(exc),flush=True)
  finally:d.stop();time.sleep(.15)
finally:
 app.features.shutdown();app.runner.shutdown();(base/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
