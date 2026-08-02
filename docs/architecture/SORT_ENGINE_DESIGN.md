# SortEngine Design

`SortEngine` valida la columna y dirección solicitadas y entrega un `SortSpec` a `LibraryService`. Solo permite una lista cerrada: title, artist, album, genre, bpm, key, rating y date_added.

```text
UI sort(column, direction) → LibraryService → SortEngine → TrackRepository ORDER BY seguro
```

El repositorio traduce el contrato a SQLAlchemy/SQLite y agrega `id` como desempate estable. `date_added` se mapea temporalmente a `created_at`; `genre` quedará disponible al existir esa columna. Ventajas: elimina el ordenamiento global pesado de Qt, habilita índices y prepara paginación por cursor.
