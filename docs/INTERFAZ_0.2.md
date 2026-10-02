# Interfaz Lumen 0.2

## Alcance

Revisión de la interfaz del ZIP 0.1.0. No se ha accedido a una copia local de Codex ni a repositorios de EMMA o NCC. El servidor y el lanzador Python solo cambian su cadena de versión; no cambian los contratos de archivos, procesos o IA.

## Cabecera y acciones

Los botones rojo, amarillo y verde desaparecen del HTML. Los menús genéricos de puntos se sustituyen por iconos explícitos: abrir proyecto, ajustes del editor y conexión del asistente. Los textos de archivos muy largos pueden seguir truncándose con elipsis, que no son botones de menú.

La ventana del navegador usa sus propios controles. Solo cuando existe el puente pywebview se presentan minimizar, pantalla completa y cerrar. Esta condición se ha comprobado ausente en web; el host nativo Windows no se ha ejecutado.

## Modelo de paneles

`layout-state.js` define un estado versionado y validado. Cada panel aparece exactamente una vez en izquierda, derecha o abajo. Los identificadores desconocidos, duplicados y tamaños inválidos se normalizan. La clave es `lumen.layout.v2`; una versión incompatible o JSON inválido restablece Lumen.

`docking.js` mueve los nodos DOM vivos, sin clonarlos ni recrear el editor. Dos o tres paneles en una zona comparten una fila de pestañas. El editor conserva su zona central. La versión no ofrece ventanas flotantes del sistema, monitores múltiples, particiones arbitrariamente anidadas ni múltiples instancias del mismo panel.

Las cuatro distribuciones son Lumen (original), Código (sin asistente), Agrupado (asistente y consola a la derecha) y Enfoque (solo editor). Los ajustes posteriores crean una distribución personalizada. El atajo Enfoque conserva una instantánea durante la sesión; después de una recarga sin esa instantánea, salir de enfoque restaura Lumen.

Los separadores aceptan ratón y teclado. Las flechas ajustan 10 px, Shift+flecha 30 px. Doble clic elimina el tamaño personalizado. La distribución se guarda con localStorage cuando está disponible; si se deniega, la sesión sigue funcionando. Se ha probado serialización y restauración con almacenamiento inyectado, no la durabilidad real entre cierres del navegador.

## Movimiento

`motion.js` usa Web Animations API. Hay una animación vigente por elemento; una acción nueva cancela la anterior. El cambio de distribución traduce superficies sin escalar el texto del editor. No se anima el tamaño de las fuentes ni se añade movimiento continuo al área de código.

Los tiempos definidos son 120 ms para microinteracciones, 180 ms para entradas y 220 ms para desplazamientos de distribución. El cambio de tema tiene una ventana de transición de 240 ms. Son decisiones de diseño, no tiempos de render medidos en cualquier hardware.

La preferencia `prefers-reduced-motion` y el ajuste local desactivan el movimiento. Se comprobó que alternancias rápidas finalizan sin animaciones ejecutándose ni IDs DOM duplicados. No se ha hecho un benchmark de 60/120 Hz, una medición de latencia de entrada ni una certificación de fluidez universal.

La integración del pequeño objeto Babylon consulta la visibilidad de la página y del panel. Sigue siendo opcional; la prueba usa su alternativa CSS, no un motor WebGL cargado.

## Navegación y densidad

Las pestañas agrupadas y de archivo permiten flechas, Home y End con foco visible. Las pestañas de archivo se reordenan con arrastre o Alt+Shift+flecha; el orden vive en la colección de documentos abiertos, no en una copia visual. No se promete restauración completa de documentos no guardados tras cerrar la aplicación.

Los iconos tienen nombre accesible y ayudas que no dependen únicamente de su dibujo. Hay estados de foco, anuncios de distribución y reducción de movimiento. Esto no constituye una auditoría completa WCAG ni una validación con todos los lectores de pantalla.

Se mantienen los tres temas. Los refinamientos están separados en `web/refinement.css`, cargado después de `style.css`. La densidad Compacta reduce controles y espaciado; el tamaño del código se configura por separado. Se probaron anchos de 1024, 1100, 1366, 1648 y 1920 px. Por debajo de 1180 px, el grupo derecho pasa a un cajón superpuesto. No es una interfaz móvil completa.

## Referencias de implementación

- MDN, Element.animate: https://developer.mozilla.org/en-US/docs/Web/API/Element/animate
- MDN, prefers-reduced-motion: https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion
- W3C APG, patrón de pestañas: https://www.w3.org/WAI/ARIA/apg/patterns/tabs/

Las referencias documentan las API y patrones utilizados; no certifican esta aplicación.
