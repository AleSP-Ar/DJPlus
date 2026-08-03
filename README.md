# DJPlus

DJPlus v0.20.0 es una biblioteca musical local para DJs, basada en PySide6, SQLAlchemy y SQLite.

Estado: v0.20.0 preparada para publicación local. El binario FFmpeg se conserva localmente y se incorpora durante el empaquetado del instalador, no en Git.

## Capacidades v0.20.0

- Épica 18 cierra el Preview Player local: backend Qt aislado, backend determinista sin audio, dispositivos serializados, Settings schema 3 y registro `played` una vez por carga confirmada.
- `PreviewPlayerBar` ofrece carga explícita desde la fila activa de biblioteca, transporte, seek, volumen privado, selección de salida, estados y errores seguros. No hay autoplay ni rutas visibles.
- El modo degradado mantiene DJPlus y la biblioteca operativos sin Qt Multimedia o sin dispositivo. Waveform, mezcla, pitch, tempo y el rediseño visual definitivo permanecen fuera de alcance.

- `SettingsService` centraliza preferencias inmutables y versionadas, con migracion `1 -> 2`, validacion estricta, recuperacion controlada y escritura JSON atomica fuera del repositorio.
- `AppLoggingService` escribe eventos JSON Lines locales, rotativos y sanitizados; soporta hooks explicitos, reconfiguracion segura y diagnosticos atomicos con checksum.
- `BackupRestoreService` crea ZIPs locales verificables mediante SQLite Backup API, manifest/checksums, retencion y restauracion confirmada con backup preventivo obligatorio.
- Los backups no incluyen archivos musicales, rutas de biblioteca, secretos, prompts, logs completos ni `ffmpeg.exe`. No hay UI, scheduler, copia remota ni backup de medios en esta version.

## Preview Player Core (Épica 18.1)

- `PreviewPlayerService` ofrece preescucha local mediante un protocolo de backend: cargar, reproducir, pausar, reanudar, detener, seek, volumen, estado y cierre seguro.
- `QtMultimediaPlaybackBackend` encapsula `QMediaPlayer` y `QAudioOutput`; el backend determinista permite pruebas headless sin emitir audio. Soporta inicialmente MP3, FLAC, AIFF/AIF y WAV según codecs de Qt/sistema.
- Este sprint no agrega controles visuales, reproducción automática, historial persistente, mezcla ni funciones DJ. Consulte [PREVIEW_PLAYER_CORE_DESIGN.md](docs/architecture/PREVIEW_PLAYER_CORE_DESIGN.md).

## Preview Player â€” Sprint 18.2

- La salida de preescucha se representa con IDs serializados y aplica fallback de ID configurado a descripciÃ³n, salida predeterminada y finalmente estado degradado. No cambia el dispositivo global de Windows.
- Settings schema 3 guarda explÃ­citamente volumen privado (por defecto `.70`) y preferencia de salida. La historia `played` se escribe una vez por carga sÃ³lo tras `PLAYING` confirmado; una falla de historial no interrumpe reproducciÃ³n.
- `MainWindow` recibe y cierra el servicio opcional sin controles visuales ni referencias directas a Qt Multimedia. Consulte `docs/architecture/PREVIEW_PLAYER_CORE_DESIGN.md`.

## Preview Player Visual (Epic 18.3)

- `PreviewPlayerBar` is a persistent functional bottom control bar: explicit load from the active library row, play/pause, stop, seek, elapsed time, private volume, output selection and safe state/error feedback.
- It uses only `PreviewPlayerService`; it does not autoplay on selection, expose file paths or create Qt multimedia objects. Device preferences are explicit and degraded operation keeps the library usable.
- The current UI is functional rather than the final visual redesign. Waveform, artwork, mixing and DJ controls remain pending. See `docs/architecture/PREVIEW_PLAYER_VISUAL_INTEGRATION.md`.

## Capacidades v0.18.0

- El orden oficial de formatos es MP3, FLAC, AIFF/AIF y WAV; MP3 es el formato predeterminado. La detección se hace por contenido antes que por extensión.
- `AudioDecoderProtocol` y `AudioDecoderRegistry` separan el análisis de los decoders. `WAVPCMDecoder` y `AIFFPCMDecoder` procesan PCM nativo por bloques, con memoria acotada y cancelación cooperativa.
- `FFmpegAudioDecoder` habilita MP3 y FLAC locales por stdout PCM, sin archivos temporales. `FFmpegResolver` prioriza ruta configurada, PATH y luego `runtime/ffmpeg/ffmpeg.exe`; no modifica PATH ni instala o descarga software.
- `FFmpegCapabilityProbe` valida versión y decoders MP3/FLAC. El runtime bundled se acepta sólo si `CHECKSUM.sha256` verifica `ffmpeg.exe`.
- `MultiFormatAudioAnalysisFacade` conserva resultados read-only, exportación textual y diagnóstico de formato, decoder, procedencia y capacidades. `MainWindow` lo compone opcionalmente y no inicia análisis automáticos.
- El runtime local actual es Windows x64, BtbN/FFmpeg-Builds `autobuild-2026-08-02-13-17`, LGPL v3, con `ffmpeg.exe` de 114.9 MB. El ejecutable está ignorado por Git: el desarrollador debe colocarlo en `runtime/ffmpeg/` y el instalador final debe incorporarlo tras verificar su checksum. Los manifiestos versionados fijan origen, versión, licencia y hashes; ver [FFMPEG_DISTRIBUTION_AND_LICENSES.md](docs/architecture/FFMPEG_DISTRIBUTION_AND_LICENSES.md).

## Capacidades v0.17.0

- `DuplicateDetectionService` calculates block-wise SHA-256 through `LibraryService`, groups matches deterministically and isolates file errors.
- `FingerprintCache` reuses fingerprints by filepath, size and `mtime_ns`; a size or timestamp change safely invalidates the cache entry.
- `DuplicateDetectionFacade` provides textual export, while `DuplicateDetectionWorker` reports progress and supports cooperative cancellation without modifying the library.
- `DuplicateDetectionTool` is optional, allowlisted and read-only. `ToolRegistry.default()` initializes base tools before optional extensions.
- `MainWindow` optionally composes the duplicate facade without automatic scans. A dedicated visual panel remains pending.
- No files are deleted, moved, renamed or modified. Recoverable bytes estimate keeping one copy per group; hashing uncached large libraries is I/O-bound and linear in scanned bytes. A cache miss currently delegates the selected scan to canonical hashing.

## Capacidades v0.16.0

- Backend Boundary Cleanup: APIs canónicas, compatibilidad legacy aislada y roadmap histórico señalado.
- `TrackMetadataEditorService` permite patches individuales y masivos, preview determinista, confirmación y restauración.
- Historial durable por pista mediante `0005_track_metadata_history`, `TrackMetadataFacade` y herramientas preview/apply.
- `TrackMetadataPanel` se integra opcionalmente en `MainWindow`. La UI mínima hoy sólo expone título e IDs separados por coma.

## Capacidades v0.15.0

- `AnalysisChangePlanner` compara BPM, key y energía con políticas `never_overwrite`, `overwrite_lower_confidence` y `force`, y produce una vista previa determinista explicable.
- `AnalysisPersistenceService` exige propuesta y confirmación en `ActionPipeline`, aplica cambios atómicos por pista y permite respaldo/restauración transitorios.
- La migración `0004_analysis_provenance` agrega procedencia nullable: fecha, versión del analizador y confianzas por campo; las pistas antiguas conservan `NULL`.
- `AnalysisChangePreviewTool` sólo muestra el plan. No se agrega UI en esta versión; lotes aíslan el resultado de cada pista.

## Capacidades v0.14.0

- `MusicAnalysisService` inspecciona WAV PCM locales de forma determinista: duración, sample rate, canales, peak, RMS y energía normalizada.
- BPM se estima por envolvente y picos, con confianza explicable; la tonalidad usa perfil cromático y plantillas mayor/menor con confianza explicable.
- `MusicAnalysisFacade` realiza análisis read-only por lote desde `LibraryService`, aislando errores por archivo y sin actualizar metadata.
- `MusicAnalysisWorker` aporta progreso, límite de concurrencia, cancelación y cierre cooperativos; `MusicAnalysisBatchTool` devuelve resultados y exportación textual sin acciones.
- `AssistantPanel` puede mostrar filas de análisis cuando la herramienta se registra opcionalmente.
- El soporte actual se limita a WAV PCM. BPM y key pueden ser `None`; no se resuelven modulaciones, mezclas complejas ni nombres enarmónicos.

- `SetPlanningEngine` con políticas deterministas de saltos BPM y energía.
- `EnergyJourneyPlanner` con curvas ascending, descending y arc; fases warm-up, build, peak y cooldown.
- `SetBuilderFacade` y `SetBuilderTool` read-only con candidatas de `LibraryService`, exclusión de historial y exportación a texto.
- Integración opcional de secuencias en `AssistantPanel`, sin persistir ni crear playlists.

- Cachés locales acotadas y profiling interno por etapa, sin cachear resultados ni datos vivos.
- Hardening cooperativo: timeout opcional, cancelación, límites de concurrencia y cierre seguro.
- `DiagnosticsService` y `DiagnosticsTool` read-only, con exportación local sin secretos ni histórico.
- Resumen compacto de diagnóstico opcional en `AssistantPanel`.

- Recommendation Scoring Engine explicable por BPM, key, energía e historial.
- Ranking determinista por score, confianza e ID de pista como desempate.
- RecommendationFacade con filtros de candidatos y exclusión por historial reciente.
- `RecommendationTool` de solo lectura y presentación de resultados en `AssistantPanel`.
- El ranking actual se calcula por página de candidatos; no es un ranking global de toda la biblioteca.

- Tool Planner determinista con múltiples llamadas ordenadas y dependencias explícitas entre pasos.
- Tool Plan Executor basado exclusivamente en `ToolDispatcher`, con estados `success`, `failed` y `blocked`.
- Tool Result Composer para resúmenes estructurados, ordenados y deterministas de planes completos, parciales o fallidos.
- Integración opcional de planificación, ejecución y composición en `AssistantRuntime`.

- AI Provider Infrastructure con contratos, registro, configuración, resiliencia, credenciales redactadas y transportes mock/locales.
- Tool Calling Framework con schemas validados y herramientas de biblioteca acotadas a Services.
- Execution Framework simulado, con confirmación, autorización, idempotencia, auditoría y rollback tipado; no ejecuta escrituras reales.
- Asistente local Ollama restringido a `http://localhost:<puerto>`, con timeout, cancelación, worker Qt y panel PySide6 no bloqueante.
- Búsqueda natural de biblioteca por texto, BPM, tonalidad, rating, favoritos y género, con filtros compuestos y paginación mediante `LibraryService`.

## Capacidades heredadas

- Biblioteca virtual con carga incremental, búsqueda, filtros y ordenamiento SQLite.
- Colecciones manuales, playlists ordenadas, favoritos e historial de actividad.
- Smart Collections basadas en reglas AND compatibles con los filtros actuales.
- Migraciones SQLite idempotentes y versionadas desde la línea base v0.5.
- Import Engine sin UI: descubrimiento, metadata, cola persistente, worker y transacciones atómicas por pista.
- Reimportación por filepath normalizado: crea, omite archivos intactos o refresca metadata sin modificar datos de usuario.
- AI Runtime independiente del proveedor: `AssistantRuntime`, `PromptBuilder`, `ToolRegistry` y `ToolDispatcher` separan el flujo interno de futuros proveedores como OpenAI, Ollama o modelos locales.
- Sesiones conversacionales locales y efímeras, sin memoria persistente ni acceso directo a SQLite, ORM, repositorios o filesystem.
- Action Pipeline y Confirmation Manager: las herramientas sólo generan propuestas inmutables, auditables y sujetas a confirmación; no ejecutan acciones de escritura.
- Auditoría arquitectónica y ADRs para límites del Runtime, herramientas, conversaciones, propuestas y políticas de confirmación.

## Arquitectura

La UI utiliza Services, que coordinan Repositories y motores de consulta. El Runtime de IA es una capa de servicios aislada y basada en DTOs; no conoce proveedores de IA ni infraestructura de persistencia. La documentación completa está en [DJPLUS_ARCHITECTURE.md](docs/architecture/DJPLUS_ARCHITECTURE.md) y [AI_RUNTIME_IMPLEMENTATION.md](docs/architecture/AI_RUNTIME_IMPLEMENTATION.md).

## Requisitos

```bash
pip install -r requirements.txt
```

## Uso

```bash
python -m app.main
```

No se requiere ni se realiza una descarga de FFmpeg en tiempo de ejecución. Para actualizar el runtime, seguir el procedimiento obligatorio documentado en `runtime/ffmpeg/SOURCE.txt`, verificar el ZIP antes de extraer, actualizar los manifiestos y ejecutar las pruebas reales MP3/FLAC. El proceso de empaquetado debe comprobar el checksum de `ffmpeg.exe` antes de incluirlo en el instalador.

## Configuración local

`SettingsService` es la frontera canónica de preferencias persistentes. Por defecto usa `%APPDATA%\DJPlus\config.json` en Windows; no guarda credenciales y realiza escrituras JSON atómicas con migraciones versionadas. Las pruebas inyectan una ruta temporal. La configuración puede preparar FFmpeg, límites de análisis y preferencias no secretas del asistente, pero no crea todavía una pantalla de Settings.

## Logging y diagnóstico local

`AppLoggingService` consume explícitamente `LoggingSettingsDTO` y escribe JSON Lines rotativos en `%APPDATA%\DJPlus\logs` por defecto. Cada evento contiene hora UTC, nivel, componente, versión, proceso e hilo; los contextos son pequeños y sanitizados. Claves de credenciales, tokens, prompts, rutas musicales y ejecutables se redactan. La exportación diagnóstica es atómica, acotada y con SHA-256; incluye configuración y capacidades sanitizadas, no la biblioteca, base de datos, audio ni binarios. Consulte [LOGGING_AND_DIAGNOSTICS_DESIGN.md](docs/architecture/LOGGING_AND_DIAGNOSTICS_DESIGN.md).

## Backup y restauración local

`BackupRestoreService` crea ZIPs verificables con una copia consistente SQLite, configuración portable sanitizada, manifiesto y checksums. La restauración exige plan, token de confirmación y un backup preventivo verificado; no existe aún UI ni tarea programada. No se incluyen música, rutas de biblioteca, logs completos, credenciales ni FFmpeg. Consulte [BACKUP_AND_RESTORE_DESIGN.md](docs/architecture/BACKUP_AND_RESTORE_DESIGN.md).

La versión de aplicación se centraliza en `app/version.py`.
