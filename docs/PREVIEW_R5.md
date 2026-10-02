# Preview R5 · alcance de la entrega

## Interfaz

Pestañas redondeadas agrupadas por carpeta, selección mediante menú, rutas dinámicas y barra de actividad contraíble. Paneles, desplegables, búsqueda, sugerencias de Monaco, perfil y depuración comparten temas Día, Oscuro y Bosque. Popups breves, estados de foco visibles y respeto al movimiento reducido. La esfera queda centrada en su espacio y el compositor de IA permanece accesible mientras el contenido superior se desplaza.

La revisión automatizada cubre 1050, 1366 y 1920 píxeles de ancho. Esto no equivale a certificar todos los DPI, lectores de pantalla o dispositivos.

Proyecto, Asistente y Terminal se pueden dejar flotantes con el botón de su cabecera o al arrastrarlos al centro del espacio. Se mueven por la cabecera y se redimensionan desde la esquina inferior; Escape cancela el arrastre. Los tres botones superiores permiten acoplarlos a izquierda, derecha o abajo. Cerrar un panel conserva su sesión. «Organizar y agrupar paneles» permite recuperarlo; Ctrl+J alterna la Terminal. Las posiciones se recuerdan y se reajustan para seguir visibles al reducir la ventana.

La selección de Terminal utiliza una línea fina sin recuadro lila. La burbuja de Melody es más pequeña y está separada de los controles del proveedor; todo el panel lateral del asistente queda 16 px por debajo de la fila del editor. La entrada de terminal se envía en orden, incluso al escribir rápidamente mientras el proceso responde.

## Lantern Live

Ctrl+Alt+L activa el archivo abierto sin navegar a Depuración. Al cambiar de pestaña, Lantern sigue el nuevo archivo. Tras un intervalo de estabilidad, analiza el búfer; una revisión incompleta espera y una válida sustituye a la anterior. No exige guardar y no sobrescribe el original.

Para compiladores crea una copia temporal del contexto admitido. El snapshot limita cantidad y tamaño de archivos y excluye cachés y dependencias voluminosas. Proyectos complejos, imports externos, sistemas de build personalizados o assets fuera del proyecto requieren configuración específica; no se promete equivalencia con todos los builds de producción.

## Lantern Lens

Los valores vienen de la ejecución, no de predicciones. Python instrumenta asignaciones, retornos y errores; JavaScript dispone de consola e instrumentación explícita; C/C++ usan el SDK de Lens. Las anotaciones no se escriben en el archivo y se retiran al desactivar Lantern. Los restantes adaptadores ofrecen salida y diagnósticos: no todos tienen instrumentación automática de expresiones.

## Memoria cooperativa

Python dispone de `lantern_state`; JavaScript de `lanternState`. El SDK C/C++ serializa estado declarado; nC usa su protocolo de checkpoint. Los ejemplos de `examples/lantern` y `debugger-support/lantern` muestran la colaboración necesaria.

La revisión siguiente valida el checkpoint y restaura los campos compatibles. Hay versión de esquema, migración explícita y verificación de integridad. Al cancelar se concede un intervalo para guardar el checkpoint antes de terminar el proceso.

Esto conserva estado de aplicación declarado. No conserva automáticamente direcciones de memoria, punteros, recursos del SO, pilas de hilos o cualquier heap de un ejecutable arbitrario. Un cambio incompatible de esquema requiere migración o reinicio del estado.

## IA y edición

Una pregunta normal es de lectura. Para modificar hay que usar «Editar archivo…» y autorizar esa petición. El trabajo queda ligado al modelo del archivo original; cambiar de pestaña no lo cancela. Los saltos CRLF se normalizan para no confundir las propias actualizaciones de la IA con cambios del usuario.

Si editas el archivo objetivo durante la generación, Lumen detiene esa edición y conserva tus cambios. Cerrar el modelo también cancela la tarea. La aplicación al búfer es visible y se puede deshacer; guardar es una operación separada. Los fallos o respuestas incompletas se presentan como tales.

## Instalación y retirada

El instalador consulta los tamaños de descarga publicados, la arquitectura y las dependencias disponibles. Un bootstrapper no permite conocer de antemano todos los GB que descargará después: ese tamaño se indica como pendiente, no como un total inventado. Incluye opciones ASM/NASM y herramientas Android.

El gestor de compiladores acepta hasta 500.000.000.000 bytes por archivo, escribe a disco y admite pausa/reanudación cuando el servidor la permite. Ese límite es una capacidad implementada; las pruebas no transfieren 500 GB.

El desinstalador gráfico muestra qué se va a eliminar. Conservar datos es la opción inicial. El borrado de proyectos internos exige selección adicional; no alcanza proyectos externos.

## Extensiones y límites de preview

Los motores Node funcionan con permisos del usuario tras autorización. Se probaron comandos y proveedores de autocompletado, definición, inlays y diagnósticos, además de eventos de configuración, registro de extensiones y tokens semánticos.

La API de VS Code todavía es un subconjunto. Extensiones con webviews, APIs Electron, decoraciones de explorador, servidores complejos o dependencias entre hosts pueden requerir funciones pendientes. Maven for Java, por ejemplo, solicita `window.registerFileDecorationProvider`, aún no implementada. Instalar el VSIX no prueba que todas sus funciones estén operativas.

Los SDK no incluyen necesariamente un servidor de lenguaje. Las funciones semánticas avanzadas dependen del LSP/extensión disponible; coloreado y snippets básicos no equivalen a análisis completo del compilador. La depuración de hardware remoto, drivers o kernel necesita adaptadores y permisos específicos y no está validada en esta entrega.
