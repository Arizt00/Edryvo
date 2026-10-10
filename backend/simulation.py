"""Run the independent CPU emulator as a bounded external process."""
import json
from pathlib import Path
import subprocess
import sys
from .foundation import ARCHITECTURES, bundled_tool
from .runtime_paths import find_tool
from .terminals import child_environment

EXAMPLES={
 'x86':'.intel_syntax noprefix\n.text\nmov eax, 7\nadd eax, 5\nmov ebx, eax\n',
 'x86_64':'.intel_syntax noprefix\n.text\nmov rax, 7\nadd rax, 5\nmov rbx, rax\n',
 'arm':'.syntax unified\n.text\nmov r0, #7\nadd r0, r0, #5\nmov r1, r0\n',
 'arm64':'.text\nmov x0, #7\nadd x0, x0, #5\nmov x1, x0\n',
 'riscv64':'.text\naddi a0, zero, 7\naddi a0, a0, 5\naddi a1, a0, 0\n'}

class Simulation:
    def __init__(self,features):self.features=features
    def status(self):
        return {'architectures':[{'id':key,'label':{'x86':'x86 · 32 bits','x86_64':'x86-64','arm':'ARM · 32 bits','arm64':'ARM64','riscv64':'RISC-V · 64 bits'}[key],'example':EXAMPLES[key]} for key in ARCHITECTURES],
                'assembler':find_tool('clang'),'linker':find_tool('ld.lld'),'python':find_tool('python'),
                'description':'Registros, memoria, instrucciones y ejecución paso a paso en una CPU emulada.'}
    def run(self,ws,body):
        if not ws.trusted:raise PermissionError('Autoriza el proyecto antes de simular.')
        if body.get('architecture') not in ARCHITECTURES:raise ValueError('Arquitectura desconocida.')
        source=body.get('source')
        if not isinstance(source,str) or len(source.encode())>131072:raise ValueError('ASM admite hasta 128 KiB.')
        clang=find_tool('clang');linker=find_tool('ld.lld')
        if not clang or not linker:raise ValueError('Prepara LLVM con Clang y ld.lld en la base de Zénit.')
        python=find_tool('python') or (sys.executable if not getattr(sys,'frozen',False) else None)
        if not python:raise ValueError('Prepara el runtime independiente del laboratorio ASM.')
        worker=Path(__file__).resolve().parents[1]/'tools/asm_worker.py'
        result=subprocess.run([python,str(worker)],input=json.dumps({**body,'clang':clang,'linker':linker}),capture_output=True,text=True,
                              encoding='utf-8',timeout=32,env=child_environment(),creationflags=0x08000000 if sys.platform=='win32' else 0)
        if result.returncode:raise ValueError(result.stderr[-1500:] or 'El proceso de simulación terminó inesperadamente.')
        if len(result.stdout)>2_000_000:raise ValueError('Respuesta del simulador demasiado grande.')
        return json.loads(result.stdout)
