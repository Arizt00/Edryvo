# Arquitectura de Lumen 0.4

La UI anterior se conserva. La ampliación se compone en `backend/platform_services.py` y `web/src/workbench.js`, sin sustituir el contrato básico de archivos y tareas. Las rutas nuevas están bajo `/api/platform/` y pasan por la autenticación del servidor existente.

| Módulo | Responsabilidad |
| --- | --- |
| `preferences.py` | Esquema de 43 preferencias, validación, escritura atómica y auditoría mínima |
| `extensions.py` | Open VSX, revisión segura de VSIX, instalación y contribuciones declarativas |
| `terminals.py` | Perfiles, PTY/ConPTY, entrada/salida, tamaños y ciclo de vida |
| `toolchains.py` | Detección, tareas argv, planes de instalación y configuración LSP |
| `lsp.py` | Transporte JSON-RPC stdio, sincronización, solicitudes y diagnósticos |
| `providers.py` | Adaptadores, credenciales, streaming, cancelación y conversaciones en memoria |
| `hardware.py` | Muestreo de lectura, limitado y optativo |
| `platform_services.py` | Composición, rutas, confianza y cola de comandos de UI |
| `lumen.py` | Cliente de comandos de una instancia local ya iniciada |
| `workbench.js` | Páginas auxiliares, ajustes, proveedores, PTY, herramientas y LSP en la UI |
| `platform.css` | Diseño de páginas nuevas, estados, controles y adaptación de tamaños |

El servicio HTTP maneja objetos pequeños y salida incremental por consultas. La PTY se mantiene en Python, no en una etiqueta que finge ser una consola. El frontend usa xterm si el paquete local está disponible; en caso contrario, conserva un visor básico explícito.

La extensión del editor mantiene separados los modelos de archivo y las páginas auxiliares. Abrir ajustes no destruye el búfer de edición. Los grupos de paneles reutilizan nodos y los laterales conservan estado al contraerse. El modo concentración guarda y restaura el estado de distribución v3 existente.

El lenguaje del editor y el compilador no son la misma función. Asociaciones y snippets no acreditan semántica; LSP agrega capacidades cuando existe un servidor. Las tareas ejecutan argumentos explícitos de una herramienta real. El proyecto nC/NCC debe aportar su interfaz; no se crea un dialecto paralelo dentro del IDE.

El asistente produce propuestas revisables. La interfaz conserva una instantánea del archivo al pedir una respuesta y rechaza aplicar automáticamente sobre un búfer distinto. La autorización de ejecución no se delega a un modelo. Las sesiones de IA permanecen en memoria, no se exportan como preferencias.

Los recursos decorativos conservan la esfera Babylon opcional y su alternativa CSS. Esta entrega no añade un motor 3D para dibujar texto o botones. El renderizado de los controles utiliza DOM/CSS; el núcleo C/C++/ASM conserva las operaciones de estadísticas y búsqueda existentes.

El empaquetado fuente y el binario son procesos diferentes. Los scripts de construcción nunca afirman que hayan generado un artefacto si falta su compilador o empaquetador. La interfaz no declara conectado un proveedor por el mero hecho de elegir su nombre.
