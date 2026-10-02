import json,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.diagnostics import output_diagnostics
from backend.extensions import registry_metadata,color_theme
from backend.server import Application
from backend.runtime_paths import find_tool

class PreviewR6(unittest.TestCase):
 def test_theme_inheritance_is_confined_and_child_colors_win(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);(root/'base.json').write_text('{"colors":{"editor.background":"#123456"},"tokenColors":[]}',encoding='utf-8')
   (root/'child.json').write_text('{"include":"base.json","colors":{"editor.background":"#abcdef"}}',encoding='utf-8')
   self.assertEqual(color_theme(root,'child.json')['colors']['editor.background'],'#abcdef')
   (root/'cycle.json').write_text('{"include":"cycle.json"}',encoding='utf-8')
   for path in ['cycle.json','../outside.json',None]:
    with self.assertRaises(ValueError):color_theme(root,path)
 def test_javac_diagnostics_have_source_line_caret_and_details(self):
  text='C:\\tmp\\Demo.java:7: error: cannot find symbol\n    System.out.println(missing);\n                       ^\n  symbol:   variable missing\n  location: class Demo\n1 error\n'
  items=output_diagnostics(text,'Demo.java');self.assertEqual(len(items),1);self.assertEqual(items[0]['startLineNumber'],7);self.assertEqual(items[0]['startColumn'],24);self.assertIn('variable missing',items[0]['message'])
  self.assertEqual(output_diagnostics(text,'Other.java'),[])
 def test_registry_prefers_host_architecture_not_arbitrary_latest(self):
  with patch('backend.extensions.target_platform',return_value='win32-x64'),patch('backend.extensions.download',return_value=json.dumps({'targetPlatform':'win32-x64'}).encode()) as fetch:
   registry_metadata(['meta','pyrefly'],'latest');self.assertIn('/win32-x64/latest',fetch.call_args.args[0])
 def test_registry_falls_back_only_to_universal(self):
  with patch('backend.extensions.target_platform',return_value='win32-x64'),patch('backend.extensions.download',side_effect=[b'{"error":"missing"}',b'{"targetPlatform":"universal"}']) as fetch:
   self.assertEqual(registry_metadata(['qa','theme'],'latest')['targetPlatform'],'universal');self.assertEqual(fetch.call_count,2)
 @unittest.skipUnless(find_tool('javac') and find_tool('java'),'JDK required')
 def test_lantern_java_unsaved_utf8_and_compiler_diagnostics(self):
  with tempfile.TemporaryDirectory() as temp:
   base=Path(temp);ws=base/'project';ws.mkdir();file=ws/'Hello.java';original='class Hello { public static void main(String[] a) { System.out.println("DISK"); }}';file.write_text(original,encoding='utf-8')
   app=Application(ROOT,ws,data_dir=base/'profile');app.workspace.trusted=True
   live=app.features.lantern
   def wait(predicate):
    end=time.monotonic()+30
    while time.monotonic()<end:
     state=live.snapshot()
     if predicate(state):return state
     time.sleep(.1)
    self.fail(str(live.snapshot()))
   try:
    live.start(app.workspace,'Hello.java',original.replace('DISK','áéíóú ñ ¿Qué tal? 😀'),1)
    state=wait(lambda s:s['status']=='watching');self.assertIn('áéíóú ñ ¿Qué tal? 😀',state['output']);self.assertEqual(file.read_text(encoding='utf-8'),original)
    live.buffer(app.workspace,'Hello.java','class Hello {\n public static void main(String[] a) {\n System.out.println(missing);\n }}',2)
    state=wait(lambda s:s['status']=='waiting');self.assertEqual(state['diagnostics'][0]['startLineNumber'],3);self.assertIn('cannot find symbol',state['error'])
    live.buffer(app.workspace,'Hello.java',original.replace('DISK','RECOVERED'),3);self.assertIn('RECOVERED',wait(lambda s:s['status']=='watching')['output'])
   finally:app.features.shutdown();app.runner.shutdown()

if __name__=='__main__':unittest.main()
