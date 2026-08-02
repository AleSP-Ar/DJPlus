# Import Engine Design — v0.6.1

## Implementado

El motor funciona sin UI y procesa cada archivo en este flujo:

```text
ScannerService -> MetadataService -> ImportQueue -> ImportService
                                                   -> TrackImportService
                                                   -> UnitOfWork / SQLite
```

- `ScannerService` descubre extensiones configuradas y emite eventos progresivos.
- `normalize_filepath()` convierte rutas a una forma absoluta normalizada. El lookup reconoce también registros relativos heredados de v0.5.0.
- `MetadataService` usa Mutagen y devuelve metadata normalizada sin persistirla.
- `ImportRepository` persiste jobs, items, progreso y errores seguros de hasta 500 caracteres.
- `ImportWorker` ejecuta el servicio en un hilo y expone eventos de datos.
- `TrackImportService` crea tracks, omite snapshots intactos o actualiza metadata derivada del archivo. Sólo una creación añade un evento `added`.
- `UnitOfWork` confirma juntos track, history e ImportItem; una excepción revierte toda la operación del item.

## Migraciones

El esquema usa únicamente migraciones versionadas:

1. `0001_baseline_schema`: esquema v0.5.
2. `0002_import_engine`: `import_jobs` e `import_items`.
3. `0003_track_import_snapshots`: metadata y snapshots en `tracks`.

Una DB nueva y una DB v0.5.0 actualizada terminan con las tres versiones. `Base.metadata.create_all()` se limita a fixtures de prueba.

## Reglas de datos

| Condición | Resultado |
|---|---|
| filepath inexistente | crea Track + `added` + item `imported` |
| mismo filepath, tamaño y mtime iguales | item `skipped`; no modifica la biblioteca |
| mismo filepath, snapshot diferente | actualiza metadata importada; item `imported` |
| metadata o archivo inválido | item `failed`; continúa el job |

Rating, favoritos, energía, playlists, collections e historial no se sobrescriben. No se calcula hash ni se deduplican archivos por contenido.

## Futuro

- Adaptador UI/PySide para progreso y selección de carpeta.
- Política explícita de duplicados por contenido/hash.
- Paralelismo de workers tras medir contención SQLite.
