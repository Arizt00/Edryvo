# Distribución y estado de instaladores · 0.4

## Dos rutas distintas

El **instalador de fuente** (`tools/install_user.py`) es ejecutable con Python y crea una instalación versionada por usuario. La validación de esta entrega instaló y desinstaló una copia real en Linux en una ruta con espacios, con `--target`, `--skip-dependencies` y `--skip-assets`. Se verificaron su entorno privado, el arranque HTTP y su comando `lumen focus`. Esa prueba no verifica la instalación de dependencias de red, los accesos de menú ni una ventana gráfica nativa.

La **distribución autónoma** está preparada mediante `packaging/lumen.spec`. Sus recetas se incluyen, pero no se produjo un binario PyInstaller en este entorno. Windows e Inno Setup generan Setup.exe; macOS e hdiutil generan DMG; Linux produce un bundle tar.gz con instalador de usuario. Deben compilarse, probarse y firmarse donde corresponda. No hay un `.exe` o `.dmg` oculto dentro del ZIP.

## Comandos

Mostrar rutas sin instalar:

```bash
python tools/install_user.py --plan
```

Instalar con dependencias en un destino nuevo:

```bash
python tools/install_user.py --launch
```

Añadir el SDK oficial opcional de Copilot:

```bash
python tools/install_user.py --copilot --launch
```

Esto instala una dependencia, no autentica una cuenta ni valida la cuota. El runtime del SDK puede necesitar una descarga adicional; revisa su documentación actual antes de distribuirlo.

Instalación base sin descargas:

```bash
python tools/install_user.py --target "ruta/nueva/Lumen" --skip-dependencies --skip-assets
```

Con esa modalidad no se instalan pywebview, xterm, Monaco, Babylon, keyring ni ConPTY. El editor base sigue siendo una aplicación local servida por Python. La prueba de esta modalidad no se atribuye a sus componentes ausentes.

## Ubicaciones predeterminadas

Windows: `%LOCALAPPDATA%/Programs/LumenStudio/versions/0.4.0`. macOS: `~/Library/Application Support/LumenStudio/application/versions/0.4.0`. Linux: `~/.local/share/lumen-studio/application/versions/0.4.0`.

Preferencias y datos viven en el directorio de usuario definido por `backend/preferences.py`, independiente de la instalación. La variable `LUMEN_DATA_DIR` permite usar un perfil aislado. No coloques una clave en el argumento de una orden ni dentro del repositorio.

El instalador no sobrescribe una versión existente. Para repetirla, utiliza otro destino o desinstala esa copia después de guardar cualquier cambio al código. Su desinstalador comprueba el manifiesto y elimina la versión y los lanzadores que le pertenecen; no elimina preferencias ni proyectos. Algunos accesos de menú pueden requerir limpieza manual. En Windows utiliza un Python externo al entorno que estás eliminando.

## Checklist de publicación

1. Fijar y registrar las versiones exactas de dependencias, conservar licencias y generar SBOM. Las cotas de requirements no constituyen un lockfile reproducible de producción.
2. Construir por sistema y arquitectura. Revisar WebView2, WebKit/Qt, DPI, permisos, ventanas, rutas con Unicode, carpetas protegidas y ConPTY.
3. Ejecutar la navegación directa con CSP, carga de Monaco/workers, Babylon/shader y xterm. Probar teclado, lectores de pantalla y movimiento reducido.
4. Probar actualización/desinstalación y verificar que los proyectos/credenciales no se sobrescriben. No hay todavía un actualizador automático de la aplicación.
5. Firmar Windows y firmar/notarizar macOS con las credenciales del publicador; no se solicitan ni se fabrican certificados en estos scripts.
6. Probar las integraciones de IA con cuentas autorizadas y gasto controlado. No declarar compatibles modelos o extensiones que no se hayan probado.

El workflow incluido se activa manualmente y crea artefactos de construcción, no una publicación automática. PyInstaller no es un compilador cruzado entre los tres sistemas; documentación oficial en `FUENTES.md`.
