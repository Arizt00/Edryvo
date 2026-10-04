# Extensiones · Preview R8

Lumen consulta Open VSX y permite importar VSIX. El paquete se inspecciona antes de instalarlo: rutas, enlaces, duplicados, tamaño expandido y manifiesto. Las actualizaciones siguen el mismo proceso.

## Aportaciones

Asociaciones de lenguaje, snippets, temas para el editor y la interfaz e iconos se cargan como aportaciones declarativas. Un paquete con `main` compatible puede ejecutar su motor Node desde Extensiones, en un proyecto de confianza y con autorización.

El host implementa comandos, documentos, configuración persistente y eventos, `extensions.getExtension`, diagnósticos, autocompletado, navegación a definición, inlays, hover, formato, símbolos, CodeLens y tokens semánticos. Algunas clases y puntos de registro existen para integración progresiva: no implican que toda la API de VS Code esté implementada.

Las APIs ausentes producen un mensaje con su nombre. No hay compatibilidad universal con webviews, Electron, decoración de archivos, gestores de tareas ni cualquier adaptador DAP aportado por un plugin. Los depuradores integrados de Lumen se configuran por separado.

## Descarga e integridad

La descarga remota es incremental a disco, con progreso y cancelación; ya no pasa por el anterior límite de 48 MiB. Límites de inspección: VSIX de 4 GiB, total expandido de 8 GiB, archivo individual de 2 GiB y 20.000 entradas. No son límites del gestor de compiladores de 500 GB.

Se verifica longitud, espacio libre y SHA-256. El ticket dura diez minutos y se refiere a los mismos bytes revisados. Se resuelven los textos `%description%` con `package.nls.json`. La exportación por el canal JSON antiguo conserva un límite de 48 MiB; para paquetes mayores se debe usar la carpeta instalada.

El hash detecta cambios, pero no certifica al publicador. El proceso Node separado protege la respuesta de la interfaz, no aísla código malicioso del equipo. Solo activa motores en los que confíes.

## Estado comprobado

Las pruebas automatizadas usan paquetes reales de prueba instalados en el mismo host que los plugins. También se verificaron la activación de nC Language y Material Icon Theme, y una descarga real de Java VSIX de más de 54 MB. Maven for Java sigue requiriendo APIs no implementadas; se muestra esa limitación al activarlo.

El registro utilizado es [Open VSX](https://open-vsx.org/). El contrato de referencia es la [API de VS Code](https://code.visualstudio.com/api/references/vscode-api); Lumen implementa únicamente el subconjunto descrito.

R6 añade selección de variante por plataforma, reinstalación, herencia de temas y eventos antes/después del guardado. Pyrefly usa su servidor LSP nativo para Python, con diagnósticos, hover y autocompletado verificados en Windows. No se ejecuta su interfaz exclusiva de VS Code. Consulta [R6](PREVIEW_R6.md).


## Persistencia y servicios de R7

El índice de paquetes se lee en UTF-8, se actualiza con un bloqueo entre procesos y cada instalación conserva un recibo de recuperación. Un índice dañado puede reconstruirse desde paquetes completos; una extensión desactivada permanece desactivada. Las autorizaciones de motores se recuerdan por proyecto. Solo se restauran en proyectos de confianza y se registra cualquier fallo de activación.

`workspace.findFiles`, `workspace.fs` y los observadores de archivos tienen implementaciones reales. Las escrituras, borrados y renombrados generan eventos; los observadores se liberan al detener el motor.

Language Support for Java de Red Hat usa un adaptador nativo de Eclipse JDT LS. Su configuración y caché se escriben en el perfil de Lumen, sin modificar el paquete instalado. Se verificaron diagnósticos sobre texto sin guardar, autocompletado de la biblioteca estándar, hover y definición en Windows. Pyrefly mantiene su adaptador nativo. La capa LSP también transporta formato y tokens semánticos cuando el servidor los ofrece.

Esto amplía la compatibilidad, pero no proporciona paridad total con VS Code: webviews, APIs específicas de UI, contribuciones de tareas y otros servicios todavía pueden impedir la activación de un paquete. Los fallos muestran la API o herramienta que falta. [Alcance de R7](PREVIEW_R7.md).

## Editor y árboles de R8

`registerTreeDataProvider` y `createTreeView` consultan nodos reales del plugin. Las vistas se abren desde Vistas de extensiones en la barra del editor y permiten expandir, actualizar y ejecutar comandos. Los argumentos de los nodos conservan su identidad y sus métodos en el motor Node.

Los proveedores de ayuda de firmas, plegado, enlaces HTTP/HTTPS/correo y renombrado están conectados al editor Monaco. Las ediciones de renombrado se limitan al proyecto abierto. El transporte de `WorkspaceEdit` y `SemanticTokensBuilder` conserva los campos necesarios para aplicarlos. No todas las opciones de estas APIs ni los servicios de interfaz de VS Code están disponibles. [Alcance de R8](PREVIEW_R8.md).
