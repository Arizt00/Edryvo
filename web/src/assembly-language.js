/** LLVM/GNU suggestions follow the CPU selected in the laboratory. */
const x86=[['mov','rax, 1','Copia'],['lea','rax, [rbx]','Calcula una dirección'],['add','rax, rbx','Suma'],['sub','rax, rbx','Resta'],['xor','rax, rax','XOR; dos operandos iguales ponen a cero'],['cmp','rax, 0','Compara y actualiza flags'],['test','rax, rax','AND sin guardar el resultado'],['push','rax','Guarda en la pila'],['pop','rbx','Recupera de la pila'],['inc','rax','Incrementa'],['dec','rcx','Decrementa'],['imul','rax, rax, 2','Multiplica con signo'],['jmp','label','Salta'],['jnz','label','Salta si ZF = 0'],['jz','label','Salta si ZF = 1'],['call','label','Llama a una subrutina'],['ret','','Vuelve de una subrutina'],['nop','','No modifica registros']];
const arm=[['mov','r0, #1','Copia'],['add','r0, r1, #1','Suma'],['sub','r0, r1, #1','Resta'],['cmp','r0, #0','Compara'],['ldr','r0, [r1]','Carga memoria'],['str','r0, [r1]','Guarda memoria'],['b','label','Salta'],['bne','label','Salta si no son iguales'],['bl','label','Llama'],['bx','lr','Vuelve']];
const arm64=[['mov','x0, #1','Copia'],['add','x0, x1, #1','Suma'],['sub','x0, x1, #1','Resta'],['cmp','x0, #0','Compara'],['ldr','x0, [x1]','Carga memoria'],['str','x0, [x1]','Guarda memoria'],['b','label','Salta'],['b.ne','label','Salta si no son iguales'],['cbnz','x0, label','Salta si no es cero'],['bl','label','Llama'],['ret','','Vuelve']];
const riscv=[['addi','a0, zero, 1','Suma un inmediato'],['add','a0, a1, a2','Suma'],['sub','a0, a1, a2','Resta'],['mul','a0, a1, a2','Multiplica (extensión M)'],['ld','a0, 0(sp)','Carga 64 bits'],['sd','a0, 0(sp)','Guarda 64 bits'],['beq','a0, zero, label','Salta si son iguales'],['bne','a0, zero, label','Salta si no son iguales'],['jal','ra, label','Llama'],['ret','','Vuelve']];
const registers={x86:'eax ebx ecx edx esi edi esp ebp ax bx cx dx al bl cl dl',x86_64:'rax rbx rcx rdx rsi rdi rsp rbp r8 r9 r10 r11 r12 r13 r14 r15 eax ebx ecx edx',arm:Array.from({length:13},(_,i)=>'r'+i).join(' ')+' sp lr pc',arm64:Array.from({length:31},(_,i)=>'x'+i).join(' ')+' sp xzr',riscv64:'zero ra sp gp tp t0 t1 t2 t3 t4 t5 t6 s0 s1 s2 s3 s4 s5 s6 s7 s8 s9 s10 s11 a0 a1 a2 a3 a4 a5 a6 a7'};
export function assemblyCompletions(architecture='x86_64',source=''){
  const instructions={x86,x86_64:x86,arm,arm64,riscv64:riscv}[architecture]||x86;
  const list=instructions.map(([label,operands,detail])=>({label,detail:architecture+' · '+detail,kind:'instruction',insertText:label+(operands?' '+operands.split(', ').map((x,i)=>'${'+(i+1)+':'+(architecture==='x86'?x.replace(/r(ax|bx|cx)/g,'e$1'):x)+'}').join(', '):'')}));
  for(const label of (registers[architecture]||registers.x86_64).split(' '))list.push({label,detail:architecture+' · registro',kind:'register',insertText:label});
  for(const label of new Set([...source.matchAll(/^\s*([A-Za-z_.$][\w.$]*):/gm)].map(x=>x[1])))list.push({label,detail:'Etiqueta del búfer',kind:'label',insertText:label});
  for(const label of ['.text','.data','.bss','.global','.byte','.word','.long','.quad','.align'])list.push({label,detail:'Directiva LLVM/GNU',kind:'directive',insertText:label});
  return list;
}
export function assemblySyntax(){return {ignoreCase:true,tokenizer:{root:[
  [/\/\/.*$/,'comment'],[/;.*$/,'comment'],[/#(?:\s|[A-Za-z]).*$/,'comment'],
  [/^\s*[A-Za-z_.$][\w.$]*:/,'type.identifier'],[/\.[A-Za-z_]\w*/,'keyword'],
  [/\b(?:mov|lea|add|addi|sub|xor|cmp|test|push|pop|inc|dec|imul|mul|jmp|jnz|jz|je|jne|call|ret|nop|ldr|str|b|bne|bl|bx|cbnz|ld|sd|beq|jal)\b/,'keyword'],
  [/\b(?:[re]?(?:ax|bx|cx|dx|si|di|sp|bp)|[rxw]\d+|[ats]\d+|zero|ra|sp|lr|pc|gp|tp|xzr)\b/,'type'],
  [/"([^"\\]|\\.)*"/,'string'],[/\b(?:0x[\da-f]+|0b[01]+|\d+)\b/,'number']
]}};}
