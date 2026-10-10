# Zénit · x86-64 · sintaxis Intel para LLVM/GNU (no NASM).
# Suma 1 + 2 + ... + 10 y copia el resultado mediante la pila.
# Laboratorio ASM: no necesita main, ret ni llamadas al sistema.
.intel_syntax noprefix
.text
    xor rax, rax          # acumulador = 0
    mov rcx, 10           # contador = 10
suma:
    add rax, rcx
    dec rcx
    jnz suma
    push rax              # guardar 55 en la pila emulada
    pop rbx               # recuperar 55 en RBX
    mov rdx, rax
    imul rdx, rdx, 2      # RDX = 110
# Final: RAX = RBX = 55 (0x37), RCX = 0, RDX = 110 (0x6e).
