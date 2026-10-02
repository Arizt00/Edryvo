# Preview R6 · alcance de la entrega

Esta revisión corrige fallos de R5 sin cambiar el formato de los proyectos.

## Editor y asistencia

El menú de Monaco se carga en español cuando corresponde, conserva los colores de Lumen dentro de su Shadow DOM y puede salir del borde del editor sin quedar debajo de Melody. Una petición explícita de escribir o modificar código en vivo abre la autorización de esa edición. Preguntar, explicar o analizar mantiene el archivo intacto. La edición autorizada conserva como destino el búfer original al cambiar de pestaña; no guarda automáticamente y permite deshacer.

## Lantern y Java

Los diagnósticos de javac incluyen archivo, línea, columna y detalles del símbolo. Un error de compilación aparece en el editor y en el monitor; ya no figura como cero diagnósticos. El monitor en línea se oculta al abrir Depuración y vuelve al editor al cerrar esa vista. Las operaciones iniciar, reiniciar, cambiar archivo y detener se serializan para descartar respuestas obsoletas. Compilador, programa Java, depurador Java y procesos Python reciben configuración UTF-8.

El ciclo Live sigue ejecutando el búfer sin guardarlo. La continuidad conserva checkpoints declarados por el programa, según el adaptador; no preserva automáticamente todos los punteros, recursos o memoria de un proceso. El contrato y los ejemplos de R5 siguen vigentes.

## Extensiones y temas

Open VSX se consulta primero para la arquitectura del equipo y después para la variante universal. No se instala una variante ARM/Linux como sustituto de Windows x64. «Reinstalar paquete» permite reparar una descarga de plataforma incorrecta.

Pyrefly incorpora un adaptador para ejecutar el servidor de lenguaje nativo que incluye el paquete: diagnósticos, autocompletado, hover y navegación mediante LSP. No ejecuta su interfaz exclusiva de VS Code. El host Node incorpora eventos reales `onWillSaveTextDocument`, ediciones asíncronas `waitUntil` con plazo limitado y `onDidSaveTextDocument` después de guardar.

Los temas instalados se pueden aplicar desde su tarjeta. Colorean el editor, paneles, campos, navegación y terminal; la selección persiste. Se resuelve la herencia `include` dentro del paquete y se rechazan ciclos o rutas externas. Elegir un tema integrado elimina los colores del tema externo. Las revisiones de paquetes agrupan los detalles técnicos para facilitar la lectura.

## Verificación y límites

La entrega se comprueba con pruebas Python/Node, navegador conectado al backend real y un paquete Pyrefly para Windows descargado de Open VSX. Las pruebas de edición de IA usan un transporte determinista para verificar permiso, destino, guardado y deshacer; no miden la calidad de un modelo externo.

La API de VS Code continúa siendo parcial. No se garantiza cualquier VSIX: webviews, aportaciones de tareas, Java Project Manager, Maven y adaptadores de depuración externos pueden necesitar APIs pendientes. La interfaz debe comunicar esa limitación. El límite de descargas de compiladores de 500 GB permanece, pero no se ha transferido un archivo de ese tamaño en las pruebas. Las capacidades previas se documentan en [R5](PREVIEW_R5.md).
