# API ejecutable preview de Lumen

El VSIX incluye `extension/package.json` con `publisher`, `name`, `version` y `main` apuntando a un archivo `.js`, `.cjs` o `.mjs`. Exporta `activate(context, lumen)`. En CommonJS también está disponible `require('lumen')`.

```js
exports.activate = (context, lumen) => {
  lumen.registerCommand('uppercase', document => ({
    text: document.text.toUpperCase()
  }), 'Convertir a mayúsculas');
  lumen.registerCompletionProvider('python', document => [
    {label: 'saludar', insertText: 'print("Hola")'}
  ]);
  lumen.registerInlayHintsProvider('python', document => [
    {position: {line: 0, character: 4}, label: ': int'}
  ]);
  lumen.registerDefinitionProvider('python', document => [{
    path: 'otro.py',
    range: {start: {line: 0, character: 0}, end: {line: 0, character: 8}}
  }]);
};
```

Un documento contiene `path` relativa al proyecto, `text` con el búfer actual y `language`. Las posiciones de la API usan líneas y caracteres desde cero. Un comando puede devolver `{text}` para abrir una propuesta revisable, o texto para notificar. `lumen.notify(text)` muestra un aviso al terminar el comando.

`registerDiagnosticsProvider(language, fn)` devuelve diagnósticos Lumen con `line`, `column`, `endLine`, `endColumn`, `message` y `severity` (`error` / `warning`), desde uno. `registerTokens(language, rules)` recibe reglas `{pattern, flags, token}` compatibles con Monarch.

Se admiten proveedores síncronos o async. No bloquees el proceso durante más de diez segundos. La entrada/salida del protocolo está reservada; usa `console.log` para el registro de la extensión, que se redirige a stderr. No escribas directamente a stdout.

`require('vscode')` tiene un subconjunto de comandos, documento activo, notificaciones, completado, definición, hints, tipos Position/Range/Uri y workspaceFolders. Otras APIs no están implementadas. Las extensiones de navegador y las que requieren el host completo de VS Code necesitan una adaptación. El proceso es terminable e independiente de la interfaz, pero tiene acceso al equipo con los permisos del usuario; autoriza solo código de confianza.
