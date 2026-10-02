# Integrar la interfaz Lumen 0.3 en Codex

## Base exacta

El parche se ha generado contra **LumenStudio_0.2_Interfaz.zip** de esta conversación. No se ha inspeccionado tu copia de trabajo posterior. No pegar el ZIP completo sobre un repositorio modificado.

Conserva las integraciones reales de EMMA y nC/NCC que existan en el destino. No se cambian protocolos, ejecución, compilación ni autenticación. Las únicas modificaciones Python son identificadores de versión; no es necesario imponerlos si el destino usa otro versionado.

## Procedimiento

Comprueba el estado y conserva cualquier trabajo pendiente según el flujo del repositorio. No ejecutar reset, clean, checkout destructivo ni un stash automático para imponer esta revisión.

```bash
git status --short
git switch -c ui/lumen-0.3
# Sustituye la ruta por la ubicación real del archivo extraído.
git apply --check /ruta/Lumen_UI_0.2_a_0.3.patch
```

Solo si la comprobación termina correctamente:

```bash
git apply /ruta/Lumen_UI_0.2_a_0.3.patch
git diff --check
npm run check
npm run test:layout
python3 tools/build_native.py
python3 -m unittest discover -s tests -v
```

Si el parche no encaja, no usar `--reject` indiscriminadamente ni copiar archivos completos encima. Leer los cambios por componentes y fusionarlos con la implementación actual. Revisar especialmente `app.js`, `index.html` y `docking.js`. El manifiesto del paquete incluye SHA-256 de los archivos base y nuevos para facilitar la comparación, no para forzar una sustitución.

## Componentes

`web/atelier.css` es la nueva capa de estilo. Debe cargarse después de style.css y refinement.css. No quitar el código ni los recursos ya integrados por Codex.

`layout-state.js` migra v2 a v3 e introduce estados contraídos y navegación compacta. `docking.js` añade franjas, controles, recuperación, foco y conservación de nodos. `motion.js` interpola las pistas de la cuadrícula y cancela transiciones interrumpidas.

`icons.js` sustituye la familia de glifos por SVG locales con retícula común. `index.html` añade los controles y `app.js` conecta atajos, ajustes y paleta. No se sustituyen los modelos del editor por capturas ni por componentes simulados.

`test_ui_refinement.py` usa ahora la clave persistida v3; la migración desde v2 se prueba explícitamente en `test_ui03.py`. El harness incorpora atelier.css. Se añaden pruebas puras de estado, glifos y pares de contraste. No borrar las pruebas anteriores.

El parche no incluye capturas de pantalla, vídeo, dependencias descargadas, fuentes tipográficas ni bibliotecas compiladas. El ZIP completo y las capturas entregadas sirven como referencia visual.

## Comprobación en destino

Las tres suites de UI están escritas para el editor base en una copia sin `web/vendor`:

```bash
python3 -m pip install playwright
python3 -m playwright install chromium
python3 tests/test_ui.py --transport direct
python3 tests/test_ui_refinement.py --transport direct
python3 tests/test_ui03.py --transport direct
```

Comprobar además Monaco y workers, Babylon y shader, pywebview/WebView2, DPI y escalado Windows, almacenamiento entre cierres reales, teclado y servicios EMMA/NCC del destino. Las capturas entregadas muestran el editor integrado y la alternativa CSS, no esas integraciones opcionales.

No convertir una mejora de interfaz en un rediseño no solicitado. Mantener los tres temas, la geometría Lumen y la recuperación explícita de los paneles. Un cambio de versión o un botón visible no demuestra que un servicio externo esté conectado.
