# Milestones

## v1.0.0-rc1 — Release Candidate

Esta versión candidata cierra la ruta de datos segura, la migración conservadora de la base legacy y el empaquetado PyInstaller reproducible. La validación de escritorio manual fue aprobada y las mejoras puramente visuales quedan diferidas. El backend funcional, el esquema, la UI existente, las integraciones DJ y los proveedores externos se mantienen sin cambios.

## v0.23.0 — UI Freeze cerrado

La Fase Gráfica completa sus diez sprints: shell y navegación, Biblioteca, Preview Player, Colecciones/Playlists, Import Manager, Metadata, Assistant/Diagnóstico, feedback y accesibilidad. El trabajo es exclusivamente visual y conserva el backend congelado de v0.22.0.

## v0.22.0 — Backend Freeze & Hardening cerrado

Las APIs backend, compatibilidad legacy, migraciones, restore y lifecycle quedan formalmente congelados. Próxima etapa: fase gráfica completa. APIs externas, metadata externa, Traktor, Rekordbox, Serato, Gemini y ChatGPT/OpenAI permanecen backlog.

## Backend Freeze Sprint 3 — migration hardening in progress

Historical 0001/0003/0005 restore, second-copy migration, startup migration coordination and isolated import smoke coverage are implemented. The remaining freeze validation is an explicitly injected clean-install UI lifecycle plus the full resource/performance audit; no schema, UI or scoring change is included.

## Backend Freeze Sprint 2

Safe API clarification is complete: explicit local/provider analysis names, legacy compatibility policy and import coverage. The next work remains controlled backend cleanup; no graphical phase or external integration has started.

## Epic 19 closed - v0.21.0 Global Ranking

Global Ranking Engine introduces batched lightweight candidates and deterministic top-K recommendations across the complete library. The next stage is backend freeze and final cleanup; Traktor, Rekordbox, other DJ software databases, external metadata APIs and Gemini/ChatGPT/OpenAI integrations remain backlog only.

## v0.20.0 local published - Epic 18 closed

Preview Player closes with a service-only Qt backend, deterministic tests, explicit device/Settings/history integration and a functional bottom bar. The next planned stage is Epic 19 - Global Ranking & DJ Integration; no implementation is included here.

## Épica 18 - Preview Player (Sprint 18.1 en progreso)

Preview Player Core añade backend Qt encapsulado, servicio sin UI, estados, seek, volumen, lifecycle y pruebas deterministas headless. La integración visual, historial, controles y funciones DJ quedan fuera de este sprint.

## Epic 18 Sprint 18.2 in progress

Preview Player now owns device selection, explicit schema-3 preferences, played-history integration and optional MainWindow lifecycle composition. Visual controls, waveform and DJ playback functions remain pending.

## Epic 18 Sprint 18.3 in progress

The functional preview bar is integrated at the bottom of MainWindow. It loads the active library row only by explicit action and offers transport, seek, private volume, output selection and degraded status. Final visual design and DJ features remain out of scope.

## v0.19.0 local published - Epic 17 closed

Configuration, Logging & Backup Foundation closes with atomic versioned settings, local sanitized JSONL diagnostics and verified SQLite ZIP backups. Restore requires plan/token confirmation and a mandatory pre-action backup; UI, scheduling, remote storage and media copies are out of scope.

## Next: Epic 18 - Preview Player

Pending approval. No implementation begins in v0.19.0.

## Épica 17 — Configuration, Logging & Backup Foundation (Sprints 17.1–17.3)

En progreso, sin commit de sprint: configuración persistente/versionada, logging JSON Lines y backup ZIP verificable. El nuevo motor hace copia SQLite consistente, manifest/checksums, retención, plan/token de restore y backup preventivo; no incluye medios ni crea UI o scheduler. La UI de Settings, backup remoto y telemetría externa permanecen fuera de alcance.

## v0.18.0 local release candidate

Multi-format Audio Analysis adds the official MP3, FLAC, AIFF/AIF and WAV decoder order, native PCM decoders, optional FFmpeg MP3/FLAC decoding, local capabilities/diagnostics, bundled checksum verification and optional MainWindow composition. Real MP3/FLAC validation is complete. The Windows x64 runtime remains part of the distributable package but its 114.9 MB executable is intentionally ignored by Git; the local installer build must supply the verified binary and validate its manifest checksum.

## v0.17.0 release candidate

Duplicate Detection — block-wise SHA-256, safe file-snapshot cache, deterministic groups, cooperative worker, read-only tool, text export and optional MainWindow integration — is ready as `v0.17.0` release candidate. It does not delete or modify files; a dedicated visual panel remains pending.

## v0.16.0 published

Track Metadata Editing — limpieza de fronteras, edición individual/masiva, preview, confirmación, historial durable, restore, migración `0005`, herramientas y panel mínimo — published as `v0.16.0`.

## v0.15.0 published

Analysis Persistence & Library Enrichment — planificación, políticas, confirmación, persistencia atómica, respaldo/restauración, procedencia y migración `0004` — publicado como `v0.15.0`.

## v0.14.0 release candidate

Music Analysis Engine — análisis WAV PCM local, energía/RMS, BPM, tonalidad, lotes, worker, herramienta read-only y exportación textual — está preparado para release como `v0.14.0`. Commit y tag continúan pendientes de aprobación explícita.

## Historial

## v0.13.0 release candidate

Intelligent Set Builder — secuenciación, curvas energéticas, fachada read-only, herramienta y exportación de planes — está preparado para release como `v0.13.0`. Commit y tag continúan pendientes de aprobación explícita.

## v0.12.0 release candidate

Core Optimization & Hardening — cachés acotadas, profiling, ejecución cooperativa, límites de concurrencia y diagnóstico read-only sin histórico — está preparado para release como `v0.12.0`. Commit y tag continúan pendientes de aprobación explícita.

## v0.11.0 release candidate

DJ Recommendation Engine — scoring, ranking determinista por página, filtros, exclusión de historial, fachada, herramienta y panel — está preparado para release como `v0.11.0`. Commit y tag continúan pendientes de aprobación explícita.

## v0.10.0 release candidate

Advanced Tool Calling — Tool Planner, Tool Plan Executor, dependencias, estados tipados y Tool Result Composer — está preparado para release como `v0.10.0`. Commit y tag continúan pendientes de aprobación explícita.

## v0.9.0 release candidate

AI Assistant Foundations — Providers, Tool Calling, Execution Framework, Ollama local and Natural Language Library Search — is prepared for release as `v0.9.0`. Commit and tag remain pending explicit approval.

| Hito | Estado | Referencia |
|---|---|---|
| Inicialización del proyecto | Completado | v0.1 |
| Escáner y SQLite | Completado | v0.2 |
| Biblioteca visual | Completado | v0.3 |
| Arquitectura MVC inicial | Completado | v0.4 |
| Biblioteca Profesional | Release Candidate | v0.5.0 |
| Import Engine | Completado | v0.6.1 |
| Épica 1 — AI Runtime Core | Completado | v0.8.0 |
| v0.9.0 — AI Assistant Foundations | Preparado para release | v0.9.0 |

## Hito técnico actual

DJPlus v0.8.0 está preparado para cierre: la Épica 1 AI Runtime Core completó Runtime, Prompt Builder, Tool Registry y Dispatcher, Conversation Session, Action Pipeline, Confirmation Manager, auditoría y ADRs. El commit y tag quedan pendientes de aprobación explícita.

## Desglose de sprints v0.5

| Sprint | Alcance |
|---|---|
| 5.2.1 | `LibraryService`: frontera UI → servicio → repositorio |
| 5.2.2 | `SearchEngine`: búsqueda fuera de la UI — completado inicialmente |
| 5.2.3 | `SortEngine`: ordenamiento SQLite fuera de la UI — completado inicialmente |
| 5.2.4 | `FilterEngine`: contratos y validación de filtros — completado inicialmente |
| 5.2.5 | Caché, solo si las mediciones lo justifican |
| 5.3 | Virtual Library: carga incremental — completado |
| 5.4 | Collection Engine: colecciones manuales — completado |
| 5.5 | Playlist Engine: secuencias manuales ordenadas — completado |
| 5.6 | Favorites + History Engine — completado |
| 5.7 | Smart Collections Engine — completado |
| 5.8 | Stabilization & Release Candidate — validado, pendiente de aprobación de cierre |

## Epic 19 — Global Ranking Engine

- Sprint 19.1: global batched ranking, deterministic top-K, canonical factory, effective ToolRegistry composition, SQLite anti-N+1 coverage and 10,000-track benchmark validation.
- Sprint 19.2 remains pending; no UI work or musical scoring change was started.
