# Lumen Studio 0.5.2 · Preview R9

R9 amplía los servicios de extensiones conectados al editor y corrige la distribución de paneles, controles y avisos. Conserva Lantern, Forge, los estilos de trabajo y las ventanas independientes de R8.

## Extensiones y Open VSX

- La resolución de paquetes conserva el error HTTP 404 de una variante de plataforma y consulta la variante universal. Se comprobó con Maven for Java 0.45.3: la variante Windows no existe y la universal sí. La descarga, inspección e instalación reales completan el proceso.
- Las consultas de metadatos reintentan los fallos de transporte y los errores transitorios hasta tres veces. Los errores permanentes conservan su código HTTP y no se presentan como falta de conexión. Una revisión fallida ofrece Reintentar en un único diálogo.
- El catálogo muestra la cantidad de resultados y permite cargar más sin descartar los anteriores.
- Las correcciones rápidas y acciones de código consultan `provideCodeActions` y `resolveCodeAction`. Las ediciones de texto pueden afectar a varios búferes del proyecto, admiten deshacer y no guardan los archivos. Un resultado obsoleto se rechaza si cambió el documento de origen.
- Se conectan formato de selección, formato al escribir, resaltado de referencias, selección progresiva y colores con sus presentaciones. El formato al escribir depende de **Ajustes → Editor de texto → Formatear al escribir**; está desactivado inicialmente.
- `registerFileDecorationProvider` muestra insignias y descripciones reales en el Explorador. Los cambios de estado y la eliminación del proveedor se reflejan en el árbol. Los colores de las insignias se adaptan a la paleta de Lumen.
- `RelativePattern` acepta rutas, URI y carpetas de trabajo. Esto corrige la búsqueda de proyectos de Maven. El logger de telemetría de extensiones mantiene ambos tipos de telemetría desactivados y no invoca al emisor.
- Las APIs ausentes se registran incluso cuando el plugin captura el error. Al iniciar el motor, Lumen informa de esos servicios pendientes.

Estas implementaciones siguen el [contrato de referencia de VS Code](https://code.visualstudio.com/api/references/vscode-api) y el [registro Open VSX](https://github.com/eclipse-openvsx/openvsx/wiki/Registry-API).

## Interfaz

Melody tiene encabezado compacto, acciones desplazables y espacio reservado para contexto, permiso de edición, entrada y envío. El área de escritura cabe en las resoluciones verificadas de 1700×1000, 1366×768 y 1280×720.

Las pestañas de archivos conservan sus grupos de carpeta y reciben un indicador de selección más discreto. Terminal usa una línea de selección sin el bloque lila. Los paneles y tarjetas usan las superficies del tema activo, con bordes, tamaños y separaciones coherentes. El catálogo deja más espacio a los resultados.

Los avisos idénticos se agrupan, se pueden cerrar y aparecen arriba para liberar la entrada de Melody. El editor vacío está localizado y se sitúa debajo de las herramientas del estilo de trabajo, sin cubrirlas. Java y otros lenguajes tienen iconos diferenciados; los temas de iconos instalados siguen teniendo prioridad.

Se corrige una capa invisible de Monaco que interceptaba los clics en las correcciones rápidas. La lista conserva colores legibles y sus acciones se pueden seleccionar con el ratón.

Al abrir otro apartado, se cierran las sugerencias y pistas del editor. Los widgets de Monaco insertados fuera de su panel quedan ocultos mientras lo cubre la página de trabajo, para evitar que aparezcan sobre el catálogo o los ajustes.

Lantern Lens reintenta la publicación de su última captura cuando Windows mantiene el archivo abierto durante una lectura. Esto evita perder los últimos valores observados al terminar una revisión corta de Python.

## Verificación y límites

Las pruebas usan paquetes de extensión instalados en el host Node y el editor Monaco real. Comprueban correcciones en dos archivos sin escritura en disco, deshacer, formato por carácter, colores, decoraciones del árbol, revisión fallida, paginación y geometría de paneles en los tres temas. Las pruebas de R7 y R8 comprueban también Forge, terminal, arrastre, ventanas compartidas, estilos de trabajo y búferes independientes.

**La paridad total con VS Code sigue pendiente.** Maven llega a registrar 29 comandos y su vista de proyectos; su activación aún solicita `window.onDidCloseTerminal`. No se certifica que todos sus objetivos ni todos los plugins funcionen. Webviews, gestores de tareas, APIs de terminal y depuradores aportados por extensiones requieren más integración. No se sustituyen por implementaciones que anuncien un resultado falso.

Las acciones de código de R9 aplican ediciones de texto a archivos existentes dentro del proyecto. No implementan operaciones de creación, borrado o renombrado de archivos mediante `WorkspaceEdit`, ni ediciones fuera del proyecto. Las insignias no reproducen todas las opciones de propagación y color de VS Code. Los límites de R7 y R8 siguen vigentes.

## Distribución

| Sistema | Paquete de R9 |
|---|---|
| Windows 10/11 x64 | `LumenStudio-0.5.2-R9-Windows-Setup.exe` y portable `.zip` |
| Ubuntu 24.04 y derivados compatibles x64 | `LumenStudio-0.5.2-R9-Linux-amd64.deb` y portable `.tar.gz` |
| macOS | Preparado en la pipeline; pendiente de construcción y verificación en Mac |

Windows y Linux se construyen localmente y se verifican con la interfaz nativa del runtime empaquetado. Se publican con manifiestos, resultados de verificación y SHA-256. La pipeline de GitHub de R8 quedó bloqueada por facturación de la cuenta; no se presenta un `.dmg` sin verificar como una distribución disponible.

La actualización conserva el perfil local de preferencias, extensiones y proyectos. Node.js y las herramientas de cada lenguaje se preparan por separado. Se mantienen la licencia propietaria de preview y los requisitos de sistema descritos en [R8](PREVIEW_R8.md).
