# Integración con Codex · Lumen 0.4

## Base de este cambio

El parche se genera contra una extracción limpia de `LumenStudio_0.3_Interfaz.zip` de la conversación. No se inspeccionaron cambios posteriores del repositorio que Codex esté desarrollando. No se conecta EMMA ni se inventan comandos de NCC. No copies toda la carpeta encima del proyecto existente.

## Aplicación

Conserva o confirma tus cambios actuales. Desde la raíz correcta del proyecto:

```bash
git status --short
git apply --check /ruta/al/paquete/lumen-0.3-to-0.4.patch
git apply /ruta/al/paquete/lumen-0.3-to-0.4.patch
```

El chequeo comprueba aplicabilidad, no la compatibilidad semántica con cambios propios. Si falla, integra por archivo comparando la base 0.3 y el estado actual; no uses una sustitución destructiva. `PATCH_MANIFEST.json` identifica los archivos y hashes de esta entrega. El informe `PATCH_VERIFICATION.json` registra la aplicación sobre una base limpia, no sobre un repositorio desconocido.

## Prioridades posteriores

1. Probar navegación real con CSP, workers de Monaco, shader Babylon y xterm. Ejecutar las suites en Windows y macOS, DPI y ConPTY, sin trasladar resultados del editor base a motores que no se hayan cargado.
2. Construir instaladores autónomos en los tres sistemas, generar lockfiles/SBOM, completar firma y notarización con credenciales autorizadas, y probar actualización/desinstalación sin pérdida de datos.
3. Validar cada proveedor con cuentas reales autorizadas, una solicitud pequeña y límites de gasto. Catalogar generación/streaming/cancelación/errores por separado. No usar una respuesta mock para declarar conectado Copilot o una API.
4. Decidir y construir un host ejecutable de plugins. El actual es declarativo. Definir APIs, procesos y permisos antes de afirmar compatibilidad de extensiones VS Code o exponer webviews de terceros.
5. Ampliar LSP/DAP, lenguajes y pruebas a repositorios reales. Registrar capacidades admitidas por servidor; no declarar «todos los lenguajes» por una lista de sufijos.
6. Integrar NCC y EMMA desde sus repositorios y contratos reales. NCC conserva la autoridad de sintaxis/semántica; EMMA debe usar una interfaz y permisos definidos por su implementación.

Conserva las referencias visuales Lumen y los temas día, oscuro y bosque. Toda mejora debe preservar contracción, agrupación, concentración, búsquedas, guardado con conflicto y revisión de cambios. Evita indicadores ficticios de CPU, IA conectada, compilación o compatibilidad.

El archivo `docs/QA.md` es el estado actual. `docs/history` conserva evidencia anterior que no debe presentarse como una ejecución de la nueva versión.
