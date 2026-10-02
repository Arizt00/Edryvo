# Lantern: continuidad cooperativa nativa

Lantern recompila y sustituye el proceso. El programa participa guardando **estado de aplicación**, recuperándolo al arrancar y migrándolo cuando cambia su esquema. No se serializan la pila, punteros, hilos ni recursos del sistema operativo. Esos recursos se reconstruyen a partir del estado guardado.

## C y C++

El ejecutor de Lumen incluye esta carpeta automáticamente en la búsqueda de headers. En una tarea propia añade `-I` con esta carpeta. Usa `#include "lantern.h"` o `#include "lantern.hpp"`. Abre **Lantern → Memoria e historial → Ejemplo de continuidad** para crear un ejemplo funcional sin reemplazar tu archivo.

1. Define una estructura con datos de tamaño fijo: números, arrays y caracteres. No guardes `std::string`, `std::vector`, punteros ni handles. El wrapper comprueba que el tipo admite copia trivial; todavía debes excluir los punteros.
2. Al arrancar, llama `lantern_restore(&state, sizeof(state), schema, migrate)` o construye `lantern::State<Data> state(schema, migrate)`.
3. Guarda en puntos coherentes con `lantern_checkpoint` o `state.checkpoint()`. La escritura se publica mediante reemplazo del archivo temporal y lleva checksum.
4. En bucles prolongados llama `lantern_poll` o `state.reload()`. Cuando devuelve 1/true, el checkpoint ya está guardado: libera tus recursos y sal del programa. Lantern solicita esta salida y espera hasta dos segundos antes de recurrir a detener el proceso. En ese caso se conserva el último checkpoint completo.
5. Cambia el número de esquema si cambias tipos, orden, alineación, arquitectura o significado de los campos. Proporciona una función `lantern_migration` que transforme el esquema anterior en el nuevo. Si no existe una migración válida, el SDK devuelve -2 y conserva el archivo anterior. Nunca reinicies silenciosamente un estado incompatible.

Los códigos son 1 (restaurado/guardado), 0 (primer arranque/sin petición), -1 (E/S), -2 (esquema incompatible), -3 (archivo corrupto). Hay un límite de 1 MiB por checkpoint nativo. El callback de migración recibe el contenido antiguo y una estructura nueva inicializada a cero; devuelve 1 al terminar. El SDK publica el resultado solo si la migración y la escritura terminan correctamente.

## nC

El ejemplo `counter.n` usa las capacidades nativas de ncc: JSON, entorno y archivos. Las funciones `checkpointPath`, `load`, `migrate`, `checkpoint` y `reloadRequested` son el soporte reutilizable: incorpóralas al contenedor runtime de tu programa y define las claves de estado que necesitas. El ejemplo incluye la migración 1 → 2 y conserva el contador.

En cada arranque carga el estado con `load(path, version)`. En puntos seguros, guarda con `checkpoint(state, path)`. En tu bucle, cuando `reloadRequested(path)` sea true, guarda y sal. La escritura usa archivo temporal y `rename_file`; comprueba que tu compilador permite reemplazar el destino. Si tu programa mantiene recursos externos o varios hilos, coordina su cierre antes de confirmar el estado.

## Persistencia

`LUMEN_LANTERN_STATE` contiene la ruta privada del checkpoint del archivo activo; `LUMEN_LANTERN_REVISION` identifica la revisión. Los SDK C/C++ añaden `.native` y el protocolo de salida usa `.reload`. Cada archivo conserva su checkpoint e historial aunque cambies de pestaña o cierres Lumen. No copies estructuras nativas entre arquitecturas sin una migración. Python dispone de `lantern_state` y `lantern_checkpoint()`; JavaScript/TypeScript de `lanternState` y `lanternCheckpoint()`.

El IDE no guarda indiscriminadamente todas las variables: el programa decide qué estado es coherente y persistente. Esta colaboración conserva datos reales entre ejecutables distintos y permite evolucionar su formato de manera comprobable.
