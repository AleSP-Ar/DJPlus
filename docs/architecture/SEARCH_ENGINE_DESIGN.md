# SearchEngine Design

`SearchEngine` normaliza solicitudes de búsqueda y crea un contrato tipado para `LibraryService`. No importa Qt, no abre sesiones y no ejecuta SQL.

```text
UI intención → LibraryService → SearchEngine normaliza → TrackRepository consulta SQLite
```

API inicial: `build(text, artist, title, album, genre, bpm, key, rating, date_added)`. El texto libre se aplica a artista, título y álbum; los campos estructurados quedan preparados para el modelo actual y columnas futuras. La ejecución corresponde a `TrackRepository` mediante consultas parametrizadas.

Ventajas: UI libre de SQL, validación centralizada y evolución directa hacia FTS5 o ranking. Futuras ampliaciones: prefijos, tokens, historial de búsqueda y búsqueda semántica sin alterar la UI.
