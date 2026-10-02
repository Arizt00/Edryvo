"""Syntax diagnostics without evaluating the editor buffer; compiler output adapters."""
from __future__ import annotations
import ast
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from .terminals import child_environment


def marker(message, line=1, column=1, severity=8, source='Lumen'):
    return {'message':str(message)[:3000], 'startLineNumber':max(1,int(line or 1)),
            'startColumn':max(1,int(column or 1)), 'severity':severity,'source':source}


def output_diagnostics(text, path):
    """Normalize compiler locations without turning log text into commands."""
    result=[]
    lines=text.splitlines()
    for index,line in enumerate(lines):
        # javac omits a column and places a caret on the following source line.
        java=re.match(r'(.+\.java):(\d+):\s*(error|warning):\s*(.*)',line)
        if java:
            file,ln,level,msg=java.groups()
            if Path(file.strip()).name.casefold()==Path(path).name.casefold():
                caret=lines[index+2] if index+2<len(lines) else ''
                column=caret.index('^')+1 if '^' in caret else 1
                details=[]
                for detail in lines[index+3:index+6]:
                    if not re.match(r'\s+(symbol|location):',detail):break
                    details.append(detail.strip())
                result.append(marker(msg+(' · '+' · '.join(details) if details else ''),ln,column,4 if level=='warning' else 8,'Java'))
            continue
        match=re.search(r'(.+?)\((\d+),(\d+)\):\s*(error|warning)\s*([^:]*):\s*(.*)',line)
        if not match:match=re.search(r'(.+?):(\d+):(\d+):\s*(fatal error|error|warning)(?:\s+([^:]+))?:\s*(.*)',line)
        if match:
            file,ln,col,level,code,msg=match.groups()
            if Path(file.strip()).name.lower()!=Path(path).name.lower():continue
            item=marker((code+' ' if code else '')+msg,ln,col,4 if level=='warning' else 8,'Compilador')
            result.append(item)
    # Node and Python separate the location and exception message.
    if not result:
        loc=re.search(r'(?:File "[^"]+", line |[^\n]+:)(\d+)(?::(\d+))?\s*\n',text)
        error=re.search(r'(?:SyntaxError|IndentationError|TabError|error(?:\[\w+\])?):\s*([^\n]+)',text)
        if loc and error:result.append(marker(error.group(0),loc[1],loc[2] or 1))
    return result[:200]


def inspect_buffer(ws, runtimes, path, content):
    ws.resolve(path)
    if not isinstance(content,str) or len(content)>250_000:raise ValueError('El diagnóstico admite hasta 250 000 caracteres.')
    suffix=Path(path).suffix.lower();items=[];source='syntax'
    try:
        if suffix in ('.py','.pyw'):ast.parse(content,filename=path)
        elif suffix in ('.json',):json.loads(content)
        elif suffix in ('.js','.mjs','.cjs','.ts') and ws.trusted:
            node=runtimes.executable('node')
            with tempfile.TemporaryDirectory(prefix='lumen-syntax-') as folder:
                file=Path(folder)/('buffer'+suffix);file.write_text(content,encoding='utf-8')
                result=subprocess.run([node,'--check',str(file)],capture_output=True,text=True,encoding='utf-8',errors='replace',
                    timeout=4,env=child_environment(),creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                items=output_diagnostics(result.stderr,path)
        else:source='language-server-or-build'
    except SyntaxError as exc:items=[marker(exc.msg,exc.lineno,exc.offset,source='Python')]
    except json.JSONDecodeError as exc:items=[marker(exc.msg,exc.lineno,exc.colno,source='JSON')]
    except (ValueError,OSError,subprocess.TimeoutExpired):source='language-server-or-build'
    return {'path':path,'diagnostics':items,'source':source}
