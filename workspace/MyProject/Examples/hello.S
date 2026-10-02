/* Linux x86-64. Compiled by the Lumen runner with gcc. */
.section .rodata
message: .string "LUMEN | Assembly x86-64 task"
.text
.globl main
.type main, @function
main:
    push %rbp
    mov %rsp, %rbp
    lea message(%rip), %rdi
    call puts@PLT
    xor %eax, %eax
    pop %rbp
    ret
.section .note.GNU-stack,"",@progbits
