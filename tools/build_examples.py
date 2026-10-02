#!/usr/bin/env python3
"""Build two original, data-only VSIX examples without npm/vsce dependencies."""
import json
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PACKAGES={
 'lumen.starter-snippets':{
  'package.json':{'name':'starter-snippets','publisher':'lumen','version':'0.4.0','displayName':'Lumen · Starter Snippets','description':'Fragmentos originales de Python y CMake, sin código ejecutable de extensión.','license':'MIT','engines':{'vscode':'^1.80.0'},'contributes':{'snippets':[{'language':'python','path':'snippets/python.json'},{'language':'cmake','path':'snippets/cmake.json'}]},'lumen':{'commands':[{'id':'python-main','title':'Lumen: insertar punto de entrada Python','kind':'insertSnippet','body':'def main():\n    print("Hola desde Lumen")\n\nif __name__ == "__main__":\n    main()\n'}]}},
  'snippets/python.json':{'Punto de entrada Python':{'prefix':'lumen-main','body':['def main():','    ${1:pass}','','if __name__ == "__main__":','    main()']}},
  'snippets/cmake.json':{'Proyecto CMake mínimo':{'prefix':'lumen-cmake','body':['cmake_minimum_required(VERSION 3.20)','project(${1:MyProject} LANGUAGES CXX)','add_executable(${1:MyProject} main.cpp)','target_compile_features(${1:MyProject} PRIVATE cxx_std_20)']}}
 },
 'lumen.forest-syntax':{
  'package.json':{'name':'forest-syntax','publisher':'lumen','version':'0.4.0','displayName':'Lumen · Forest Syntax','description':'Tema de editor verde bosque. Contribución declarativa para Monaco.','license':'MIT','engines':{'vscode':'^1.80.0'},'contributes':{'themes':[{'label':'Lumen Forest Syntax','uiTheme':'vs-dark','path':'themes/forest.json'}]}},
  'themes/forest.json':{'name':'Lumen Forest Syntax','colors':{'editor.background':'#081D15','editor.foreground':'#DEECE3','editorLineNumber.foreground':'#748D7C','editorCursor.foreground':'#99E2B7'},'tokenColors':[{'scope':'keyword','settings':{'foreground':'#9ADDB4'}},{'scope':'string','settings':{'foreground':'#EFCB96'}},{'scope':'comment','settings':{'foreground':'#94AB9C','fontStyle':'italic'}}]}
 }
}
LICENSE='''MIT License\n\nCopyright (c) 2026 Lumen example contributors\n\nPermission is hereby granted, free of charge, to any person obtaining a copy\nof this software and associated documentation files (the "Software"), to deal\nin the Software without restriction, including without limitation the rights\nto use, copy, modify, merge, publish, distribute, sublicense, and/or sell\ncopies of the Software, and to permit persons to whom the Software is\nfurnished to do so, subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in\nall copies or substantial portions of the Software.\n\nTHE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\nIMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\nFITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\nAUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\nLIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\nOUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN\nTHE SOFTWARE.\n'''
def main():
    out=ROOT/'examples/extensions';out.mkdir(parents=True,exist_ok=True)
    for name,files in PACKAGES.items():
        source=out/name;source.mkdir(exist_ok=True)
        for relative,obj in files.items():
            p=source/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (source/'LICENSE').write_text(LICENSE)
        with zipfile.ZipFile(out/(name+'-0.4.0.vsix'),'w',zipfile.ZIP_DEFLATED) as z:
            for p in sorted(source.rglob('*')):
                if p.is_file():
                    entry=zipfile.ZipInfo('extension/'+p.relative_to(source).as_posix(),(2026,9,28,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;z.writestr(entry,p.read_bytes())
    print('Dos ejemplos declarativos creados. No proceden de un marketplace ni simulan extensiones de terceros.')
if __name__=='__main__':main()
