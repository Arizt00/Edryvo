/* System V AMD64 ABI. rdi=data, rsi=size, rax=newline count.
   Reads exactly size bytes. No out-of-bounds vector loads. */
.text
.globl lumen_count_newlines
.type lumen_count_newlines, @function
lumen_count_newlines:
    xor %eax, %eax
    test %rdi, %rdi
    je .Ldone
    test %rsi, %rsi
    je .Ldone
.Lscan:
    xor %edx, %edx
    cmpb $10, (%rdi)
    sete %dl
    add %rdx, %rax
    inc %rdi
    dec %rsi
    jne .Lscan
.Ldone:
    ret
.size lumen_count_newlines, .-lumen_count_newlines
.section .note.GNU-stack,"",@progbits
