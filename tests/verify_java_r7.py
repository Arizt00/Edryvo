"""Optional real JDT LS probe. Uses an installed package read-only and temporary data."""
import argparse,json,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.extension_lsp import JavaLanguageHost
from backend.workspace import Workspace

def main():
    p=argparse.ArgumentParser();p.add_argument('extension',type=Path);args=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='lumen-jdt-r7-') as t:
        base=Path(t);project=base/'project';project.mkdir();workspace=Workspace(project,None)
        text='class Demo {\n static int value=42;\n public static void main(String[] args) {\n  int bad="wrong";\n  System.out.println(value);\n }\n}\n'
        (project/'Demo.java').write_text(text,encoding='utf-8');host=JavaLanguageHost(args.extension,workspace,base/'storage')
        try:
            print('engine',host.capabilities['engine'],flush=True)
            def call(kind,code=text,**kw):return host.request({'method':'provide','kind':kind,'document':{'path':'Demo.java','text':code,'language':'java'},**kw})
            start=time.monotonic();diagnostics=[]
            while time.monotonic()-start<60:
                diagnostics=call('diagnostics')['items']
                if any(d['severity']=='error' for d in diagnostics):break
                time.sleep(.3)
            assert any(d['line']==4 and d['severity']=='error' for d in diagnostics),diagnostics
            print('PASS Java type-error diagnostic at unsaved source line',flush=True)
            fixed=text.replace('int bad="wrong"','int bad=7');completions=call('completion',fixed.replace('System.out.println(value);','System.out.pri'),position={'line':4,'character':16})['items']
            assert any('print' in x['label'] for x in completions),completions
            print('PASS Java standard-library completion',len(completions),flush=True)
            definition=call('definition',fixed,position={'line':4,'character':23})['items'];assert definition,definition
            print('PASS Java go-to-definition',json.dumps(definition),flush=True)
            hover=call('hover',fixed,position={'line':4,'character':23})['items'];assert hover,hover
            print('PASS Java hover',flush=True)
        finally:host.close()
if __name__=='__main__':main()
