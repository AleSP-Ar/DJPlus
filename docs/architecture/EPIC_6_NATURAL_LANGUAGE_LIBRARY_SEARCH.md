# Epic 6 - Natural Language Library Search

`LibraryQueryTool` incorpora un intérprete determinista de lenguaje natural. No usa modelo, SQL generado, Repository ni acceso a SQLite. El resultado es un `NaturalLibraryQueryDTO` validado y la ejecución se delega exclusivamente a `LibraryService.query()` y `LibraryService.count_results()`.

Filtros admitidos y combinables: BPM exacto, mínimo, máximo o rango; tonalidad (`key 8A` / `tono Am`); rating de 1 a 5; favoritos o no favoritos; género; y texto libre entre comillas o con `buscar`/`texto`.

Ejemplos:

- `"Sunset" género house BPM entre 120 y 128 key 8A mínimo 4 estrellas favoritos`
- `buscar techno menos de 130 BPM no favoritos rating 5`

Si se menciona un filtro pero no puede interpretarse, la herramienta devuelve una respuesta explicativa tipada y no consulta el servicio. No genera propuestas ni acciones; todas las salidas permanecen en modo solo lectura.

## Prueba manual

Desde el panel local, solicitar una consulta de los ejemplos anteriores. Comprobar que Ollama invoque únicamente `library_query`, que la respuesta muestre el total encontrado y que no aparezcan propuestas de acción. Probar `bpm muy rápido`: debe explicar el formato requerido, sin alterar la biblioteca.
