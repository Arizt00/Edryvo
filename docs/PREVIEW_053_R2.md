# Zénit 0.5.3 Preview R2

Zénit sustituye a Edryvo como nombre del producto. La marca aparece en el IDE, las ventanas nativas, el instalador y el desinstalador. Los nombres de descarga usan `Zenit` para mantener rutas portables; el nombre visible lleva tilde. Los perfiles de versiones anteriores se conservan mediante rutas y credenciales compatibles.

La vista web y Lantern pueden abrirse en ventanas nativas compartidas. Sus botones permiten volver a acoplarlas a la ventana principal. La vista web recibe HTML y dependencias abiertas desde los búferes, sin guardar el archivo original. Lantern muestra la sesión existente; abrir su ventana no crea otra ejecución ni reinicia su memoria. Los cuatro espacios de desarrollo tienen controles de desacoplamiento y retorno.

El catálogo de extensiones muestra el icono del paquete instalado o del registro, con caché local y alternativa para paquetes sin icono. Las imágenes se validan y no se insertan como HTML ejecutable. Los estilos de trabajo, las herramientas de vista previa, el catálogo y el buscador tienen espaciado y superficies adaptadas al tema activo.

La compatibilidad incorpora `TextDocument.save()` y `workspace.saveAll()`, guardado atómico, comprobación de versión en disco y de conflictos entre ventanas, y eventos de guardado. No se presenta una operación fallida como un guardado correcto. La paridad completa con VS Code sigue siendo un trabajo pendiente: las APIs no implementadas se identifican por su nombre y cada extensión debe verificarse con su comportamiento real.

Distribución: Windows EXE y ZIP portátil; Linux DEB y paquete portátil. El flujo de construcción de macOS existe, pero un DMG sólo se considera disponible después de compilarlo y comprobarlo en macOS. La preview conserva su licencia propietaria.
