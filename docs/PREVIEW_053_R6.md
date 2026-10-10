# Zénit 0.5.3 Preview R6

Las gramáticas TextMate de extensiones activas se ejecutan en Monaco con
vscode-textmate 9.2.0 y Oniguruma 2.0.1, incluidos localmente con WASM.
Se leen JSON/JSONC y plist, includes entre gramáticas instaladas, inyecciones,
estados multilínea y mapas de lenguajes embebidos. Los selectores de tokenColors
pueden usar contextos y estilos de fuente; el mapa de colores codificados se
sincroniza con el tema de Monaco. Desactivar una gramática restaura el proveedor
integrado disponible. No es necesario ejecutar el código Node de una extensión
para aplicar su gramática.

Los recursos se resuelven dentro del paquete instalado. Cada gramática admite
3 MB y el conjunto activo 16 MB; los errores de lectura o carga se muestran en
las aportaciones. Las líneas de más de 20.000 caracteres omiten estas expresiones
regulares. La tokenización usa un presupuesto de 20 ms entre coincidencias,
no una garantía de interrupción de cualquier expresión regular individual.

ASM ofrece sugerencias de instrucciones, operandos, registros y etiquetas del
búfer correspondientes a x86, x86-64, ARM32, ARM64 o RISC-V64. Son sugerencias
locales para el dialecto LLVM/GNU; no son un servicio semántico ni una lista de
todas las extensiones posibles de cada ISA. Los comentarios, números hexadecimales,
registros y directivas se distinguen en el editor.

El laboratorio mejora la distribución de controles y resultados, permite mostrar
registros en decimal sin perder precisión y resalta cambios entre ejecuciones.
Incluye el ejemplo [x86-64: bucle y pila](../examples/asm/x86_64_sum.s): suma 1…10
en 36 instrucciones, RAX = RBX = 55 y RDX = 110. Paso sigue reejecutando desde el
estado inicial; cambiar el búfer invalida los resultados. La CPU emulada no tiene
un sistema operativo ni ejecuta llamadas al sistema del anfitrión.

La cabecera del explorador separa sus acciones en una segunda fila cuando el
panel es estrecho, para mantener visible el nombre completo. Los colores siguen
el tema elegido y las animaciones conservan la preferencia de movimiento reducido.

La **paridad total con VS Code sigue pendiente**. Consulta el alcance actual de
[extensiones](EXTENSIONES.md). Custom editors, restauración de webviews, entradas
browser, un host global único y otras API avanzadas siguen requiriendo integración;
esta revisión no certifica todos los plugins.

Distribuciones: Windows EXE/ZIP y Linux DEB/tar.gz. Los paquetes públicos contienen
el runtime del IDE, las bibliotecas de resaltado y el ejemplo; los compiladores y
el SDK agregado se preparan aparte. La publicación macOS continúa pendiente de
construcción y verificación en Mac. Se conserva la [licencia propietaria](../LICENSE)
del IDE y las licencias independientes de los componentes de terceros.
