# FilterEngine Design

`FilterEngine` construye filtros estructurados combinables: género, rango BPM, key, rating y fechas. Valida rangos y representa una condición AND que `LibraryService` entrega al repositorio.

```text
UI filtros → LibraryService → FilterEngine → TrackRepository WHERE parametrizado
```

API inicial: `build(genre, bpm_min, bpm_max, key, rating_min, rating_max, date_added_from, date_added_to)`. Los filtros sin columna física aún (por ejemplo genre) están preparados en el contrato y se rechazan explícitamente hasta que una migración los habilite. Esto evita resultados silenciosamente incorrectos y prepara Smart Collections futuras.
