#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (c) 2026 L4CE (Arizt00).
"""Independent JSON-in/JSON-out CPU laboratory, distributed with its source.

Uses the real LLVM assembler/linker and Unicorn CPU emulation. It deliberately
does not emulate an operating system or execute guest syscalls on the host.
"""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile

def simulate(request):
    from elftools.elf.elffile import ELFFile
    import unicorn as u
    import capstone as c
    from unicorn import x86_const as x, arm_const as a, arm64_const as aa, riscv_const as r
    definitions={
        'x86':('i386-none-elf',u.UC_ARCH_X86,u.UC_MODE_32,c.CS_ARCH_X86,c.CS_MODE_32,x.UC_X86_REG_EIP,x.UC_X86_REG_ESP,
               {name:getattr(x,'UC_X86_REG_'+name.upper()) for name in ('eax','ebx','ecx','edx','esi','edi','esp','ebp')}),
        'x86_64':('x86_64-none-elf',u.UC_ARCH_X86,u.UC_MODE_64,c.CS_ARCH_X86,c.CS_MODE_64,x.UC_X86_REG_RIP,x.UC_X86_REG_RSP,
                  {name:getattr(x,'UC_X86_REG_'+name.upper()) for name in ('rax','rbx','rcx','rdx','rsi','rdi','rsp','rbp','r8','r9')}),
        'arm':('armv7-none-eabi',u.UC_ARCH_ARM,u.UC_MODE_ARM,c.CS_ARCH_ARM,c.CS_MODE_ARM,a.UC_ARM_REG_PC,a.UC_ARM_REG_SP,
               {**{'r'+str(i):getattr(a,'UC_ARM_REG_R'+str(i)) for i in range(13)},'sp':a.UC_ARM_REG_SP,'lr':a.UC_ARM_REG_LR}),
        'arm64':('aarch64-none-elf',u.UC_ARCH_ARM64,u.UC_MODE_ARM,c.CS_ARCH_ARM64,c.CS_MODE_ARM,aa.UC_ARM64_REG_PC,aa.UC_ARM64_REG_SP,
                 {**{'x'+str(i):getattr(aa,'UC_ARM64_REG_X'+str(i)) for i in range(16)},'sp':aa.UC_ARM64_REG_SP}),
        'riscv64':('riscv64-none-elf',u.UC_ARCH_RISCV,u.UC_MODE_RISCV64,c.CS_ARCH_RISCV,c.CS_MODE_RISCV64,r.UC_RISCV_REG_PC,r.UC_RISCV_REG_SP,
                   {name:getattr(r,'UC_RISCV_REG_'+name.upper()) for name in ('ra','sp','t0','t1','t2','s0','s1','a0','a1','a2')})}
    architecture=request.get('architecture')
    if architecture not in definitions:raise ValueError('Arquitectura desconocida.')
    source=request.get('source')
    if not isinstance(source,str) or len(source.encode())>131072:raise ValueError('ASM admite hasta 128 KiB.')
    steps=request.get('steps',100)
    if type(steps) is not int or not 1<=steps<=10000:raise ValueError('Usa entre 1 y 10.000 instrucciones.')
    triple,arch,mode,csarch,csmode,pc,sp,registers=definitions[architecture]
    with tempfile.TemporaryDirectory(prefix='zenit-asm-') as folder:
        folder=Path(folder);file=folder/'buffer.s';obj=folder/'buffer.o';image=folder/'buffer.elf'
        file.write_text(source,encoding='utf-8')
        flags=['-march=rv64im'] if architecture=='riscv64' else []
        for argv in ([request['clang'],'-target',triple,*flags,'-c',str(file),'-o',str(obj)],
                     [request['linker'],'--image-base=0x10000','-Ttext=0x100000','--entry=0x100000',str(obj),'-o',str(image)]):
            result=subprocess.run(argv,capture_output=True,timeout=15,creationflags=0x08000000 if sys.platform=='win32' else 0)
            if result.returncode:raise ValueError(result.stderr.decode('utf-8','replace').replace(str(folder),'<búfer>')[:12000])
        raw=image.read_bytes();elf=ELFFile(io.BytesIO(raw));text=elf.get_section_by_name('.text')
        if not text or not text.data():raise ValueError('No hay instrucciones en .text.')
        start=text['sh_addr'];end=start+text['sh_size'];cpu=u.Uc(arch,mode);pages=set()
        for segment in elf.iter_segments():
            if segment['p_type']!='PT_LOAD':continue
            lo=segment['p_vaddr'];length=segment['p_memsz']
            if length>4*1024*1024 or lo<0x10000 or lo+length>0x200000:raise ValueError('La imagen excede la memoria del laboratorio.')
            for page in range(lo&~4095,(lo+length+4095)&~4095,4096):
                if page not in pages:cpu.mem_map(page,4096);pages.add(page)
            cpu.mem_write(lo,segment.data())
        cpu.mem_map(0x200000,65536);cpu.reg_write(sp,0x20fff0)
        disassembler=c.Cs(csarch,csmode);instructions=[];trace=[];count=0
        for instruction in disassembler.disasm(text.data(),start):
            instructions.append({'address':hex(instruction.address),'bytes':instruction.bytes.hex(' '),'text':instruction.mnemonic+' '+instruction.op_str})
            if len(instructions)>=2000:break
        def hook(engine,address,size,_):
            nonlocal count
            count+=1
            if len(trace)<256:trace.append({'address':hex(address),'registers':{name:hex(engine.reg_read(reg)) for name,reg in registers.items()}})
        cpu.hook_add(u.UC_HOOK_CODE,hook)
        fault=''
        try:cpu.emu_start(start,end,timeout=1_000_000,count=steps)
        except u.UcError as exc:fault=str(exc)
        position=cpu.reg_read(pc)
        return {'architecture':architecture,'instructions':instructions,'trace':trace,'executed':count,'pc':hex(position),
                'registers':{name:hex(cpu.reg_read(reg)) for name,reg in registers.items()},'memory':cpu.mem_read(0x20ffc0,64).hex(' '),
                'status':'fault' if fault else 'complete' if position==end else 'paused','error':fault,
                'note':'CPU y memoria emuladas. Sin sistema operativo ni llamadas al sistema del anfitrión.'}

if __name__=='__main__':
    try:result=simulate(json.loads(sys.stdin.read(150000)))
    except Exception as exc:result={'status':'error','error':str(exc)}
    print(json.dumps(result,ensure_ascii=False))
