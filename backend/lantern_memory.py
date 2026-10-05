"""JSON checkpoint contract shared by Lantern revisions; never deserialize code."""
import json
import os
import runpy
import sys
import time
from pathlib import Path


def main(argv):
    source, destination = map(Path, argv[:2])
    try:
        state = json.loads(destination.read_text(encoding='utf-8')) if destination.stat().st_size<=1_000_000 else {}
        if not isinstance(state, dict): state = {}
    except (OSError, ValueError): state = {}
    try:
        from .lantern_lens import Lens
    except ImportError:
        from lantern_lens import Lens
    lens = Lens(source)
    previous = None
    last = 0

    def checkpoint(force=False):
        nonlocal previous, last
        now = time.monotonic()
        if not force and now-last < .05: return
        last = now
        try:
            text = json.dumps(state, ensure_ascii=False, allow_nan=False)
            if len(text.encode('utf-8')) > 1_000_000: return
            if text != previous:
                temp = destination.with_suffix('.tmp')
                temp.write_text(text, encoding='utf-8')
                for attempt in range(8 if force else 1):
                    try:
                        os.replace(temp, destination)
                        break
                    except PermissionError:
                        if not force or attempt==7:raise
                        time.sleep(.008)
                previous = text
        except (TypeError, ValueError, OSError): pass

    next_poll = 0
    def trace(frame, event, arg):
        nonlocal next_poll
        if frame.f_code.co_filename == str(source):
            lens.trace(frame,event,arg)
            checkpoint()
            now=time.monotonic()
            if now>=next_poll:
                next_poll=now+.05
                if destination.with_name(destination.name+'.reload').exists():
                    checkpoint(True)
                    raise SystemExit(0)
        return trace

    sys.argv = [str(source)]
    sys.path.insert(0, str(source.parent))
    sys.settrace(trace)
    try:
        scope={'__name__':'__main__','__file__':str(source),'__package__':None,'lantern_state':state,'lantern_checkpoint':lambda:checkpoint(True),lens.hook:lens.capture,'lantern_lens':lambda value,line: lens.capture(value,line)}
        exec(lens.code,scope,scope)
    finally:
        sys.settrace(None)
        checkpoint(True)
        lens.flush(True)


if __name__ == '__main__': main(sys.argv[1:])
