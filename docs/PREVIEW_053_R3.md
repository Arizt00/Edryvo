# Zénit 0.5.3 Preview R3

La paleta de comandos de Monaco utiliza una superficie opaca centrada, un campo redondeado y colores del tema activo. Desaparece el recuadro gris y el contorno rectangular de foco. Las ventanas de revisión, controles de ajustes y paneles reciben espaciado y bordes uniformes. Las animaciones respetan el movimiento reducido del sistema.

El instalador de extensiones muestra el icono propio, versión, licencia declarada, tamaño del VSIX, tamaño descomprimido y estado de cada dependencia requerida u opcional. Los tamaños son reales para ese paquete; no se anuncian como el total de dependencias que aún no se han revisado. Instalar bloquea solicitudes duplicadas mientras guarda el paquete y muestra el error en el mismo diálogo si falla. Descargar, inspeccionar, instalar e iniciar motor siguen siendo operaciones distinguibles.

La compatibilidad añade `window.createQuickPick()`, `window.createInputBox()`, `window.showQuickPick()` y `window.showInputBox()`: opciones dinámicas, selección múltiple, separadores, navegación de pasos, botones de elementos, validación asíncrona y tokens de cancelación. Los eventos conservan la identidad de los objetos de la extensión. Un asistente abierto no se mata por el timeout del comando mientras espera al usuario. Detener el host elimina sus controles.

Se verifican los controles en el servidor Python, host Node y navegador Edge reales, además de los tamaños y la instalación/persistencia de un VSIX. Los paneles se revisan en los tres temas integrados y a varias anchuras de escritorio.

La paridad completa con VS Code continúa pendiente. Entre los límites están la instalación automática de toda la cadena de dependencias, exports compartidos entre hosts, TextMate, entradas `browser`, restauración completa de webviews y opciones avanzadas de UI. Las APIs ausentes producen un error explícito. Consulta el [estado actualizado de extensiones](EXTENSIONES.md).

Distribución: EXE y ZIP Windows; DEB y portable Linux. macOS requiere construcción y verificación en Mac; las ejecuciones de GitHub Actions están bloqueadas por la facturación de la cuenta. No se publica un DMG sin verificar. La preview conserva su licencia propietaria.

Cada revisión instala su contenido en una carpeta propia. Una ventana de una revisión anterior puede seguir trabajando con sus archivos originales hasta que el usuario decida reiniciar; los accesos directos abren la revisión nueva.
