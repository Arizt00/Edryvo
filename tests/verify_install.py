#!/usr/bin/env python3
"""Optional real-system verification; uses isolated temporary folders, not user projects."""
from pathlib import Path
import tempfile,subprocess,sys,os,json,time,urllib.request
root=Path(__file__).resolve().parents[1];results=[]
with tempfile.TemporaryDirectory(prefix='lumen04-install-qa-') as td:
 td=Path(td);target=td/'App With Spaces';data=td/'data';data.mkdir();env={**os.environ,'LUMEN_DATA_DIR':str(data)}
 p=subprocess.run([sys.executable,str(root/'tools/install_user.py'),'--target',str(target),'--skip-dependencies','--skip-assets'],capture_output=True,text=True);assert p.returncode==0,(p.stdout,p.stderr);print(p.stdout,flush=True)
 installed=target/'versions/0.4.0';launcher=target/'bin/lumen';assert launcher.exists();results.append('Per-user source installer creates private environment and quoted launcher in a path with spaces; no dependency network')
 (data/'keep-after-uninstall.txt').write_text('User data belongs to the user.');log=(td/'app.log').open('w')
 process=subprocess.Popen([str(launcher),'--no-browser','--port','0'],env=env,stdout=log,stderr=subprocess.STDOUT)
 try:
  for i in range(100):
   if (data/'instance.json').exists():break
   if process.poll() is not None:raise AssertionError((td/'app.log').read_text())
   time.sleep(.1)
  instance=json.loads((data/'instance.json').read_text());base=instance['url']
  with urllib.request.urlopen(base) as response:assert response.status==200;assert 'Lumen' in response.read().decode()
  results.append('Installed source launches actual loopback HTTP application from private venv')
  p=subprocess.run([str(launcher),'focus'],env=env,capture_output=True,text=True);assert p.returncode==0,(p.stdout,p.stderr);print(p.stdout,flush=True);results.append('Installed lumen command queues focus toggle against running instance')
 finally:process.terminate();process.wait(8);log.close()
 p=subprocess.run([sys.executable,str(installed/'tools/uninstall_user.py'),'--yes'],capture_output=True,text=True);assert p.returncode==0,(p.stdout,p.stderr);assert not installed.exists();assert not launcher.exists();assert (data/'keep-after-uninstall.txt').exists();results.append('Uninstaller removes only its owned version and launchers; preserves user data')
Path(os.environ.get('LUMEN_INSTALL_REPORT', 'installer_results.json')).write_text(json.dumps({'checks':len(results),'passed':results,'mode':'source installer, Linux, dependencies deliberately skipped','not_tested':['native window','pip dependency installation','Windows or macOS','frozen binaries','OS menu registration (--target skips it)']},indent=2))
print(json.dumps(results,ensure_ascii=False,indent=2))
