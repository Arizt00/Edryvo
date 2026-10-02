# Diseño Lumen 0.3

La referencia es la composición Lumen elegida: marca y búsqueda arriba; navegación y Proyecto a la izquierda; editor central; asistente a la derecha; consola inferior. Las capturas de la entrega proceden del programa ejecutado, no de generación de imágenes.

## Geometría

Referencia: 1648 × 928 píxeles CSS. Cabecera de 64 px, estado de 34 px y separaciones de 10 px. El editor comienza aproximadamente en x=404 con los laterales originales. El lateral izquierdo predeterminado mide unos 296 px, el derecho unos 422 px y la consola inferior 180 px. Se aplican límites dependientes del tamaño de ventana.

Los laterales se contraen a 44 px. La navegación pasa de 78 px a 48 px en modo compacto; en ventanas pequeñas su modo con etiquetas usa 68 px. El editor tiene prioridad sobre las etiquetas opcionales de la cabecera. El ancho mínimo global es 720 px y las suites cubren desde 768 hasta 3840 px; no es una versión móvil completa.

Las esquinas principales son de 14 px; controles de 8 a 12 px según función. No se usa una transparencia sobre el código ni un fondo de paisaje detrás del texto editable. Las imágenes pequeñas del lateral se conservan como parte del diseño aprobado y desaparecen en navegación compacta.

## Tokens principales vigentes

| Token | Día | Oscuro | Bosque |
| --- | --- | --- | --- |
| Fondo | #F1F3F9 | #12151D | #071A13 |
| Superficie | #F9FAFF | #191D28 | #10261D |
| Editor | #FFFFFF | #151922 | #0B2118 |
| Texto | #20243B | #E6EAF4 | #E1EEE5 |
| Texto secundario | #535D7B | #B0BAD0 | #AEC7B8 |
| Texto discreto | #626D86 | #929FB8 | #8EAF9E |
| Acento | #6250DA | #B3A5FF | #98D0AE |
| Borde | #E1E5EF | #2B3243 | #234236 |

El archivo vigente es `web/atelier.css`; las hojas anteriores permanecen para limitar el alcance del parche. Los tres tests de tokens validan pares concretos de texto/sintaxis con umbral de contraste 4,5:1, no todos los estados del producto ni certificación WCAG.

## Iconos y tipografía

59 iconos SVG originales, 24 × 24, trazo de 1,7 con esquinas y extremos redondeados. Los tamaños se adaptan al control, sin imágenes bitmap para los glifos. El catálogo está en LUMEN_LINE.svg. No se incluyen fuentes tipográficas ni fuentes de iconos.

La aplicación utiliza las familias del sistema definidas en style.css. El código base conserva 12,5 px / 16 px y se puede ampliar en Ajustes. La marca pasa a 22 px; encabezados de panel de 13 px. Los nombres largos mantienen truncado visual sin modificar la ruta real.

## Movimiento y calidad

Controles 120 ms; aparición 180 ms; cambio de geometría 240 ms. El contenido no se escala. Las animaciones se pueden interrumpir y el movimiento reducido tiene prioridad. Ver INTERFAZ_0.3.md y QA.md.

No se certifica identidad de rasterizado entre sistemas operativos, fuentes, DPI, navegadores y Monaco. Las capturas usan editor base y esfera CSS; las integraciones opcionales necesitan verificación en destino.
