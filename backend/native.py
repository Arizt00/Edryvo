"""ctypes bridge to the optional C / C++ / x86-64 assembly core."""
from __future__ import annotations
import ctypes
from pathlib import Path


class NativeCore:
    def __init__(self, project: Path):
        self.lib = None
        self.name = "Python fallback"
        candidates = [
            project / "native/build/lib/liblumen_core.so",
            project / "native/build/lib/Release/lumen_core.dll",
            project / "native/build/lib/lumen_core.dll",
            project / "native/build/lib/liblumen_core.dylib",
        ]
        for candidate in candidates:
            if not candidate.is_file():
                continue
            try:
                lib = ctypes.CDLL(str(candidate))
                for fn in ("lumen_line_count", "lumen_ascii_words", "lumen_count_newlines"):
                    getattr(lib, fn).argtypes = [ctypes.c_char_p, ctypes.c_size_t]
                    getattr(lib, fn).restype = ctypes.c_size_t
                lib.lumen_fuzzy_score.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
                lib.lumen_fuzzy_score.restype = ctypes.c_int
                lib.lumen_backend_name.restype = ctypes.c_char_p
                self.name = lib.lumen_backend_name().decode("utf-8")
                self.lib = lib
                break
            except (OSError, AttributeError):
                continue

    def stats(self, text: str) -> dict:
        data = text.encode("utf-8")
        if self.lib:
            lines = self.lib.lumen_line_count(data, len(data))
            words = self.lib.lumen_ascii_words(data, len(data))
        else:
            lines = text.count("\n") + 1
            # Match the native byte/ASCII whitespace definition exactly.
            import re
            words = len(re.findall(rb"[^ \t\r\n\v\f]+", data))
        return {"bytes": len(data), "characters": len(text), "lines": lines, "words": words, "backend": self.name}

    def fuzzy(self, query: str, candidate: str) -> int:
        if self.lib and query.isascii() and candidate.isascii():
            return self.lib.lumen_fuzzy_score(query.encode(), candidate.encode())
        if not query:
            return 0
        q, c = query.lower(), candidate.lower()
        qi, score, previous = 0, 0, -2
        for ci, char in enumerate(c):
            if qi >= len(q):
                break
            if char != q[qi]:
                continue
            score += 10 + (8 if ci == previous + 1 else 0)
            score += 12 if ci == 0 or c[ci - 1] in "/_-" else 0
            previous, qi = ci, qi + 1
        return max(0, score - (len(c) - len(q))) if qi == len(q) else -1
