# DJPlus

DJPlus v0.17.0 es una biblioteca musical local para DJs, basada en PySide6, SQLAlchemy y SQLite.

Estado: v0.17.0 preparada como release candidate; el commit y tag requieren aprobación explícita.

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

La versión de aplicación se centraliza en `app/version.py`.
