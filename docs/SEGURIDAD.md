# Seguridad y permisos · Preview R5

## Modelo

Servicio limitado a loopback, validación de Host/Origin/Sec-Fetch-Site, cookie de sesión HttpOnly/SameSite y token para la API. No es un servidor para exponerse a Internet. Las rutas de archivos quedan dentro del proyecto y se comprueban conflictos antes de escribir. No hay una sandbox de sistema operativo para código autorizado.

Las PTY, tareas y servidores LSP exigen confianza explícita. Revocarla o cambiar de proyecto detiene los procesos administrados y cancela las respuestas activas. Las shells pueden acceder a recursos con tus permisos; cerrar el proceso principal no permite garantizar que cualquier programa malicioso haya desaparecido del sistema. Los procesos externos pueden ignorar, crear hijos o escapar de un grupo de procesos. No otorgues confianza a código desconocido.

## IA y credenciales

La nube está desactivada inicialmente. Cada envío se revisa; se envían la pregunta y el contexto aprobado, no todo el repositorio. Algunas rutas evidentes de claves (.env, .pem, id_rsa y similares) se bloquean como adjunto. Es una defensa adicional, no un clasificador infalible de secretos dentro de cualquier texto.

Credenciales en memoria, entorno existente o almacén seguro nativo admitido. Un backend keyring inseguro se rechaza. Los fallos de almacén no habilitan persistencia en texto plano. Los tokens de servicio no forman parte de las preferencias exportadas. Las variables conocidas de secretos se filtran del entorno heredado de las tareas; no se afirma aislamiento frente a un proceso ejecutado con los mismos permisos del usuario.

Los adaptadores envían datos solo a sus endpoints declarados; no siguen redirecciones con credenciales. Ollama se restringe a localhost/loopback y no utiliza el proxy del entorno. Copilot requiere su runtime y autenticación externos; la sesión se crea sin herramientas, con permisos rechazados y un directorio temporal.

Los límites de contexto, respuesta y tiempo reducen riesgos, pero no son un tope económico garantizado. Cancelar puede llegar después de que el proveedor haya procesado parte de la solicitud. Las políticas de los proveedores se aplican a los datos enviados.

## Extensiones

Aportaciones declarativas y motores Node opcionales autorizados explícitamente. Los motores ejecutan código con los permisos del usuario: el proceso separado no es una sandbox. Se valida el ZIP y el ticket de revisión de los mismos bytes. No hay análisis antivirus ni verificación criptográfica de identidad del publicador. Las APIs compatibles son parciales y se documentan en EXTENSIONES.md.

## Hardware

Métricas de lectura bajo activación expresa. No hay servicio con privilegios de kernel, drivers nuevos, control de ventiladores, frecuencia, energía o voltaje. La GPU solo se consulta por el mecanismo soportado cuando está disponible. El monitor no garantiza exactitud de un sensor ausente ni constituye una herramienta de diagnóstico profesional.

## Límites de auditoría

Las pruebas no reemplazan pentesting, revisión externa, análisis de dependencias, evaluación de recuperación ante fallos eléctricos o certificación de accesibilidad. Las limitaciones de transporte visual y los componentes no ejecutados se enumeran en `PREVIEW_R5.md`. No incluyas claves, prompts privados ni proyectos reales en incidencias o capturas de prueba.
