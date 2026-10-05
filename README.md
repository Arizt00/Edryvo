# Edryvo · 0.5.3 Preview R1

Edryvo es el nuevo nombre de Lumen Studio: un IDE de escritorio con editor Monaco, terminal integrada, depuración por lenguaje, Lantern Live y asistencia de IA. 0.5.3 R1 conecta terminales, tareas, webviews y adaptadores de depuración de extensiones a servicios reales del IDE, y amplía las ediciones entre archivos. Consulta [los cambios y límites de 0.5.3 R1](docs/PREVIEW_053_R1.md).

## Usar Edryvo

Instalador `.exe` para Windows 10/11 x64 (Edge WebView2), `.deb` y portable para Linux x64 compatible con Ubuntu 24.04. La pipeline prepara `.dmg` separados para macOS Apple Silicon e Intel; su publicación queda pendiente de construcción y verificación en Mac. Los paquetes incluyen el runtime Python del IDE; los compiladores y SDK de tus proyectos se preparan aparte. Los ejecutables de esta preview no tienen firma Authenticode ni notarización de Apple. Consulta [los paquetes de 0.5.3 R1](docs/PREVIEW_053_R1.md) y [las instrucciones de cada plataforma](docs/PREVIEW_R8.md).

El primer inicio permite elegir tema, idioma, distribución y perfil. Una instalación nueva comienza sin archivos recientes inventados. Los paneles principales usan superficies al 92 % en Día y al 94 % en Oscuro y Bosque, con colores de sintaxis integrados e iridiscencia animada configurable.

## Trabajo diario

- Pestañas agrupadas por carpeta, selector de archivos, menús contextuales, renombrado, eliminación recuperable y apertura en otra ventana.
- Proyecto, Asistente y Terminal pueden cerrarse, recuperarse, acoplarse, flotar dentro del área de trabajo o abrirse en ventanas nativas independientes en otro monitor.
- Dos archivos de código simultáneos con Ctrl+\. El editor separado comparte el búfer sin guardar y detecta cambios simultáneos.
- Arrastra archivos a los bordes para dividir el editor en filas o columnas; arrastra pestañas y encabezados de panel fuera de Edryvo para separarlos en otra ventana o monitor.
- Estilos persistentes con herramientas propias: desarrollo general, vista web sin guardar, exploración CSV/TSV y paleta/contraste para diseño.
- Forge: espacio de ejecución y depuración con contexto del archivo, herramientas detectadas, Python desde el búfer actual y C con GCC y GDB integrado.
- La última carpeta y las extensiones instaladas se conservan; los motores previamente autorizados se recuperan en proyectos de confianza.
- Actualizaciones de GitHub: comprobación al iniciar y cada seis horas, descarga automática configurable e instalación elegida por el usuario.
- Ruta superior ligada al archivo activo. Búsqueda de archivos, texto y comandos.
- Autoguardado configurable o guardado manual, sin notificaciones repetidas en cada autoguardado.
- Depuración integrada con pila, variables, puntos de interrupción y entrada al programa, según el adaptador.
- Lantern Live ejecuta el búfer sin guardarlo. Lens muestra valores reales junto al código. La memoria entre revisiones es cooperativa.
- La IA recibe el contexto actual; preguntar o explicar no reescribe el archivo. Una edición autorizada puede continuar en su archivo original mientras cambias de pestaña.
- Open VSX y VSIX locales, con aportaciones declarativas y motores Node autorizados. La compatibilidad con la API de VS Code es parcial.

Atajos: Ctrl+N, nuevo archivo; Ctrl+Shift+N, nueva ventana; Ctrl+S o Ctrl+O, guardar; Ctrl+Shift+S o Ctrl+Shift+O, guardar como; Ctrl+K, buscar; Ctrl+Alt+L, Lantern. Ctrl+O conserva la asignación solicitada para esta preview.

## Configuración local

Las preferencias, sesiones y extensiones se almacenan bajo `%LOCALAPPDATA%/LumenStudio`. Los proyectos externos permanecen donde los hayas creado. Emma se configura con su carpeta o endpoint local. Los clientes oficiales de IA que admiten cuentas usan sus flujos de autenticación y los derechos del plan correspondiente; una suscripción web no concede acceso universal a una API.

El desinstalador gráfico permite conservar los datos, borrar los datos locales o incluir también los proyectos internos, con una revisión previa. Los proyectos externos quedan fuera de esas opciones.

## Desarrollo

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-build.txt
.venv/Scripts/python tools/setup_assets.py
.venv/Scripts/python app.py --desktop
.venv/Scripts/python tools/build_desktop.py --require-assets --installer
```

Node.js se necesita para los motores de extensiones. Para depuración nativa prepara LLVM/LLDB y el SDK del lenguaje; NetCoreDbg y Delve pueden seleccionarse en Lenguajes y depuradores. Los binarios auxiliares de la distribución no se versionan en este repositorio. `config/runtime-local.json` es una personalización opcional de desarrollo, ignorada por Git y por el paquete final.

```powershell
python -m unittest discover -s tests -p "test_*.py"
npm run check
npm test
python tests/test_ui_r7.py --output qa-output
python tests/verify_desktop_r7.py --output qa-output
```

Las pruebas visuales requieren Playwright y Microsoft Edge. Las pruebas dependientes de herramientas pueden omitirse si no están instaladas.

## Documentación y licencia

[0.5.3 R1](docs/PREVIEW_053_R1.md) · [Lantern, cambios y límites](docs/PREVIEW_R7.md) · [Lenguajes](docs/LENGUAJES.md) · [Extensiones](docs/EXTENSIONES.md) · [Seguridad](docs/SEGURIDAD.md)

Repositorio público bajo [licencia propietaria](LICENSE), sin licencia de código abierto por el momento. Las dependencias mantienen sus propias licencias: [avisos de terceros](THIRD_PARTY_NOTICES.md).
