# Preview R7 · alcance de la entrega

R7 incorpora Forge, recuperación de la carpeta de trabajo, extensiones persistentes, ventanas nativas independientes, dos editores simultáneos y actualizaciones desde GitHub. Mantiene el formato de proyectos y las capacidades de [R6](PREVIEW_R6.md).

## Forge · ejecución y depuración

El botón Forge de la cabecera abre una ventana propia, independiente de la ventana del IDE y que puedes mover a otra pantalla. Sigue el archivo enfocado y los cambios sin guardar del editor principal. «Forge: abrir en la terminal integrada» permite trabajar dentro de Lumen con una consola inicialmente ampliada. «Integrar en Lumen» devuelve las sesiones de Forge a la terminal sin finalizar sus procesos.

Muestra el archivo enfocado, los cambios sin guardar, el estado de la ejecución y las rutas reales de Python, GCC y GDB al pasar el cursor por sus indicadores. Las acciones se habilitan según el lenguaje y las herramientas disponibles. Puedes volver a detectar las herramientas después de instalarlas. La interfaz se adapta a paneles estrechos, temas instalados y movimiento reducido.

Python ejecuta el texto actual, aunque no esté guardado, con salida y entrada en una terminal PTY integrada. El directorio de trabajo es el proyecto y los imports locales pueden resolverse desde la carpeta original del archivo. La distribución Windows incluye un ejecutable auxiliar de consola que comparte el runtime Python empaquetado y se aloja en la terminal de Lumen.

La acción C compila el búfer temporal con GCC usando `-g3 -O0 -Wall -Wextra -fno-omit-frame-pointer`, mantiene los includes locales y abre GDB detenido en `main`. Puedes escribir `next`, `step`, `print variable`, `continue` y `quit`. Los errores de compilación aparecen en la salida de tareas. No se abre una ventana CMD. GCC y GDB deben estar instalados; se detectan PATH y las ubicaciones comunes de MSYS2/MinGW. Es una acción para un archivo C; proyectos con varios módulos requieren sus tareas de compilación.

La paleta ofrece acciones para abrir Forge en otra ventana o en la terminal, ocultar sus controles, ejecutar Python desde el búfer y compilar C con GDB integrado. Cambiar de archivo actualiza el contexto y las acciones; una ejecución ya iniciada conserva su archivo objetivo. Desactivar los controles de Forge deja las sesiones accesibles en la terminal.

Las ejecuciones requieren un proyecto de confianza. El fichero original no se modifica. Los temporales se eliminan cuando termina la sesión de Lumen. Las terminales reciben un entorno completo sin las claves de proveedores de IA que filtra Lumen, y los argumentos con espacios se transmiten como lista para evitar un doble entrecomillado en ConPTY.

## Carpeta y extensiones

La selección de carpeta se guarda en el perfil local y se recupera en el siguiente inicio, aunque cambie el puerto. Una carpeta explícita en la línea de comandos tiene prioridad. La opción de reabrir la última carpeta puede desactivarse en General. Si ya no existe, Lumen vuelve a su carpeta inicial.

Las extensiones mantienen un índice UTF-8 y recibos individuales; el registro se actualiza con un bloqueo entre procesos. Los paquetes completos pueden recuperar un índice dañado. Se conservan tanto la instalación como el estado desactivado y la autorización del motor por proyecto. Un motor autorizado se restaura solo en un proyecto de confianza.

El host amplía los servicios reales de archivos, búsqueda y observadores. Red Hat Java puede usar su servidor Eclipse JDT LS a través de un adaptador nativo para diagnósticos, autocompletado, hover, definición y otros servicios LSP disponibles. Las cachés se guardan fuera del paquete. No se ejecuta toda su interfaz de VS Code.

## Dos archivos y escritorio

Ctrl+\ o el botón Dividir editor permite trabajar con dos archivos a la vez. Cada panel mantiene su modelo, cursor y guardado; los atajos actúan sobre el editor enfocado. Las acciones contextuales de Lumen están disponibles en ambos.

La flecha hacia el escritorio abre Proyecto, Asistente, Terminal o el archivo activo en una ventana nativa independiente. Puede moverse fuera de la aplicación o a otra pantalla. Las ventanas comparten el backend: cerrar una terminal separada no mata su proceso. Al cerrar el panel nativo, vuelve a estar disponible en la ventana principal.

El editor separado sincroniza el texto sin guardar y el estado de guardado. Si dos ventanas editan una misma revisión a la vez, se conserva el búfer local y se avisa del conflicto. No se intenta una fusión silenciosa. Si la carpeta cambia en la ventana principal, el texto de las ventanas separadas permanece visible y se bloquea el guardado sobre el proyecto nuevo. El proyecto separado puede abrir archivos en la ventana principal; el asistente separado sigue el contexto del editor principal.

## Actualizaciones y apariencia

Lumen comprueba las releases públicas de Arizt00/LumenStudio al iniciar y cada seis horas. Solo considera versiones posteriores y un instalador Windows con URL del repositorio y digest SHA-256 de GitHub. La descarga automática se puede desactivar; «Lumen: comprobar actualizaciones de GitHub» permite revisar el progreso y descargar manualmente. La instalación se inicia cuando el usuario elige y vuelve a comprobar el hash. No se cierra el editor para descartar trabajo sin guardar.

Este mecanismo empieza en R7. Las distribuciones anteriores necesitan actualizarse una vez manualmente para incorporarlo. Los ejecutables siguen sin firma Authenticode.

Día usa superficies principales al 92 %; Oscuro y Bosque al 94 %. Los temas integrados ofrecen colores diferenciados de palabras clave, tipos, números, cadenas, funciones y comentarios. Los temas de extensiones siguen coloreando toda la interfaz.

## Verificación y límites

Las pruebas cubren persistencia, recuperación de paquetes, motores autorizados, conflictos de búfer, Python y GCC/GDB reales, descarga verificada y control de instalación. Se comprueban dos editores y ventanas separadas mediante navegador con backend real y WebView2 nativo en un perfil aislado. Se prueba también la distribución Windows empaquetada.

La compatibilidad de VS Code sigue siendo parcial. No se garantiza cualquier plugin ni paridad total: webviews, APIs específicas de UI, contribuciones de tareas y otros servicios todavía requieren implementación. Los servicios de lenguaje dependen del servidor y SDK disponibles. El adaptador Java se verificó con el paquete instalado de Red Hat; eso no acredita todas las funciones de su extensión ni otros plugins Java.

Lantern mantiene ejecución de búfer sin guardado y continuidad cooperativa. No conserva automáticamente cualquier heap, puntero o recurso entre ejecutables. Los SDK no se instalan con esta revisión de forma automática. Los límites y contratos de R5/R6 siguen vigentes, incluido el límite de descargas de compiladores de 500 GB, sin una transferencia de ese tamaño en las pruebas.
