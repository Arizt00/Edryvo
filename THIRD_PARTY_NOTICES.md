# Componentes de Lumen Studio 0.5.2

Esta distribución Windows contiene bibliotecas locales. No requiere una CDN para cargar su interfaz.

| Componente | Versión de esta entrega | Procedencia |
|---|---|---|
| Monaco Editor | 0.52.2 | npm monaco-editor / Microsoft |
| Babylon.js | 8.32.0 | npm babylonjs |
| Three.js | 0.180.0 | npm three |
| xterm.js / addon-fit | 5.5.0 / 0.10.0 | npm @xterm |
| pywebview | 6.2.1 | PyPI / pywebview |
| Python principal | 3.12.10 | python.org / PSF |
| Python auxiliar para LLDB | 3.11.9 embeddable amd64 | python.org / PSF |
| pywin32 | 312 | PyPI; integración del desinstalador con Windows |
| pywinpty | 3.0.5 | PyPI; incluye OpenConsole y winpty-agent |
| websocket-client | 1.9.2 | PyPI |
| NetCoreDbg | 3.2.0-1092 | github.com/Samsung/netcoredbg |
| Delve | 1.27.2, compilado con Go 1.27.1 | github.com/go-delve/delve |

Los textos de licencia se conservan junto a web/vendor, en debugger-support y en licenses. Las dependencias de Go usadas para compilar Delve tienen sus licencias en licenses/delve-dependencies. Los avisos de paquetes Python están en licenses/python-packages. PyInstaller se usa para construir; las licencias de su bootloader incluyen su excepción de distribución.

Se usan fuentes instaladas en el sistema, sin añadir una tipografía de terceros. Los iconos son SVG locales. Los recursos de paisaje preexistentes proceden de las referencias del proyecto; no se utiliza una captura entera como interfaz.

LLVM, GCC, SDK .NET, JDK, Node, Rust, Go, Git, ncc y modelos de IA son herramientas externas. Se detectan o se seleccionan en el instalador; sus licencias y requisitos son propios. No se incluyen credenciales, pesos de modelos ni una copia del repositorio de nC. La ruta local nC se conserva como configuración de este equipo.

El código propio de Lumen se publica bajo la licencia propietaria de preview incluida en LICENSE. Las licencias de terceros se mantienen independientes. Las marcas de terceros no implican afiliación. Las integraciones Copilot/Ollama/API conservan las condiciones de sus proveedores. El host VSIX admite aportaciones declarativas y una API Node parcial; no equivale al host completo de VS Code.

Esta entrega incluye github-copilot-sdk 1.0.15 y sus dependencias Python; sus versiones y licencias están en licenses/python-packages. Los clientes oficiales Codex, Claude Code, Gemini CLI y Copilot CLI se instalan por separado; no se incluyen sesiones ni credenciales.
