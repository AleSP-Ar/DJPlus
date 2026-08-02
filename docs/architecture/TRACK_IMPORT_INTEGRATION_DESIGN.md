# Track Import Integration Design — v0.6.1

## Implementado

`TrackImportService` procesa un `ImportItem` con un `UnitOfWork` propio. `TrackRepository`, `HistoryRepository` e `ImportRepository` comparten sesión y confirman una sola vez.

| Caso | Track | History | ImportItem |
|---|---|---|---|
| nuevo filepath normalizado | crea con metadata y snapshot | agrega `added` | `imported` |
| snapshot intacto | sin escritura | sin cambios | `skipped` |
| snapshot modificado | refresca metadata importada | sin cambios | `imported` |
| error | rollback de la operación | rollback | `failed` en recuperación separada |

La metadata importada incluye title, artist, album, genre, BPM, key, duration, bitrate y sample rate. Los snapshots usan tamaño y hora de modificación normalizada a UTC.

La identidad se basa sólo en filepath normalizado. La consulta considera también el equivalente relativo al directorio de trabajo para reconocer tracks v0.5.0 creados por el escáner heredado. No se usa `file_hash`.

## Compatibilidad

Las migraciones son aditivas y preservan pistas, rating, favoritos, playlists, collections e historial. Una actualización desde v0.5.0 termina con `0001_baseline_schema`, `0002_import_engine` y `0003_track_import_snapshots`.

## Futuro

- UI de importación y adaptador de señales PySide.
- Hashing y reglas de duplicado por contenido.
- Tolerancia de timestamps sólo si una medición real la justifica.
