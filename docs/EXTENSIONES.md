# Extensiones · Preview R6

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
