# Virtual Library Design — Sprint 5.3

La biblioteca usa `QAbstractTableModel.canFetchMore()` y `fetchMore()` para cargar inicialmente 200 filas y añadir lotes posteriores bajo demanda. `LibraryService` mantiene el estado de consulta y expone páginas; `TrackRepository` ejecuta SQLite con `LIMIT/OFFSET`. La UI no calcula offsets, SQL ni límites.

`LIMIT/OFFSET` ofrece una transición segura y suficiente para la primera Virtual Library. Para 100.000–250.000 pistas, el cursor opaco de `LibraryService` evolucionará a keyset pagination (`ORDER BY` determinista + último valor + id), porque los offsets profundos se degradan. Búsqueda, orden y filtros reinician la consulta y reemplazan el modelo; el scroll solicita más resultados sin cambiar la arquitectura.

## Sprint 5.3 decision

The implementation uses `LIMIT/OFFSET` for its first pagination strategy. It preserves the existing service API, restarts at the first page for every search, filter, or sort, and uses `id` as a deterministic tie-breaker. SQLite cursors are deliberately not held open between batches: that would extend transaction lifetime and make query resets fragile. Each batch is an independent, short query.

The Qt model retains rows that the user has already traversed, as required by `QAbstractItemModel`; the improvement is that opening the library does not materialize every row. A future windowed model would be required only if memory must stay strictly bounded after a user has navigated the entire library.
