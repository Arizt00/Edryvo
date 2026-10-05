# Edryvo 0.5.3 · Preview R1

Edryvo es el nuevo nombre de Lumen Studio. Nace de «editor + vivo» y mantiene Lantern, Forge, Melody, los estilos de trabajo y las ventanas independientes. La actualización conserva las rutas locales y los identificadores de instalación anteriores para recuperar preferencias, proyectos y extensiones.

## Servicios reales de extensiones

El host Node puede solicitar servicios al IDE y recibir eventos mientras está ejecutando un comando de una extensión. Las llamadas no bloquean el canal de respuestas del motor.

- Terminales con procesos reales, entrada, salida, identificador de proceso y eventos de apertura y cierre. `env.shell` devuelve el ejecutable que usa la terminal predeterminada. Los pseudoterminales de extensiones tienen su propio ciclo de entrada y cierre; no se les asigna un proceso ficticio.
- Tareas de proveedores y de `.vscode/tasks.json`, incluyendo comentarios JSONC, comas finales y variantes por plataforma. Las ejecuciones de proceso, shell y pseudoterminal se conectan a terminales del IDE. El selector permite elegir una tarea y los eventos informan del proceso y su finalización.
- Webviews con HTML, recursos locales autorizados y mensajes en ambas direcciones. Se abren como pestañas y se ocultan al cambiar de archivo o apartado. El cierre elimina el panel y sus documentos temporales. Los scripts requieren `enableScripts` y se ejecutan en un iframe con sandbox.
- Adaptadores DAP de extensiones mediante proceso, socket TCP, socket local, named pipe de Windows o implementación inline. La interfaz integrada recibe pila, variables y pausas; no se abre una consola externa para representar la sesión.
- `WorkspaceEdit` admite crear, borrar y renombrar archivos o carpetas, además de editar texto en varios archivos y rutas absolutas externas de un proyecto de confianza. Un fallo revierte las operaciones de archivos de esa llamada antes de publicar los búferes.

Las ediciones de texto quedan sin guardar y tienen deshacer en Monaco. Los renombrados mantienen los documentos abiertos y el texto que todavía no se ha guardado. Las operaciones de archivos se reflejan en el Explorador. El guardado manual de documentos externos respeta UTF-8, BOM, saltos de línea y conflictos con cambios en disco.

Las traducciones `package.nls.json` y sus variantes de idioma se aplican también a comandos y otras aportaciones anidadas del manifiesto. Las decoraciones pueden propagarse desde archivos hacia carpetas visibles, con límites de recorrido explícitos.

## Maven comprobado

Se instaló y ejecutó el VSIX real **Maven for Java 0.45.3** en un perfil aislado. Registró **38 comandos**, seis proveedores y su vista de proyectos sin errores de API durante la activación.

Los objetivos `validate`, `compile`, `test` y `package` terminaron con `BUILD SUCCESS` desde la terminal integrada, usando Maven y JDK 21 instalados en el equipo. Se comprobaron la clase compilada y el JAR generado. El proyecto de prueba no contenía pruebas Java propias: el objetivo `test` verifica el recorrido de ejecución, no una batería de pruebas de ese proyecto. Esta comprobación no certifica `deploy`, todos los objetivos ni cualquier configuración de Maven.

## Interfaz y pruebas

Las pruebas del editor real comprueban mensajes de webviews, cierre, cambio de pestaña, ejecución de tareas, recursos del Explorador, texto sin guardar, deshacer y una sesión real de debugpy aportada por una extensión. Se revisa la geometría en 1700×1000, 1366×768 y 1280×720.

Las doce comprobaciones visuales heredadas de R9 pasan, incluyendo distribución de Melody, editor vacío, catálogo, decoraciones, correcciones entre archivos y superficies en los tres temas. El encabezado, los diálogos y la distribución pasan a mostrar Edryvo y 0.5.3 R1.

## Límites de esta preview

**No se declara paridad total con VS Code ni compatibilidad universal con plugins.** La implementación anterior amplía servicios concretos y comprobados. Las APIs ausentes siguen produciendo un error con su nombre.

- Las tareas aún no implementan toda la orquestación de dependencias y problem matchers de VS Code.
- Las vistas web aportadas por extensiones se muestran como paneles del editor; no reproducen todos los contenedores y el ciclo de restauración de VS Code.
- DAP no implementa todas las capacidades opcionales ni todos los eventos de todos los adaptadores.
- Las operaciones de creación, borrado y renombrado de `WorkspaceEdit` no tienen deshacer de recursos mediante Ctrl+Z. El texto sí tiene deshacer. Los renombrados que solo cambian mayúsculas en Windows requieren más integración.
- Las ediciones de texto usan posiciones UTF-16 y un máximo de 2 MB por búfer. Las decoraciones recorren hasta 10.000 rutas y no reproducen todas las prioridades, colores y propagaciones de VS Code.
- Configuración, documentos virtuales, gramáticas y APIs específicas de VS Code conservan límites descritos en las previews anteriores. No se anuncian servicios vacíos como compatibles.

Las pruebas dependientes de herramientas no disponibles se omiten explícitamente. Los límites de Lantern, autenticación de proveedores de IA y compatibilidad de las plataformas siguen descritos en [R7](PREVIEW_R7.md), [R8](PREVIEW_R8.md) y [R9](PREVIEW_R9.md).

## Distribución

La distribución usa el prefijo `Edryvo-0.5.3-R1`: instalador `.exe` y portable para Windows x64, `.deb` y portable para Linux x64 compatible con Ubuntu 24.04. Cada paquete publicado incluye manifiesto de construcción, SHA-256 y resultado de verificación del runtime empaquetado.

La pipeline prepara `.dmg` de macOS Intel y Apple Silicon. La publicación de macOS sigue pendiente de una construcción y verificación reales en Mac; no se presenta un paquete no verificado como disponible. El nombre nuevo mantiene el directorio de datos y la identidad de instalación antiguos para permitir actualizar desde Lumen Studio.

La primera migración desde Lumen Studio requiere descargar e instalar este paquete manualmente: el actualizador de las versiones anteriores solo reconoce el repositorio y los nombres antiguos. A partir de Edryvo 0.5.3 R1, el servicio de actualizaciones consulta `Arizt00/Edryvo` y reconoce los paquetes nuevos. La instalación conserva los datos existentes si no se elige eliminarlos en el desinstalador.

El repositorio es público bajo [licencia propietaria de preview](../LICENSE). Las dependencias conservan sus licencias y sus avisos de terceros.
