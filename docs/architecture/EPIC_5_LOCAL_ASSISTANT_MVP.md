# Epic 5 - MVP Asistente Local

## Alcance y seguridad

El MVP usa `LocalAssistantMVP` para construir un flujo de solo lectura: consulta del usuario -> `AssistantRuntime` -> `OllamaProvider` -> `LibraryQueryTool` -> respuesta y resultado visible en `AssistantPanel`.

`LocalhostHTTPProviderTransport` usa exclusivamente la biblioteca estándar de Python y acepta únicamente URLs `http://localhost:<puerto>`. Rechaza antes de conectar cualquier host, esquema, credencial embebida o URL sin puerto. No usa SDKs, secretos, variables de entorno obligatorias, `requests` ni `httpx`.

`LocalAssistantConfigDTO` declara explícitamente la URL local, el modelo y el timeout. El token de cancelación se revisa de forma cooperativa antes de abrir la conexión; el timeout se entrega al socket y sus errores se devuelven tipados.

La única herramienta registrada por este MVP es `LibraryQueryTool`. Es de solo lectura, accede únicamente a `LibraryService.count_tracks()` y no genera propuestas ni acciones.

## Prueba manual con Ollama

1. Iniciar Ollama local y disponer de un modelo, por ejemplo `ollama run llama3.2`.
2. Componer el panel con `AssistantPanel(LocalAssistantMVP(library_service))` dentro de la aplicación PySide6.
3. Consultar “¿Cuántas pistas hay en mi biblioteca?”.
4. Verificar que la respuesta muestra el texto del modelo y el resultado de `LibraryQueryTool`.
5. Probar una URL distinta de `http://localhost:puerto`: la configuración debe rechazarla. No se debe realizar una conexión externa.

Las pruebas automatizadas no requieren Ollama: usan `MockProviderTransport` y verifican payload, modelo, tool call, cancelación y bloqueo de endpoints externos.

## Cierre: UI no bloqueante

`AssistantPanel` ejecuta cada consulta mediante `AssistantWorker` en un `QThread`. El worker emite `started`, `result`, `error`, `cancelled` y `finished`; el panel muestra el estado, deshabilita temporalmente Enviar y habilita Cancelar. Cancelar activa el token cooperativo ya soportado por el runtime y el transporte. Al cerrar, el panel solicita cancelación y sólo acepta el cierre cuando el hilo terminó de forma segura.

La prueba manual adicional es iniciar una consulta contra un Ollama local lento, comprobar que la ventana sigue respondiendo, pulsar **Cancelar** y verificar el estado “Cancelada”. Al cerrar durante una consulta, la ventana debe esperar la finalización segura sin abortar el hilo.

El benchmark automatizado ejecuta 50 consultas con `MockProviderTransport` y verifica que el worker entrega resultados sin espera de red. Es una prueba de regresión básica, no una medición de rendimiento de Ollama.
