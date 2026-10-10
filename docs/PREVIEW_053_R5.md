# Zénit 0.5.3 Preview R5

El laboratorio reúne las herramientas detectadas, entornos Python por proyecto,
selección de estándares C/C++, Maven, Gradle, Bash, Docker y perfiles de máquinas.
Sus tarjetas, formularios y resultados se adaptan a Día, Oscuro y Bosque. Un SDK
local puede compartirse entre revisiones del programa, sin duplicar sus archivos
en cada actualización. Node también se detecta para los motores de extensiones.

Las extensiones Node y sus dependencias requeridas se activan en orden dentro
del mismo proceso. `getExtension().activate()` devuelve los exports reales,
incluidas funciones, y cada dependencia conserva su contexto y almacenamiento.
Sus comandos, proveedores, vistas y documentos virtuales se conectan al editor.
Los paquetes declarativos no necesitan inventar un motor ejecutable.

El plan de instalación recorre también dependencias ya instaladas para reparar
los paquetes transitivos que falten. Conserva versiones y estados desactivados,
rechaza ciclos y comprueba el grafo final antes de confirmar el índice. Si otra
ventana cambia una dependencia revisada, pide preparar el plan de nuevo.
Desactivar, actualizar o eliminar un paquete detiene los motores afectados.
La restauración fija las versiones y hashes autorizados; un cambio requiere
volver a revisar e iniciar el motor, sin ejecutar paquetes nuevos silenciosamente.

ASM usa LLVM, un proceso independiente de Unicorn y resultados calculados sobre
el búfer sin guardar. Incluye ejemplos para x86, x86-64, ARM32, ARM64 y RISC-V64,
registros, instrucciones y memoria. Paso reejecuta desde el estado inicial con
un límite de instrucciones creciente; no guarda un estado de CPU entre procesos.
Cambiar el archivo, el código o la arquitectura invalida los resultados.

Las máquinas Arch usan una imagen oficial, un disco propio de 16 GiB y una
consola serie sin ventanas gráficas. QEMU usa una conexión serie local para
conservar los comandos pegados y un canal QMP para apagar y cerrar el disco. La configuración NoCloud se anuncia por
SMBIOS y usa un usuario local. macOS y Windows 7 se conectan por SSH a sistemas
existentes; no se distribuyen imágenes de esos sistemas ni un motor Docker Desktop.

**El SDK completo todavía no forma parte del instalador público.** Se ha
preparado y comprobado un SDK Windows local con Python y paquetes de desarrollo,
LLVM, GCC/GDB, Java, Bash, nC, Node, Maven, Gradle, Docker CLI, QEMU e imagen Arch.
El constructor está en `tools/prepare_foundation.py`. La redistribución agregada
de sus herramientas e imágenes necesita preservar licencias y entregar las
fuentes correspondientes. El instalador público conserva la preparación opcional
de herramientas externas. No se anuncia que incluya todas las dependencias posibles
de cada lenguaje ni todas las implementaciones históricas de C/C++.

**La paridad completa con VS Code sigue pendiente.** Los exports se comparten
dentro de un grupo Node de dependencias, no entre todos los grupos del IDE.
Continúan pendientes TextMate, entradas browser, custom editors, restauración
completa de webviews y otras APIs específicas. Los hosts LSP nativos de Java y
Pyrefly mantienen su integración propia. Consulta [el estado de extensiones](EXTENSIONES.md).

El worker ASM tiene licencia GPL-2.0-or-later y se entrega con fuente y licencia;
el resto del código original conserva la [licencia propietaria](../LICENSE).

Lantern lee checkpoints con permisos de compartición de borrado en Windows;
la escritura atómica tolera bloqueos breves y el ejemplo nC reintenta reemplazos.
La suite backend completa pasó 252 pruebas: 247 correctas y 5 omitidas por
plataforma o herramientas ausentes. También pasaron 46 pruebas JavaScript y
los recorridos del catálogo, el laboratorio y las cinco arquitecturas ASM.
