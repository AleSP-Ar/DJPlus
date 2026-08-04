# Development Log

## 2026-08-04 - v0.22.0 Backend Freeze & Hardening

- Se congelan las APIs canónicas y aliases históricos del backend tras auditoría de imports, migraciones, restore, lifecycle y recursos.
- No se modifican schema, scoring, integraciones externas ni diseño visual. La próxima etapa autorizada es la fase gráfica completa.

## 2026-08-04 - Backend Freeze Sprint 3 hardening

- Added typed migration-history guards, an injected startup coordinator and real historical restore coverage for 0001, 0003 and 0005 ZIPs. Restore preserves the archive/extracted source, migrates only a second temporary candidate, validates integrity/foreign keys and keeps the active database on the covered failure path.
- Added an isolated subprocess import smoke test and a controlled DDL/index failure regression: migration history is not recorded before migration success. SQLite DDL rollback is deliberately not claimed.
- The remaining isolated lifecycle blocker is addressed in Sprint 3C through an optional widget-composition seam; no visual/UI redesign was introduced.

## 2026-08-04 - Backend Freeze Sprint 3C closure evidence

- Added the optional `MainWindowDependencies` composition seam and a headless clean-install lifecycle using temporary Settings, logging, SQLite, repositories and degraded deterministic preview. The default constructor remains unchanged.
- Added a test-only migration execution hook matrix and representative historical restore fixtures. Git LFS diagnostics now reproduce successfully with empty `ls-files` output; no LFS attribute or tracked FFmpeg binary exists.

## 2026-08-03 - Backend Freeze Sprint 2

- Canonical local file analysis is now named `AudioFileMusicAnalysisService`; the published local and provider `MusicAnalysisService` aliases retain their historical meanings.
- Removed one duplicate `app.services.__all__` entry and added import/export compatibility coverage. Legacy launchers remain deprecated shims; no module, dependency or migration was removed.

## 2026-08-03 - v0.21.0 Global Ranking (Epic 19 closed)

- Added a batched global candidate source and bounded deterministic top-K ranking without UI or ORM materialization.
- `ToolRegistry.default()` composes the canonical global `RecommendationFacade` automatically with Library, History and DJ Intelligence while preserving manual injection.
- Set Builder shares the bounded global source and returns `CANCELLED` without a final plan on cooperative cancellation. SQLite query-count, 10,000-candidate benchmark and structured-event coverage were validated before local publication.

## 2026-08-03 - v0.20.0 Preview Player

- Épica 18 queda cerrada con Preview Player Core, selección de dispositivo, Settings schema 3, historial `played` confirmado y la barra funcional integrada en MainWindow.
- La publicación es local mediante un único commit y tag anotado; no usa GitHub, push, Git LFS ni versiona `runtime/ffmpeg/ffmpeg.exe`.
- Próxima etapa planificada: Épica 19 — Global Ranking & DJ Integration, sin implementación iniciada.

## 2026-08-03 - Epic 18 Sprint 18.3 Functional Preview Player Visual Integration

- Added `PreviewPlayerBar` as a service-only persistent bottom bar with explicit library load, transport, seek, volume, output-device selection, safe status/errors and accessibility basics.
- MainWindow composes the optional bar without direct Qt Multimedia access. The UI trusts backend-confirmed service state and does not write played history itself.
- Automated coverage remains headless and deterministic; the manual helper now opens a file chooser for optional audible checks.

## 2026-08-03 - Epic 18 Sprint 18.2 Device Selection, Playback History & Application Integration

- Added serializable output-device selection/fallback and explicit Settings schema 3 preferences with migration `1 -> 2 -> 3`.
- Added a once-per-load, backend-confirmed `played` history port with isolated history failures.
- MainWindow now accepts and safely closes an optional player service without adding playback controls.

## 2026-08-03 - Épica 18 Sprint 18.1 Preview Player Core

- Se creó un núcleo de preescucha independiente de UI con protocolo de backend, estados tipados, DTOs inmutables y backend determinista sin audio para pruebas.
- `QtMultimediaPlaybackBackend` encapsula `QMediaPlayer` y `QAudioOutput`, mientras `PreviewPlayerService` valida archivos, seek, volumen, callbacks, cierre y logs sanitizados.
- No hay todavía controles visuales, reproducción automática, historial de `played`, dispositivo persistido, FFmpeg de reproducción ni funciones de mezcla DJ.

## 2026-08-03 - v0.19.0 Backup Configuration and Logging

- Epic 17 closes with versioned SettingsService, structured local AppLoggingService and verified BackupRestoreService.
- Local publication uses one commit and annotated tag only: no GitHub, push, Git LFS or FFmpeg executable in Git.
- Restore remains intentionally non-visual and requires plan, confirmation, pre-action backup and disposed database connections.

## 2026-08-03 — Épica 17 Sprint 17.3 Backup & Restore Engine

- Se creó `BackupRestoreService` como frontera única para backups ZIP locales, verificados y rotativos mediante las preferencias explícitas de `BackupSettingsDTO`.
- Las copias SQLite usan `Connection.backup()` e `integrity_check`; los ZIP se escriben temporalmente, se verifican por manifiesto/checksum y se publican de forma atómica.
- La restauración requiere plan y token, crea un backup preventivo obligatorio, valida/extray únicamente en temporales seguros y reemplaza archivos individualmente de manera atómica.
- No se incluyen audio, rutas de biblioteca, FFmpeg, caches, repositorio ni secretos; no hay UI, scheduler ni almacenamiento remoto.

## 2026-08-03 — Épica 17 Sprint 17.2 Structured Logging & Diagnostics

- Se incorporó `AppLoggingService`: JSON Lines local, rotación por tamaño, retención, reconfiguración sin handlers duplicados y cierre idempotente, configurado por `LoggingSettingsDTO`.
- `StructuredLogSanitizer` limita tamaño/profundidad, evita `repr` arbitrario y redacta secretos, prompts/rutas sensibles y datos de ejecutables. No hay telemetría externa.
- Se integraron eventos seguros de ciclo de vida, settings, FFmpeg, análisis, workers, asistente y migración de base de datos. Los hooks de excepciones son explícitos y preservan el comportamiento previo.
- La exportación diagnóstica atómica devuelve checksum y manifiesto; sólo contiene datos sanitizados y logs recientes acotados.

## 2026-08-03 — Épica 17 Sprint 17.1 Configuration Foundation

- Se creó `SettingsService` como API canónica para preferencias JSON tipadas, inmutables, versionadas y persistidas atómicamente en `%APPDATA%\DJPlus\config.json`.
- El esquema actual es `2`; la migración `1 → 2` respalda el archivo antes de completar las confirmaciones y tema de la sección general. Versiones futuras se rechazan y JSON corrupto se respalda antes de volver a defaults seguros.
- La configuración no contiene secretos. Exportaciones sanitizadas, opciones de asistente sin claves sensibles y errores tipados protegen logs y diagnósticos.
- Se agregaron adaptadores no invasivos para `FFmpegResolver`, límites de análisis/hardening y `ProviderConfigDTO`; no existe aún UI de Settings ni servicios acoplados a `MainWindow`.

## 2026-08-03 — v0.18.0 Multi-format Audio Analysis

- Se incorporaron `AudioDecoderProtocol` y `AudioDecoderRegistry`, con decoders PCM por bloques para WAV y AIFF/AIF; el orden contractual es MP3, FLAC, AIFF/AIF y WAV.
- `FFmpegAudioDecoder` agrega MP3/FLAC locales por stdout PCM, con timeout, cancelación, cierre seguro, errores tipados y sin archivos temporales, SDKs, red ni instalación.
- `FFmpegResolver` aplica prioridad ruta configurada → PATH → runtime bundled. `FFmpegCapabilityProbe` valida versión y decoders; el fallback bundled verifica SHA-256 antes de iniciar el proceso.
- El runtime Windows x64 proviene de BtbN/FFmpeg-Builds `autobuild-2026-08-02-13-17`, artefacto LGPL no-shared `ffmpeg-N-125907-ga7e72069f1-win64-lgpl.zip`. `LICENSE.txt`, notices, origen, versión, build configuration y checksums quedan junto al binario.
- `MultiFormatAudioAnalysisFacade` exporta diagnósticos y procedencia por item; `MainWindow` lo compone de forma opcional, sin escaneo automático.
- El binario de 114.9 MB queda fuera del historial Git y se conserva localmente en `runtime/ffmpeg/ffmpeg.exe`. Los manifiestos quedan versionados y el empaquetador debe validar su checksum antes de incorporar el binario al instalador.

## 2026-08-03 — v0.17.0 Duplicate Detection

- Added `DuplicateDetectionService`, immutable duplicate DTOs and block-wise SHA-256 behind `LibraryService`.
- `FingerprintCache` keys values by filepath, size and `mtime_ns`; snapshot changes invalidate safely and delegate to canonical hashing again.
- `DuplicateDetectionFacade`, cooperative worker, allowlisted read-only tool and textual export detect and explain groups without deleting, moving, renaming or modifying files.
- `ToolRegistry.default()` now initializes base tools before optional extensions. `MainWindow` exposes the duplicate facade optionally, without a dedicated visual panel.
- Recoverable bytes retain one copy per group. Hashing remains linear in uncached bytes and can be expensive on large or slow libraries.

## 2026-08-03 — v0.16.0 Track Metadata Editing

- Se consolidaron rutas backend legacy sin eliminarlas y se definieron fronteras públicas canónicas.
- Se incorporó edición de metadata confirmada, preview determinista, historial durable, restore durable y migración `0005`.
- `TrackMetadataFacade`, herramientas preview/apply y panel mínimo integrado permiten el flujo de edición sin modificar tags de audio.
- Limitación UI: sólo título e IDs manuales; faltan controles visuales para todos los campos, selección directa y detalle de progreso/error por pista.

## 2026-08-03 — v0.15.0 Analysis Persistence & Library Enrichment

- `AnalysisChangePlanner` incorpora políticas de escritura, clasificación explicable y vista previa determinista de BPM, key y energía.
- `AnalysisPersistenceService` exige confirmación mediante `ActionPipeline`, escribe atómicamente por pista y conserva respaldo/restauración tipados en memoria.
- La migración `0004_analysis_provenance` agrega fecha, versión y confianzas nullable para pistas existentes y nuevas.
- Los lotes aíslan resultados por pista; no se incorpora UI ni se aplican cambios sin confirmación explícita.

## 2026-08-03 — v0.14.0 Music Analysis Engine

- Se incorporó análisis local WAV PCM determinista para duración, sample rate, canales, peak, RMS, energía, BPM y tonalidad mayor/menor con confianza.
- `MusicAnalysisFacade` obtiene pistas sólo mediante `LibraryService`, analiza lotes sin persistir ni actualizar metadata y aísla fallos por archivo.
- `MusicAnalysisWorker`, `MusicAnalysisBatchTool`, exportación a texto e integración opcional con `AssistantPanel` mantienen el flujo read-only.
- BPM y key quedan en `None` si la evidencia es insuficiente. La cancelación se observa cooperativamente entre bloques PCM; mezclas complejas, modulaciones y enarmónicos quedan fuera del alcance actual.

## 2026-08-03 — v0.13.0 Intelligent Set Builder

- Se incorporó `SetPlanningEngine` con secuenciación determinista, sin duplicados y políticas de BPM y energía.
- `EnergyJourneyPlanner` incorpora curvas ascending, descending y arc con fases warm-up, build, peak y cooldown.
- `SetBuilderFacade` obtiene una página de candidatas mediante `LibraryService`, excluye historial reciente y expone `SetBuilderTool` read-only.
- Los planes se exportan a texto y `AssistantPanel` puede mostrar la secuencia. No se crean playlists ni se persisten planes.
- El ranking se limita al conjunto de candidatas recuperado; un plan parcial explica cuando faltan transiciones válidas.

## 2026-08-03 — v0.12.0 Core Optimization & Hardening

- Cachés locales acotadas, profiling por etapa y métricas tipadas de error, cancelación, timeout y concurrencia.
- Hardening cooperativo de `ImportWorker`, `AssistantWorker` y `ToolPlanExecutor`, con límites locales, aislamiento de fallos y cierre seguro.
- `DiagnosticsService`, `DiagnosticsTool` y resumen opcional en `AssistantPanel`, sin telemetría, persistencia ni histórico.
- Riesgo: los timeouts y cierres no fuerzan tareas en curso; se observan en el siguiente punto cooperativo.

## 2026-08-03 — v0.11.0 DJ Recommendation Engine

- Se implementó scoring de recomendaciones determinista y explicable por BPM, key, energía e historial.
- Se incorporó ranking en memoria con desempate estable, límites y confianza.
- `RecommendationFacade` consulta candidatos mediante `LibraryService`, aplica filtros y excluye historial reciente mediante `HistoryService`.
- `RecommendationTool` expone resultados read-only mediante `ToolRegistry`; `AssistantPanel` muestra rango, score y confianza.
- El ranking actual se calcula por página de candidatos. Un ranking global queda diferido a una estrategia explícita de agregación.

## 2026-08-03 — v0.10.0 Advanced Tool Calling

- Se incorporó `ToolPlanner` con planificación determinista de múltiples herramientas y validación de dependencias.
- Se incorporó `ToolPlanExecutor`, que delega exclusivamente en `ToolDispatcher` y modela pasos `success`, `failed` y `blocked`.
- Se incorporó `ToolResultComposer` para respuestas estructuradas y deterministas de planes completos, parciales y fallidos.
- `AssistantRuntime` integra estas capacidades de forma opcional, sin alterar el flujo directo de herramientas.
- No se ejecutan acciones de escritura ni se agregan accesos a Services, Repository, SQLite, red o UI en la pila de planificación.

## 2026-08-03 — v0.9.0 AI Assistant Foundations

- Se completó la infraestructura de proveedores: contratos, registro, selección, política de reintentos, errores tipados, redacción de secretos y transporte inyectable.
- Se completó el Tool Calling Framework con schemas validados y herramientas integradas exclusivamente mediante Services.
- Se incorporó el Execution Framework simulado con confirmación, autorización explícita, revalidación, auditoría, idempotencia y rollback no operativo.
- Se implementó el MVP de Ollama local, limitado a localhost, con `AssistantPanel` PySide6, worker cancelable y `LibraryQueryTool` de solo lectura.
- Se incorporó búsqueda natural determinista de biblioteca, filtros compuestos, resultados paginados y mensajes explicativos.
- El cierre de release sigue pendiente de commit y tag aprobados explícitamente.


Final v0.22.0 closure: Qt tests share one real QApplication and reject an incompatible QCoreApplication; lazy `app.services` exports eliminate the TrackRepository/LibraryService import cycle while preserving the public API. `unittest discover` completed 381 tests OK in 139.470 s, with no `0xC0000409` and no import cycles.
## 2026-08-01

- Se creó la interfaz PySide6.
- Se implementó la biblioteca visual.
- Se agregó ordenamiento por columnas.
- Se incorporó el panel de información de la biblioteca.
- Se reorganizó la arquitectura interna con TrackRepository y TrackTableModel.
- Se integró QTableView + QSortFilterProxyModel.
- Se dejó la vista preparada para una versión estable v0.4.

### Próximo objetivo

- Cerrar la versión v0.4 con un commit y tag finales.
- Iniciar el desarrollo del Editor de Track en v0.5.

## 2026-08-02 — Motor de Biblioteca

- Se incorporaron LibraryService, SearchEngine, SortEngine y FilterEngine.
- La UI delega consultas de biblioteca a LibraryService; SQLite ejecuta búsqueda y ordenamiento.
- Se añadieron pruebas unitarias para la capa de servicio y los motores.
- En 8.529 pistas: apertura 7,758 s → 2,183 s; filtro 1,074 s → 0,027 s; ordenamiento 11,262 s → 3,349 s.
- No se añadieron índices porque la siguiente limitación es materializar todas las filas Qt.

## 2026-08-02 — Sprint 5.3: Virtual Library

- `TrackTableModel` carga 200 pistas inicialmente y solicita páginas adicionales mediante `canFetchMore()` y `fetchMore()`.
- `LibraryService` conserva el estado de la consulta y reinicia la paginación al buscar, filtrar u ordenar.
- `TrackRepository` ejecuta páginas SQLite con `LIMIT/OFFSET`; no se mantienen cursores abiertos entre lotes.
- El contador muestra pistas cargadas frente al total de resultados sin repetir el `COUNT` durante el scroll.

## 2026-08-02 — Sprint 5.4: Collection Engine

- Se añadieron colecciones manuales persistentes y su relación muchos-a-muchos con pistas.
- La UI usa exclusivamente `CollectionService`; `CollectionRepository` concentra la persistencia SQLite.
- El panel de Colecciones permite crear, renombrar, eliminar y seleccionar colecciones.
- El tipo `smart` queda reservado en el modelo de datos para la próxima etapa, sin lógica de Smart Collections implementada.

## 2026-08-02 — Sprint 5.5: Playlist Engine

- Se añadieron playlists separadas de Collections, con orden manual persistente de pistas.
- `PlaylistRepository` evita duplicados y mantiene posiciones contiguas al mover o quitar una pista.
- La UI usa exclusivamente `PlaylistService` mediante un panel básico de administración.
- Se dejó documentada la futura integración de Set Builder, sin implementar reproducción ni drag and drop.

## 2026-08-02 — Sprint 5.6: Favorites + History Engine

- Se añadió el estado persistente de favorito por pista, accesible mediante `FavoriteService`.
- Se incorporó `track_history` con eventos de selección, reproducción, alta y uso en playlist.
- La selección en la biblioteca, el escáner y el agregado a playlists registran los eventos disponibles.
- Se documentó el uso futuro de historial por Smart Collections e IA, sin implementar esas funciones.

## 2026-08-02 — Sprint 5.7: Smart Collections Engine

- Se añadieron reglas persistentes para colecciones de tipo `smart`, manteniendo intactas las colecciones manuales.
- `SmartRuleEngine` traduce reglas soportadas a `FilterCriteria` con semántica AND.
- `SmartCollectionService` evalúa mediante `LibraryService`, manteniendo la consulta SQLite y la carga incremental.
- El panel permite crear una colección smart y visualizar sus reglas; no se añadió editor avanzado, IA ni recomendaciones.

## 2026-08-02 — Sprint 5.8: Stabilization & Release Candidate

- Se centralizó la versión v0.5.0 en `app.version.VERSION`.
- Se reemplazó la inicialización ad hoc por migraciones SQLite registradas e idempotentes.
- Se añadieron pruebas de integración para importación, biblioteca, favoritos, playlists, historial y Smart Collections.
- Se documentaron arquitectura, módulos legacy, deuda técnica, riesgos y recomendaciones para v0.6.
- Validación RC: 35 pruebas automatizadas correctas; benchmark visual sobre 8.529 pistas correcto.
- El cierre y cualquier commit/tag de v0.5.0 quedan pendientes de aprobación explícita.

## 2026-08-02 — Sprint 6.1: Import Engine

- Se incorporaron ScannerService, MetadataService, ImportQueue, ImportService, ImportWorker y TrackImportService.
- Las migraciones 0002 y 0003 agregan trabajos persistentes y snapshots de archivo.
- Cada alta o actualización de pista se coordina con historial e ImportItem dentro de un Unit of Work.
- El motor conserva rating, favoritos, playlists, collections e historial existentes.

## 2026-08-02 — Sprint 6.1.7A: Release Hardening

- Se centralizó la versión objetivo 0.6.1 y se actualizó la documentación de cierre.
- El arranque de base usa exclusivamente migraciones versionadas.
- Se normalizan filepaths para compatibilidad entre rutas relativas heredadas y rutas absolutas de importación.
- Los errores persistidos se acotan a 500 caracteres y se agregó un benchmark reproducible del motor.

## 2026-08-03 — Epic 19 Sprint 19.1: Global Ranking Engine

- Added canonical global recommendation composition and automatic `ToolRegistry.default()` activation while preserving manual injection.
- The ranking streams scalar columns by batches and retains only top-K; a real SQLite test guards against N+1 and the temporary 10,000-track benchmark reports time, memory, queries and determinism.
- Set Builder returns a typed global cancellation outcome rather than a final partial plan; structured events contain only counters and status.

## 2026-08-02 — Épica 1: AI Runtime Core (v0.8.0)

- Se completaron `AssistantRuntime`, `PromptBuilder`, `ToolRegistry`, `ToolDispatcher`, `ConversationSession`, `ActionPipeline` y `ConfirmationManager`.
- El Runtime es independiente de proveedores de IA: no conecta modelos, no accede a SQLite, ORM, repositorios, filesystem ni UI.
- Las herramientas son allowlisted; las propuestas de acción son inmutables y las confirmaciones sólo devuelven decisiones tipadas, sin ejecutar cambios.
- Se consolidó la arquitectura mediante cinco ADRs y pruebas de aislamiento, contratos públicos y grafo de dependencias acíclico.
- Validación de cierre: 122 pruebas automatizadas, `compileall`, `git diff --check` y benchmark de apertura de biblioteca correctos.
- Commit y tag `v0.8.0` quedan pendientes de aprobación explícita.
