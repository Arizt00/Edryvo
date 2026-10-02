"""Bounded values observed from execution, never re-evaluated expressions."""
import ast
import json
import os
from pathlib import Path
import time

def display(value, depth=0):
    kind = type(value)
    if kind in (bool, int, float, type(None)): return str(value)[:180]
    if kind is str: return repr(value[:160]) + ('…' if len(value) > 160 else '')
    if depth < 2 and kind in (list, tuple, set, frozenset):
        values = list(value)[:8]
        return ('(' if kind is tuple else '[') + ', '.join(display(v, depth+1) for v in values) + (', …' if len(value)>8 else '') + (')' if kind is tuple else ']')
    if depth < 2 and kind is dict:
        return '{' + ', '.join(display(k,depth+1)+': '+display(v,depth+1) for k,v in list(value.items())[:8]) + (', …' if len(value)>8 else '') + '}'
    # Avoid invoking user-defined __repr__, getters or iteration protocols.
    return '<' + kind.__name__ + '>'

class Lens:
    def __init__(self, source):
        self.source = str(source); self.path = os.environ.get('LUMEN_LANTERN_LENS')
        self.generation = os.environ.get('LUMEN_LANTERN_GENERATION', '')
        self.values = {}; self.last = 0; self.lines = {}
        tree = ast.parse(Path(source).read_text(encoding='utf-8-sig'), filename=self.source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                self.lines.setdefault(node.end_lineno, []).extend(n.id for target in targets for n in ast.walk(target) if isinstance(n, ast.Name))
        self.previous = {}
        hook = '__lumen_lens_capture_052'
        names = {n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
        while hook in names: hook += '_'
        self.hook = hook
        class Expressions(ast.NodeTransformer):
            def visit_Expr(self, node):
                # Keep docstrings and generator control flow intact.
                if isinstance(node.value, (ast.Constant, ast.Yield, ast.YieldFrom)): return node
                result = ast.Expr(value=ast.Call(func=ast.Name(id=hook,ctx=ast.Load()), args=[node.value,ast.Constant(node.lineno)], keywords=[]))
                return ast.copy_location(result, node)
        self.code = compile(ast.fix_missing_locations(Expressions().visit(tree)), self.source, 'exec')

    def record(self, line, value, label='', error=False):
        if not self.path: return
        self.values[int(line)] = {'line':int(line), 'value':str(value)[:500], 'label':str(label)[:80], 'error':error}
        if len(self.values)>200: self.values.pop(next(iter(self.values)))
        self.flush()

    def capture(self, value, line):
        if value is not None: self.record(line,display(value),'resultado')
        return value

    def trace(self, frame, event, arg):
        if frame.f_code.co_filename != self.source: return
        key = id(frame)
        previous = self.previous.get(key)
        if previous and event in ('line', 'return'):
            names = self.lines.get(previous, [])
            values = [name+' = '+display(frame.f_locals[name]) for name in names if name in frame.f_locals]
            if values: self.record(previous,' · '.join(values))
        if event == 'line': self.previous[key] = frame.f_lineno
        elif event == 'return':
            self.previous.pop(key,None)
            if frame.f_code.co_name!='<module>': self.record(frame.f_lineno,display(arg),'retorno')
        elif event == 'exception': self.record(frame.f_lineno,type(arg[1]).__name__+': '+str(arg[1])[:300],'error',True)

    def flush(self, force=False):
        if not self.path: return
        now = time.monotonic()
        if not force and now-self.last<.08: return
        self.last = now
        try:
            destination=Path(self.path);temporary=destination.with_suffix('.lens-tmp')
            temporary.write_text(json.dumps({'generation':self.generation,'values':list(self.values.values())},ensure_ascii=False),encoding='utf-8')
            os.replace(temporary,destination)
        except OSError: pass
