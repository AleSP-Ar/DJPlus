# Arquitectura DJPlus

Version 0.19.0 closes Epic 17: `SettingsService` owns versioned preferences, `AppLoggingService` owns local structured diagnostics, and `BackupRestoreService` owns verified local recovery packages. Their composition remains outside the UI and uses injected paths, loggers and database lifecycle callbacks.

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

### SettingsService (Épica 17)

`SettingsService` es la única frontera persistente de preferencias. Entrega `AppSettingsDTO` inmutable y versionado, usa `%APPDATA%\DJPlus\config.json` por defecto y acepta una ruta inyectada para pruebas. Las secciones general, biblioteca, análisis, FFmpeg, asistente, logging y backup validan campos desconocidos antes de guardarse mediante reemplazo atómico. El servicio no guarda credenciales, no depende de UI ni modifica `MainWindow`.

La configuración se adapta de manera opcional a `FFmpegResolver`, `ExecutionHardeningConfigDTO`, `MusicAnalysisService` y `ProviderConfigDTO`, preservando sus constructores existentes. `AppLoggingService` consume ahora la sección `LoggingSettingsDTO` de manera explícita; backup sigue siendo sólo una preferencia preparada.

### Structured logging and diagnostics (Épica 17)

`AppLoggingService` es el dueño único de un handler rotativo JSONL para la jerarquía `djplus`. `app.main` lo compone, instala de forma explícita hooks de excepciones y lo cierra durante el shutdown. Settings, FFmpeg, análisis, workers, asistente y migraciones usan loggers jerárquicos y nunca configuran handlers. `StructuredLogSanitizer` elimina secretos y rutas sensibles con límites de profundidad/tamaño; la exportación diagnóstica atómica incluye sólo configuración, capacidades y logs recientes sanitizados. `DiagnosticsService` mantiene su rol de métricas read-only y no duplica esta persistencia de soporte.

### Backup and restore (Épica 17)

`BackupRestoreService` compone `SettingsService`, `BackupSettingsDTO`, la ruta SQLite y un logger jerárquico inyectados. `app.database.create_backup_restore_service()` aporta la composición canónica y dispone el engine antes de restore; no ejecuta operaciones automáticamente. Cada ZIP usa la API SQLite de backup, `integrity_check`, manifiesto estricto y checksums. La restauración es una operación explícita de plan/token con backup `pre_action`, verificación reiterada, extracción privada y reemplazo atómico por archivo. Media, rutas de biblioteca, ejecutables, logs completos y secretos quedan fuera del paquete.

### Multi-format Music Analysis v0.18.0

El análisis local se separa en `MusicAnalysisFacade` (consulta filas mediante `LibraryService`), `MusicAnalysisService` (lectura WAV PCM) y `MusicAnalysisWorker` (lote, progreso, concurrencia y cancelación cooperativa). Los DTOs de análisis existen sólo en memoria: no actualizan pistas ni metadata. La herramienta opcional `MusicAnalysisBatchTool` es read-only y el panel sólo presenta sus resultados ya calculados.

`AudioDecoderProtocol` y `AudioDecoderRegistry` separan el análisis de los decoders y establecen el orden público MP3, FLAC, AIFF/AIF y WAV. WAV/AIFF/AIF PCM se leen con decoders nativos por bloques. `MultiFormatAudioAnalysisFacade` registra opcionalmente `FFmpegAudioDecoder` para MP3/FLAC, detecta contenido antes que extensión, publica diagnóstico y procedencia por item, y conserva exportación read-only.

`FFmpegResolver` prioriza ruta configurada, PATH y `runtime/ffmpeg/ffmpeg.exe`. El último sólo se ejecuta tras verificar su SHA-256 en `CHECKSUM.sha256`; `FFmpegCapabilityProbe` verifica localmente versión y decoders MP3/FLAC. No se descarga, instala ni modifica PATH. El runtime es Windows x64 de aproximadamente 114.9 MB, se mantiene fuera de Git y debe ser incorporado por el empaquetador tras verificar los manifiestos locales de licencia, origen y checksum. BPM y key pueden ser `None` con confianza insuficiente; modulaciones, mezclas complejas y nombres enarmónicos están fuera de alcance.

### Duplicate Detection v0.17.0

`DuplicateDetectionService` receives tracks only through `LibraryService` and calculates SHA-256 in blocks. It does not import Repository or SQLite directly and never performs file actions. Its groups are deterministic, and recoverable bytes estimate retaining one copy per group.

`FingerprintCache` keys a fingerprint with filepath, size and `mtime_ns`, so any changed snapshot becomes a cache miss. `DuplicateDetectionFacade` reuses the cache and renders text; `DuplicateDetectionWorker` reports progress and cooperative cancellation. The allowlisted tool remains read-only and `MainWindow` only composes the facade optionally. A dedicated visual panel is not part of this release; initial uncached scans of large libraries are linear and I/O-bound.

## UI

La interfaz se organiza en vistas y widgets reutilizables. La idea es que la capa visual dependa de repositorios y servicios, no de consultas directas a la base.
