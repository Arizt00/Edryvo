# Lumen Studio 0.5.2 · Preview R8

Esta revisión conserva el IDE y Forge de R7 y añade distribución nativa por sistema. Los paquetes se construyen en Windows, Ubuntu y macOS.

## Arrastre y espacios de trabajo

Arrastra una pestaña o un archivo del Explorador a los bordes del editor: izquierda/derecha muestran dos archivos en columnas; arriba/abajo los colocan en filas. Soltar en el centro abre el archivo. El indicador de destino aparece durante el arrastre y los búferes sin guardar conservan sus cambios.

Arrastra una pestaña fuera del borde de Lumen para abrirla en otra ventana nativa, incluso en un monitor con coordenadas negativas. También puedes arrastrar los encabezados de Proyecto, Melody y Terminal fuera de la aplicación. Las ventanas comparten el servicio y los búferes del proyecto; cerrar un panel separado lo devuelve a la ventana principal. Escape cancela el arrastre. Cambiar simultáneamente el mismo archivo desde varias ventanas conserva los textos y avisa del conflicto.

Cada estilo tiene herramientas propias, seleccionables desde la barra del editor y persistentes entre sesiones:

- **Desarrollo general:** ejecución, depuración y Forge independiente.
- **Desarrollo web:** vista HTML/CSS desde el búfer sin guardar y sus recursos del proyecto, en un origen local aislado, con anchos de escritorio, tableta y móvil.
- **Ciencia de datos:** tabla CSV/TSV con separadores, filtros y estadísticas numéricas calculadas sobre la selección; ejecución integrada de scripts Python.
- **Diseño y UI:** paleta de colores del búfer, contraste de colores opacos, inserción explícita de variables CSS con deshacer y vista de componentes HTML/CSS.

Las herramientas se pueden ocultar sin cambiar de estilo. La bienvenida de un perfil nuevo no muestra Continuar ni archivos recientes hasta que hayas abierto documentos reales.

## Extensiones

R8 añade vistas de árbol que consultan el proveedor real y ejecutan los comandos de los nodos, ayuda de firmas, plegado, enlaces web y renombrado de símbolos con ediciones entre documentos. Las ediciones y tokens semánticos se transportan con su estructura real. Un plugin de prueba ejecutable comprueba la cadena instalación → activación → árbol → comando. Las vistas están disponibles desde **Vistas de extensiones** en la barra del editor.

La API de extensiones continúa siendo parcial: tareas, webviews y otros servicios específicos de VS Code todavía pueden impedir que un paquete funcione. Estas aportaciones no equivalen a paridad total. Consulta [Extensiones](EXTENSIONES.md).

## Distribución nativa

| Sistema | Paquete | Instalación |
|---|---|---|
| Windows 10/11 x64 | `LumenStudio-0.5.2-R8-Windows-Setup.exe` | Ejecutar el instalador gráfico. Necesita Edge WebView2. |
| Ubuntu 24.04 y derivados compatibles x64 | `LumenStudio-0.5.2-R8-Linux-amd64.deb` | Abrir con el gestor de paquetes, o `sudo apt install ./LumenStudio-0.5.2-R8-Linux-amd64.deb`. |
| Linux x64, instalación por usuario | `LumenStudio-0.5.2-R8-Linux-amd64.tar.gz` | Extraer y ejecutar `sh install.sh`. Necesita las bibliotecas de Qt/Chromium indicadas en el `.deb`; no necesita Python global. |
| macOS 14 o posterior, Apple Silicon | `LumenStudio-0.5.2-R8-macOS-arm64.dmg` | Abrir y arrastrar `Lumen Studio.app` a `Applications`. |
| macOS 15 o posterior, Intel | `LumenStudio-0.5.2-R8-macOS-x86_64.dmg` | Abrir y arrastrar `Lumen Studio.app` a `Applications`. |

Linux usa QtWebEngine/PySide6 incluidos en el paquete. macOS usa Cocoa/WebKit. Los paquetes incluyen el runtime Python de Lumen, la interfaz local y sus licencias. Los lenguajes, compiladores, servidores semánticos, Node.js y modelos de IA se preparan aparte. El instalador de Windows mantiene su selección de herramientas mediante WinGet; las instalaciones Linux/macOS no ofrecen ese asistente específico de Windows.

Los datos se conservan fuera de la aplicación: `%LOCALAPPDATA%/LumenStudio` en Windows, `~/.config/lumen-studio` (o `XDG_CONFIG_HOME`) en Linux y `~/Library/Application Support/LumenStudio` en macOS. Desinstalar el `.deb` o quitar la aplicación de macOS conserva los proyectos y preferencias.

Las actualizaciones seleccionan el paquete del sistema y la arquitectura actuales. Windows abre el `.exe`, macOS monta el `.dmg` y Linux abre el `.deb` con el gestor de escritorio; la sustitución de la aplicación requiere la acción del usuario. Se verifica SHA-256 antes de abrirlo.

Los ejecutables de Windows no tienen firma Authenticode y los de macOS tienen la firma ad hoc de construcción, sin Developer ID ni notarización. macOS puede requerir autorizar la apertura desde Privacidad y seguridad tras comprobar la procedencia y el SHA-256. No se solicita desactivar Gatekeeper.

La pipeline ejecuta pruebas de backend, crea los paquetes y comprueba el runtime empaquetado, la interfaz nativa, el puente de escritorio, Forge con un búfer sin guardar y la ventana independiente. Solo publica si todos los sistemas completan las verificaciones. Cada paquete conserva un manifiesto con el commit de origen, arquitectura, tamaño y SHA-256.

Los adaptadores de depuración mantienen los [límites de R7](PREVIEW_R7.md). Esta revisión no afirma soporte de todas las distribuciones Linux.

La primera ejecución de GitHub Actions de R8 no pudo arrancar: GitHub comunicó un bloqueo de la cuenta por facturación. Windows y Linux se construyen y verifican localmente. Los `.dmg` de macOS están preparados en la pipeline, pero permanecen pendientes de construcción y verificación en Mac; no se publican como si hubieran sido probados. El `.deb` declara la versión de glibc del entorno de construcción y no ofrece compatibilidad con Ubuntu 22.04.
