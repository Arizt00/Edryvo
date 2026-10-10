# Extensiones · Zénit 0.5.3 Preview R5

Zénit consulta Open VSX y permite importar VSIX. Revisa rutas, enlaces, duplicados, tamaño expandido y manifiesto antes de instalar. La revisión presenta icono propio, versión, licencia declarada, bytes del archivo, bytes descomprimidos y dependencias. Las cifras iniciales corresponden al paquete revisado. Revisar dependencias prepara el grafo requerido y permite incluir los paquetes opcionales de extensionPack. El plan muestra cada paquete, su licencia, hash y tamaños, y el total que se instalará.

## Instalación y persistencia

La descarga remota es incremental a disco, con progreso, cancelación y reintento. Límites de inspección: VSIX de 4 GiB, total expandido de 8 GiB, archivo individual de 2 GiB y 20.000 entradas. Son distintos del gestor de compiladores de 500 GB. La exportación por el canal JSON antiguo conserva un límite de 48 MiB.

Se verifica longitud, espacio libre y SHA-256. El ticket dura diez minutos y se refiere a los mismos bytes revisados. El botón de instalación bloquea envíos duplicados mientras guarda el paquete e identifica los errores. Instalar no inicia automáticamente el motor ejecutable.

El índice se lee en UTF-8 y se actualiza con bloqueo entre procesos. Cada instalación conserva un recibo de recuperación. Un índice dañado puede reconstruirse desde paquetes completos; las extensiones desactivadas permanecen desactivadas. Las autorizaciones de motores se recuerdan por proyecto y solo se restauran en proyectos de confianza. Los errores de activación se conservan.

El plan admite hasta 32 paquetes, deduplica dependencias compartidas y rechaza ciclos. Conserva dependencias instaladas, incluida su desactivación. La instalación confirma el índice completo una sola vez; si falla esa escritura, restaura los paquetes temporales para reintentar. Cancelar no instala. La descarga renueva los tickets del plan durante el progreso. R5 activa conjuntamente los paquetes requeridos de cada grupo Node y conserva sus exports reales, incluidas funciones.

## Servicios conectados

| Área | Comportamiento implementado |
| --- | --- |
| Aportaciones | Asociaciones de lenguaje, gramáticas TextMate con inyecciones y estados multilínea, snippets, temas para editor e interfaz e iconos de archivos. Se resuelven textos de package.nls.json. |
| Documentos y archivos | Búferes sin guardar, TextDocument.save(), workspace.saveAll(), guardado atómico y conflictos. WorkspaceEdit permite ediciones, creación, borrado y renombrado con rollback. Las ediciones conservan deshacer en Monaco. |
| Lenguajes | Diagnósticos, completado, definición, referencias, inlays, hover, formato, firmas, plegado, enlaces, renombrado, acciones, colores, selección, resaltado y tokens semánticos según los proveedores registrados. |
| Árboles | registerTreeDataProvider y createTreeView consultan nodos reales. Los argumentos de comandos conservan identidad y métodos en el proceso de la extensión. |
| Terminales y tareas | Terminales reales o pseudoterminales de extensión, eventos de cierre, tareas de proveedores y tasks.json, procesos y códigos de salida. |
| Webviews | Paneles con HTML, recursos del paquete, mensajes bidireccionales y estado en la sesión. |
| Depuración | Adaptadores DAP de proceso, servidor, pipe o inline, con eventos y pila conectados a la depuración integrada. |
| Editores, R4 | activeTextEditor, visibleTextEditors y eventos de rango visible, selección, opciones y columna derivados de las vistas reales de Monaco, incluidos editores divididos. El último estado se entrega al activar un host. |
| QuickInput, R3 | createQuickPick, createInputBox, showQuickPick, showInputBox, cambios dinámicos, selección múltiple, separadores, botones Back y de elemento, validación asíncrona y cancelación. Los eventos y resultados llegan a la extensión original. |

QuickInput admite navegación con teclado, límites de tamaño, cierre con Esc y el tema activo. Un asistente visible no consume el timeout del comando mientras espera al usuario. Detener su motor elimina sus controles. Una validación anterior no reemplaza el resultado de una entrada posterior.

Pyrefly usa su servidor LSP nativo para Python. Language Support for Java de Red Hat usa un adaptador de Eclipse JDT LS. Su configuración y caché se guardan en el perfil de Zénit, sin modificar el paquete instalado. Estas integraciones no ejecutan todas las interfaces exclusivas de sus extensiones de VS Code.

## Alcance comprobado y límites

Las pruebas usan paquetes instalados en el host Node real y recorridos con el servidor Python y Edge. También se verificaron activación de nC Language y Material Icon Theme, Java VSIX de más de 54 MB y Maven for Java 0.45.3: 38 comandos, vista de proyectos y objetivos reales validate, compile, test y package en R1. Esto no certifica todos los objetivos ni plugins.

La paridad total sigue pendiente. No se ejecutan entradas browser de VS Code. R6 ejecuta gramáticas TextMate declarativas con Oniguruma local, sin activar el host Node. Los planes de dependencias requieren revisión explícita; los grupos Node comparten los exports reales de sus dependencias, incluidas funciones, dentro del mismo proceso; no se comparte un único host global entre todos los grupos. Los setters y operaciones avanzadas de TextEditor y registerCustomEditorProvider siguen pendientes. Markdown Preview Enhanced 0.8.39 llega ahora a solicitar registerCustomEditorProvider y no queda certificado como funcional. Persistencia/restauración de webviews, APIs específicas de Electron, opciones avanzadas de QuickInput, menús, contribuciones y propagación de decoraciones requieren más integración. Las APIs ausentes se identifican por su nombre, incluso si la extensión captura la excepción.

El proceso Node separado protege la respuesta de la interfaz; no es una sandbox de seguridad del equipo. El hash detecta cambios en el paquete y no certifica al publicador. El registro es [Open VSX](https://open-vsx.org/) y el contrato de referencia es la [API de VS Code](https://code.visualstudio.com/api/references/vscode-api).

Historial: [0.5.3 R6](PREVIEW_053_R6.md), [0.5.3 R5](PREVIEW_053_R5.md), [0.5.3 R4](PREVIEW_053_R4.md), [0.5.3 R3](PREVIEW_053_R3.md), [0.5.3 R2](PREVIEW_053_R2.md), [0.5.3 R1](PREVIEW_053_R1.md). Los límites históricos de R7–R9 describen aquellas versiones, no el estado actual de los servicios ya conectados.

En R5 el plan recorre también dependencias ya instaladas. Actualizar, desactivar o quitar un paquete detiene los grupos afectados. La restauración comprueba hashes, versiones y relaciones autorizadas antes de ejecutar de nuevo.
