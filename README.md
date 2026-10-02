# Lumen Studio · 0.5.2 Preview R5

Lumen es un IDE de escritorio con editor Monaco, terminal integrada, depuración por lenguaje, Lantern Live y asistencia de IA. Está en desarrollo: el alcance real y las limitaciones de esta entrega se detallan en [Preview R5](docs/PREVIEW_R5.md).

## Usar Lumen

Windows 10/11 x64, con Microsoft Edge WebView2. El instalador incluye el runtime Python del IDE; los compiladores y SDK de tus proyectos se seleccionan aparte. El paquete portable debe extraerse completo: `lumen.exe` necesita `_internal`. Los ejecutables de esta preview no están firmados con Authenticode.

El primer inicio permite elegir tema, idioma, distribución y perfil. Una instalación nueva comienza sin archivos recientes inventados. Los paneles usan una base de vidrio al 68,7 % y la esfera una base al 48,5 %, con iridiscencia animada y movimiento reducido configurable.

## Trabajo diario

- Pestañas agrupadas por carpeta, selector de archivos, menús contextuales, renombrado, eliminación recuperable y apertura en otra ventana.
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
python tests/test_ui_r5.py --output qa-output
python tests/test_visual_r5.py --output qa-output
```

Las pruebas visuales requieren Playwright y Microsoft Edge. Las pruebas dependientes de herramientas pueden omitirse si no están instaladas.

## Documentación y licencia

[Lantern, cambios y límites](docs/PREVIEW_R5.md) · [Lenguajes](docs/LENGUAJES.md) · [Extensiones](docs/EXTENSIONES.md) · [Seguridad](docs/SEGURIDAD.md)

Repositorio público bajo [licencia propietaria](LICENSE), sin licencia de código abierto por el momento. Las dependencias mantienen sus propias licencias: [avisos de terceros](THIRD_PARTY_NOTICES.md).
