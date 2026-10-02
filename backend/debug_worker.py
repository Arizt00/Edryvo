"""Separate debugger child process; stdout is a JSON event stream."""
from __future__ import annotations
import bdb
import io
import json
import os
from pathlib import Path
import sys
import traceback
import queue
import threading


def main(argv=None):
    args = argv or sys.argv[1:]
    file = Path(args[0]).resolve()
    points = json.loads(args[1])
    protocol = sys.stdout
    commands = sys.stdin
    control=queue.Queue();program_input=queue.Queue();pause=threading.Event();protocol_lock=threading.Lock()

    def emit(data):
        with protocol_lock:protocol.write(json.dumps(data, ensure_ascii=True) + '\n'); protocol.flush()

    def read_commands():
        for line in commands:
            if line.startswith('{'):
                try:program_input.put(str(json.loads(line)['input']))
                except (ValueError,KeyError):pass
            elif line.strip()=='pause':pause.set()
            else:control.put(line.strip())
        control.put('stop');program_input.put('')
    threading.Thread(target=read_commands,daemon=True).start()

    class Input(io.TextIOBase):
        def readline(self,size=-1):
            emit({'waitingInput':True});text=program_input.get();emit({'waitingInput':False});return text if size<0 else text[:size]
        def readable(self):return True
        def isatty(self):return False

    class Output(io.TextIOBase):
        def write(self, text):
            if text: emit({'event': 'output', 'text': text})
            return len(text)
        def flush(self): pass
        def isatty(self): return False

    class Debugger(bdb.Bdb):
        def set_continue(self):
            # Keep the trace installed so a later Pause works without breakpoints.
            self._set_stopinfo(self.botframe, None, -1)
        def dispatch_line(self,frame):
            if pause.is_set():pause.clear();self.set_step()
            return super().dispatch_line(frame)
        def user_line(self, frame):
            # Stop only inside the selected script; library frames stay out of the UI.
            if Path(frame.f_code.co_filename).resolve() != file:
                return
            stack = []
            cursor = frame
            while cursor and len(stack) < 25:
                if cursor.f_code.co_filename == str(file):
                    stack.append({'name': cursor.f_code.co_name, 'path': file.name, 'line': cursor.f_lineno})
                cursor = cursor.f_back
            variables = []
            for key, value in list(frame.f_locals.items())[:100]:
                if key.startswith('__'): continue
                try: display = repr(value)[:300]
                except Exception: display = '<no se puede representar>'
                variables.append({'name': key, 'type': type(value).__name__, 'value': display})
            emit({'status': 'paused', 'line': frame.f_lineno, 'path': file.name, 'stack': stack, 'variables': variables})
            command = control.get()
            if command == 'continue': self.set_continue()
            elif command == 'next': self.set_next(frame)
            elif command == 'step': self.set_step()
            elif command == 'out': self.set_return(frame)
            else: self.set_quit()

    sys.stdout = sys.stderr = Output()
    # The reader multiplexes debugger commands and program input independently.
    sys.stdin = Input()
    sys.argv = [str(file)]
    sys.path.insert(0, str(file.parent))
    debugger = Debugger()
    for point in points: debugger.set_break(str(file), point)
    namespace = {'__name__': '__main__', '__file__': str(file), '__builtins__': __builtins__}
    try:
        debugger.run(compile(file.read_bytes(), str(file), 'exec'), namespace, namespace)
        emit({'status': 'finished', 'variables': [], 'stack': []})
    except bdb.BdbQuit:
        emit({'status': 'stopped', 'variables': [], 'stack': []})
    except BaseException as exc:
        emit({'status': 'error', 'error': f'{type(exc).__name__}: {exc}', 'variables': [], 'stack': []})
        traceback.print_exc()
    finally:
        sys.stdout = protocol


if __name__ == '__main__':
    main()
