# Arquitectura DJPlus

## Visión general

DJPlus está organizado para separar claramente:
- la base de datos,
- la lógica de acceso a datos,
- los servicios,
- y la interfaz gráfica.

## Estructura propuesta

- app/database/: configuración de SQLAlchemy y modelos.
- app/repository/: acceso centralizado a las pistas.
- app/services/: lógica de negocio y procesamiento.
- app/ui/: vistas, widgets y diálogos.
- app/utils/: utilidades compartidas.

## Flujo de datos

1. El escáner lee archivos de audio.
2. Se almacenan en SQLite mediante los modelos.
3. La UI consulta los datos a través de repositories y servicios.
4. La biblioteca muestra los resultados en la interfaz.

## Base de datos

La base local se gestiona con SQLite y SQLAlchemy. La tabla principal es tracks.

## Repository

Los repositories encapsulan las consultas a la base de datos para evitar duplicar lógica.

## Servicios

Los servicios contienen operaciones más complejas como escaneo, análisis y preparación de datos.

### Music Analysis Engine v0.14.0

El análisis local se separa en `MusicAnalysisFacade` (consulta filas mediante `LibraryService`), `MusicAnalysisService` (lectura WAV PCM) y `MusicAnalysisWorker` (lote, progreso, concurrencia y cancelación cooperativa). Los DTOs de análisis existen sólo en memoria: no actualizan pistas ni metadata. La herramienta opcional `MusicAnalysisBatchTool` es read-only y el panel sólo presenta sus resultados ya calculados.

El soporte actual es WAV PCM. BPM y key pueden ser `None` con confianza insuficiente; modulaciones, mezclas complejas y nombres enarmónicos están fuera de alcance.

### Duplicate Detection v0.17.0

`DuplicateDetectionService` receives tracks only through `LibraryService` and calculates SHA-256 in blocks. It does not import Repository or SQLite directly and never performs file actions. Its groups are deterministic, and recoverable bytes estimate retaining one copy per group.

`FingerprintCache` keys a fingerprint with filepath, size and `mtime_ns`, so any changed snapshot becomes a cache miss. `DuplicateDetectionFacade` reuses the cache and renders text; `DuplicateDetectionWorker` reports progress and cooperative cancellation. The allowlisted tool remains read-only and `MainWindow` only composes the facade optionally. A dedicated visual panel is not part of this release; initial uncached scans of large libraries are linear and I/O-bound.

## UI

La interfaz se organiza en vistas y widgets reutilizables. La idea es que la capa visual dependa de repositorios y servicios, no de consultas directas a la base.
