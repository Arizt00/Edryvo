# Interfaz Lumen 0.3

## Alcance

Revisión incremental del ZIP 0.2: controles laterales reversibles, navegación compacta, iconografía y acabado visual. Se conservan ejecutores, contratos HTTP, workspace, modelo de archivos, adaptador de IA y núcleo nativo. En Python únicamente se actualizan cadenas de versión. No se incorpora ningún protocolo de EMMA o NCC.

## Modelo de distribución

`layout-state.js` mantiene funciones puras. `version: 3` incorpora `collapsed: []` y `railCompact: false`, sin sustituir `groups`, `active`, `hidden` ni `sizes`. Solo izquierda y derecha admiten contracción; la consola inferior mantiene su ocultación y redimensionado anteriores.

Contraer no añade elementos a `hidden`. El inventario y la pestaña activa permanecen; los paneles conservan sus nodos DOM. La franja mide 44 px y muestra un botón de expandir y un botón por herramienta visible. Expandir una herramienta selecciona su pestaña antes de mostrar el grupo.

Mover una herramienta a una zona contraída expande esa zona. Enfocar conserva la instantánea completa en memoria y la restaura al salir. Tras recargar en enfoque, se ofrece la distribución base como salida segura; no se promete recuperar una instantánea de enfoque que no se persistió.

`DockManager.read()` lee `lumen.layout.v3` y, si no existe, `lumen.layout.v2`. La normalización admite versiones 2 y 3, valida tipos, rechaza identificadores ajenos y limita tamaños. Guardar escribe únicamente la clave v3. Una clave malformada vuelve a un estado utilizable. No se envía la distribución al servidor.

## Acceso y foco

Los controles de expansión son botones nativos con `aria-expanded` y `aria-controls`. El contenido contraído usa `inert` y `aria-hidden`, además de ocultación visual. Durante la contracción por atajo, se recuerda el elemento enfocado del contenido y se traslada el foco al control de expansión. Si el elemento sigue visible al expandir, se restaura; de lo contrario se utiliza un control de la cabecera.

Los grupos conservan el patrón de pestañas con selección, orden de foco y flechas. La navegación compacta mantiene los seis botones existentes y sus nombres accesibles. Es una alternativa de 48 px, no una barra distinta con acciones simuladas.

En ventanas por debajo de 1180 px, el lateral derecho usa el cajón existente. Su botón superior sigue disponible; Escape o el fondo lo cierran. El lado izquierdo puede contraerse también en esos tamaños.

## Movimiento

`LumenMotion.changeLayout()` toma los valores calculados de columnas y filas de la cuadrícula antes de cancelar una animación activa, aplica la nueva distribución y anima la geometría hasta el destino en 240 ms. La interpolación no usa escalado de texto. Los paneles internos se recortan durante la transición y conservan su anchura de composición; el editor obtiene su tamaño real.

Una orden nueva, el redimensionado de la ventana, un separador o la desactivación del movimiento cancelan la animación anterior. Las promesas de animaciones canceladas se capturan. Al terminar se eliminan tanto el registro de animación como la clase temporal. Los iconos no tienen un bucle de renderizado.

Esta interpolación realiza trabajo de maquetación. No se ha medido rendimiento a 60/120/144 Hz, ni se afirma que el coste sea nulo. Debe medirse en destino con Monaco y en el monitor del usuario.

## Sistema visual

`atelier.css` carga después de las hojas previas. Define los tokens vigentes, las franjas laterales, navegación compacta y los acabados de controles, árbol, pestañas, tarjetas, consola, ventanas y mensajes. La composición Lumen se mantiene como opción por defecto.

`icons.js` contiene 59 SVG originales, retícula 24 × 24, trazo base 1,7 y relleno tonal puntual. Las etiquetas de C, C++, ASM y nC se dibujan como texto local. No se necesita una fuente de iconos, CDN ni conexión para los glifos. `docs/LUMEN_LINE.svg` permite revisar la familia.

El tema Día usa un violeta menos luminoso para mejorar su contraste sobre la selección. Los pares principales de texto y sintaxis definidos en los tokens se prueban con un umbral 4,5:1. Esto no sustituye una auditoría de accesibilidad del producto: hay texto ornamental con opacidad, tamaños de destino y tecnología asistiva que requieren evaluación adicional.

## Referencias técnicas

Patrón de divulgación WAI-ARIA: https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/
Cancelación de animaciones: https://developer.mozilla.org/en-US/docs/Web/API/Animation/cancel
Contenido inerte: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Global_attributes/inert

## Verificación

`tests/test_layout03.mjs` comprueba el estado, la migración y los glifos. `tests/test_theme_tokens.mjs` comprueba pares concretos de colores. `tests/test_ui03.py` prueba contracción, restauración, foco, selección, scroll, grupos, teclas, persistencia serializada, cambios rápidos y anchuras entre 768 y 3840 px. Los detalles del transporte utilizado figuran en QA.md.
