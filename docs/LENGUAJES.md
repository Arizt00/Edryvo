# Lenguajes y depuración · Preview R5

| Lenguaje | Ejecución | Depuración | Herramientas |
|---|---|---|---|
| Python | Intérprete incluido | bdb integrado | Biblioteca estándar incluida |
| JavaScript / TypeScript | Node | Node Inspector | Node; TS según runtime/configuración |
| C / C++ | GCC/G++ o Clang | LLDB DAP | Compilador, SDK y LLVM |
| Rust | rustc | LLDB DAP | Rust y LLVM |
| Java | javac y java | JDI | JDK 17+ |
| C# | dotnet build | NetCoreDbg | .NET SDK y adaptador |
| Go | go build | Delve | Go y adaptador |
| nC .n / .nc | ncc | Compilación nativa + LLDB | ncc y LLVM |
| ASM | Ensamblador según formato | LLDB según símbolos | NASM o Clang, SDK/linker |
| HTML / CSS | Vista previa local | DOM/CSS/JS | Documento HTML y motor web |

Los programas se ejecutan dentro de los paneles de Lumen con salida y entrada estándar. El depurador acepta pausa, continuación, pasos y entrada según el adaptador. Una GUI del programa puede abrir su propia ventana.

C/C++, Rust, Go y Java tienen una ruta para el archivo activo. Cargo, Maven, Gradle, CMake o paquetes npm requieren configurar su sistema de construcción y punto de entrada. C# busca un proyecto cercano o prepara uno temporal para un archivo suelto. Un `MonoBehaviour` depende del runtime Unity: no es un programa C# autónomo.

Configura las herramientas y listas de argumentos en Depuración → Lenguajes y depuradores. Variables admitidas: `${file}`, `${fileDirname}`, `${fileBasenameNoExtension}`, `${workspaceFolder}`, `${target}` y `${port}`. DAP admite stdio o TCP loopback.

## Edición y Lantern

Monaco aporta coloreado, snippets y servicios integrados para sus lenguajes. Las extensiones ejecutables y servidores LSP añaden funciones semánticas, diagnósticos, definición e inlays. Descargar un SDK no garantiza que incluya un LSP.

Lantern usa el búfer sin guardar, validación previa, cancelación y archivos temporales para compilación. Lens y la retención de memoria tienen capacidades distintas por adaptador. Consulta [Preview R5](PREVIEW_R5.md) y los ejemplos cooperativos.

nC no se distribuye con Lumen: selecciona tu compilador en ajustes. Los dominios low-level y el hardware remoto no se declaran validados. HTML/CSS no se ejecutan como binarios; la vista previa utiliza un origen separado de la API autenticada del IDE.

Referencias: [DAP](https://microsoft.github.io/debug-adapter-protocol/specification), [JDI](https://docs.oracle.com/en/java/javase/21/docs/api/jdk.jdi/com/sun/jdi/package-summary.html), [LLDB DAP](https://lldb.llvm.org/use/lldbdap.html), [NetCoreDbg](https://github.com/Samsung/netcoredbg), [Delve](https://github.com/go-delve/delve).
