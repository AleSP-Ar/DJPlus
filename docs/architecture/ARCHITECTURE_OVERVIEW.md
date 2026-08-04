# Arquitectura DJPlus

### v0.21.0 - Global Ranking (Épica 19 cerrada)

`GlobalRankingService` streams explicit scalar columns from `TrackRepository` through `LibraryService`, retains only a top-K heap and orders ties by score, confidence and track ID. `ToolRegistry.default()` composes the global recommendation facade without UI dependencies; Set Builder may consume the same source and has a typed cooperative cancellation result. The next stage is backend freeze and final cleanup.

### Backend freeze — migration and lifecycle hardening

`DatabaseMigrationCoordinator` protects an existing historical database with a verified pre-action backup, disposes injected connections and returns a typed startup result. `BackupRestoreService` restores historical schemas through a preserved extraction and a second migration candidate, then validates SQLite integrity and foreign keys before individually atomic replacement. Imports are smoke-tested in fresh subprocesses without creating user files. SQLite DDL can be partially retained after a failure, so the recorded migration history and verified recovery backup—not an unproven global rollback—are the safety guarantees.

### v0.20.0 - Preview Player (Épica 18 cerrada)

La preescucha local se organiza como `PreviewPlayerService` sobre `AudioPlaybackBackendProtocol`. El adaptador Qt encapsula multimedia, el backend determinista sirve a pruebas sin audio y `PreviewPlayerBar` consume únicamente el servicio. La composición inyecta Settings e historial, mientras MainWindow conserva el ciclo de vida. La próxima etapa es Épica 19 — Global Ranking & DJ Integration.

### Preview Player Core (Épica 18.1)

`PreviewPlayerService` es una frontera de servicios sin widgets: depende sólo de `AudioPlaybackBackendProtocol`, expone snapshots inmutables y recibe callbacks de eventos. `QtMultimediaPlaybackBackend` encapsula los objetos Qt y `DeterministicPlaybackBackend` permite pruebas sin salida audible. La UI no compone ni controla aún este servicio; futuros consumidores deberán respetar el hilo Qt y cerrar el servicio antes de liberar la aplicación.

Version 0.19.0 closes Epic 17: `SettingsService` owns versioned preferences, `AppLoggingService` owns local structured diagnostics, and `BackupRestoreService` owns verified local recovery packages. Their composition remains outside the UI and uses injected paths, loggers and database lifecycle callbacks.

Epic 19.1 adds an optional read-only global-ranking path beneath the existing recommendation boundary. `TrackRepository` streams scalar ranking fields to `LibraryService`; `GlobalRankingService` applies the unchanged score engine with bounded top-K state; `RecommendationFacade` preserves its public page DTO and `ToolRegistry.default()` composes the global factory when dependencies are available. The Set Builder may use the same source and returns a typed cancellation outcome rather than a partial final set.

Sprint 18.2 extends preview composition with `AudioOutputDeviceDTO` instead of Qt device objects, Settings schema 3 preferences and `PlaybackHistoryPortProtocol`. Device fallback is configured ID, description, default output and controlled degraded state. MainWindow only owns optional lifecycle; it has no `QMediaPlayer`, `QAudioOutput` or playback UI.

Sprint 18.3 adds `PreviewPlayerBar` under `app/ui/widgets/`. The widget consumes only `PreviewPlayerService` events through a Qt signal and renders the persistent bottom controls. `LibraryView` emits the active model row through an explicit load button, while MainWindow adapts it without another library lookup. The UI owns no multimedia object and does not record history.

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
