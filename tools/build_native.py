#!/usr/bin/env python3
"""Build the optional C/C++/ASM core with the locally installed CMake toolchain."""
from pathlib import Path
import shutil
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
if not shutil.which("cmake"):
    sys.exit("CMake no está instalado. Zénit funciona sin el módulo nativo. Instala CMake y un compilador C/C++ para compilarlo.")
try:
    subprocess.run(["cmake", "-S", str(ROOT / "native"), "-B", str(ROOT / "native/build"), "-DCMAKE_BUILD_TYPE=Release"], check=True)
    subprocess.run(["cmake", "--build", str(ROOT / "native/build"), "--config", "Release", "--parallel", "2"], check=True)
except subprocess.CalledProcessError as exc:
    sys.exit(exc.returncode)
print("\nMódulo nativo compilado. Reinicia Zénit para cargarlo.")
