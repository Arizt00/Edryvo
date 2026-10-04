import tempfile,unittest,urllib.request
from pathlib import Path
from backend.preview import WebPreview
from backend.workspace import Workspace
from backend.native import NativeCore
from unittest.mock import patch,MagicMock
from backend.desktop import DesktopAPI

class PreviewR8(unittest.TestCase):
 def test_web_preview_serves_unsaved_utf8_buffers_without_writing_originals(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'index.html').write_text('DISK',encoding='utf-8');(root/'style.css').write_text('body{color:red}',encoding='utf-8')
   ws=Workspace(root,NativeCore(Path('.')));ws.trusted=True;preview=WebPreview()
   try:
    page=preview.start(ws,'index.html',[{'path':'index.html','content':'<h1>Hola ñ</h1>'},{'path':'style.css','content':'body{color:blue}'}]);client=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    self.assertEqual(client.open(page['url']).read().decode(),'<h1>Hola ñ</h1>');self.assertEqual(client.open(page['url'].replace('index.html','style.css')).read(),b'body{color:blue}');self.assertEqual((root/'index.html').read_text(),'DISK')
    with self.assertRaises(PermissionError):preview.start(ws,'index.html',[{'path':'../outside.html','content':'no'}])
   finally:preview.stop()
 def test_native_detach_positions_allow_secondary_monitors_and_share_application(self):
  api=DesktopAPI();api._url='http://127.0.0.1:1';api._application=MagicMock();api._window=MagicMock()
  with patch('webview.create_window') as create:
   api.detach_panel('editor','a.py',{'x':-1200,'y':300});args=create.call_args.kwargs
   self.assertEqual(args['x'],-1200);self.assertEqual(args['y'],300);self.assertIs(args['js_api']._application,api._application)

if __name__=='__main__':unittest.main()
