# Backend Functional Inventory

Audit date: 2026-08-03. Scope: source under `app/`, automated tests, UI wiring,
architecture documents, milestones and roadmap. This is an evidence-based
inventory, not a product claim. Statuses mean:

- **completa**: implementation, persistence/UI where relevant, and automated tests exist.
- **parcial**: useful behavior exists but a material product boundary is absent.
- **sólo infraestructura**: contracts/mocks/designs exist without a production integration.
- **no implementada**: no usable implementation was found.
- **candidata a eliminación**: legacy or duplicated path that should be retired only after migration review.

## Capability inventory

| Area | Status | Evidence and current boundary |
|---|---|---|
| Library, pagination and sorting | completa | `LibraryService`, `SearchEngine`, `FilterEngine`, `SortEngine`, `TrackRepository`, virtual `TrackTableModel` and tests implement paged loading, deterministic ordering and result counts. |
| Text search and filters | completa | Text, BPM, key, rating, dates and favorites run through `LibraryService`; natural-language parsing maps only to existing service filters. Genre is explicitly rejected pending schema/product work. |
| Import and re-import | completa | Scanner, queue, import jobs/items, metadata service, worker, transactions, normalized filepath and snapshot refresh have migration and integration coverage. |
| Metadata editing and bulk editing | parcial | Analysis writes BPM/key/energy only, with confirmation and restore. No general track editor, title/artist/album/genre editing API, bulk selection workflow or UI exists. |
| Duplicate detection | no implementada | Filepath uniqueness prevents identical paths only. Content-hash policy is repeatedly deferred in import/roadmap documents; no detector, merge workflow or UI exists. |
| Playlists | completa | Ordered persistent entries, duplicate prevention, move/remove behavior, service and panel are implemented. |
| Manual collections | completa | Persistent collection CRUD and membership through service/repository/panel are implemented and tested. |
| Smart collections | parcial | Rules, AND semantics and service evaluation exist. Rule language is bounded and genre/richer boolean expressions remain unavailable. |
| Favorites and history | completa | Favorite state and append-only history services/repositories exist. Playback-originated history is not available because no player exists. |
| WAV music analysis | completa | Local deterministic PCM WAV duration, sample rate, channels, peak, RMS, energy, BPM and key analysis; batch facade, worker, export and tests exist. Scope is WAV PCM only and BPM/key may be absent at low confidence. |
| Analysis change planning | completa | Immutable comparison DTOs, deterministic preview and write policies are covered by `AnalysisChangePlanner` tests. |
| Analysis persistence and provenance | parcial | Confirmed atomic BPM/key/energy persistence, restore and nullable migration `0004_analysis_provenance` exist. Backup is process-memory only; there is no durable analysis-run/audit history, batch orchestration UI, or provenance for untouched fields. |
| Recommendations | parcial | Deterministic scoring/ranking/facade/tool exist, but ranking is only over the page returned by `LibraryService`, not the entire library. |
| Set Builder | parcial | Deterministic set/journey policies, facade, tool and text export exist. It is read-only, uses one candidate page and does not create/export playlists. |
| Player and preview | no implementada | No playback engine, audio output, waveform, cue/seek, device handling or preview UI exists. Roadmap still lists Preview Player as future. |
| Backup and restore of library | no implementada | Only transient analysis-value restore exists. There is no database/media backup, restore point, export archive, retention or verification workflow. |
| Application configuration | parcial | Local provider and scanner settings are DTO/config arguments, but no consolidated settings service, persistent preferences, validation UI or configuration migration exists. |
| Traktor, Rekordbox, Serato | sólo infraestructura | `SyncAdapter`/`SyncService`/`MockSyncAdapter` support read-plan-preview-apply contracts. No real adapter, parser, export format, fixture or UI exists. |
| Assistant runtime and tools | parcial | Runtime, registry/dispatcher, schemas, planning and many read-only tools exist. Tool availability is optional/injected; general natural-language routing and write execution are intentionally bounded. |
| Providers and Ollama | parcial | Provider contracts, mock transport, adapters and localhost-only Ollama MVP exist. OpenAI/LM Studio are mock-transport adapter contracts, not real integrations; no streaming/fallback/durable conversation. |
| Action execution | sólo infraestructura | Confirmation, authorization, audit/idempotency and rollback contracts use `MockActionExecutor`; only analysis persistence performs a real confirmed write. |
| Logs, errors and diagnostics | parcial | Typed errors, worker metrics, secret redaction, in-memory audit and `DiagnosticsService` exist. There is no durable structured logging, log rotation, crash reporting, telemetry policy or historical diagnostics. |

## UI and integration findings

`MainWindow` wires library, collections, playlists and import panels. The
assistant panel is separate and optional; it is not wired into `MainWindow`.
Analysis persistence deliberately has no UI. Recommendation, set-builder and
analysis panel rendering are conditional on tool results rather than a complete
user workflow. This explains why many backend capabilities are valid but still
classified as partial product features.

## Unused, duplicated or redundant paths

| Item | Classification | Rationale |
|---|---|---|
| `app/gui.py` | candidata a eliminación | Legacy Tkinter path bypasses the current PySide6/service composition. Retire only after confirming no external launcher imports it. |
| `app/library.py` | candidata a eliminación | Direct/session-oriented compatibility helpers overlap `LibraryService` and repository boundaries. |
| `app/scanner.py` | candidata a eliminación | Older direct persistence scanner overlaps `ScannerService` + Import Engine and risks bypassing jobs/UoW. |
| `app/services/music_analysis_service.py` | candidata a consolidación | Older provider/mock feature service overlaps the newer file-DSP `audio_analysis_service.py`; identical `MusicAnalysisService` naming is hazardous. Preserve compatibility behind a renamed interface or retire it. |
| `app/services/assistant_facade.py` tool classes vs `library_tools.py` | candidata a consolidación | Two tool families expose overlapping concepts (`LibraryQueryTool`, `DJCompatibilityTool`, `MusicAnalysisTool`) with different contracts. `ToolRegistry` uses `library_tools.py`; make one public tool surface. |
| `docs/roadmap/ROADMAP.md` and `MILESTONES.md` | candidata a actualización | Roadmap still describes v0.4/v0.8 future milestones while releases through v0.15 are published. It should become a forward v1.0 roadmap. |
| `app/config.py` | candidata a revisión | No application-wide configuration composition was found; either implement the documented role or remove/replace it. |

## Dependencies

Current runtime dependencies are justified by the implemented UI/persistence:
PySide6, SQLAlchemy and SQLite. The audit found no need for an additional DSP,
HTTP or vendor SDK dependency because analysis is stdlib PCM and provider tests
use mock transport. `mutagen` is used by import metadata extraction; retain it
only while multi-format metadata import remains supported. Do not add external
DJ-format libraries before the Traktor/Rekordbox/Serato ownership policy and
fixtures are approved.

## Technical risks

1. **Naming and dual APIs:** two `MusicAnalysisService` concepts and duplicated
   tool classes can cause accidental imports or the wrong capability exposure.
2. **Stateful `LibraryService`:** query/filter/pagination state is mutable;
   facades using it share state and only receive a page, affecting global
   recommendation/set quality and concurrent workflows.
3. **Analysis correctness/performance:** deterministic PCM BPM/key estimation is
   intentionally basic, WAV-only and expensive for long files; complex mixes,
   modulation and enharmonic names remain unsupported.
4. **Transient safeguards:** analysis backups, confirmations, executor audit and
   idempotency are process-local. A restart loses restore/approval/audit context.
5. **Migration coverage:** schema migration is idempotent and tested from the
   v0.5 baseline, but production backup/rollback and upgrade testing against
   real user databases is still required.
6. **Legacy bypasses:** direct scanner/session modules can evade import,
   transaction and diagnostic behavior if still invoked.
7. **UI reachability:** many backend services are not reachable from the main
   application window; passing tests alone does not establish product usability.

## Missing functions for v1.0

1. Track editor and safe bulk metadata workflow, including analysis preview,
   selection, confirmation, persistent analysis audit and durable restore.
2. Content-hash duplicate detection, review/merge policy and non-destructive UI.
3. Preview/player foundation with device/error handling and history integration.
4. Durable backup/restore for database and user data, verified recovery and
   export/import policy.
5. Consolidated persisted configuration, schema validation and a settings UI.
6. At least one production-quality external DJ workflow, after fixtures,
   licensing, conflict, backup and cancellation design; do not claim all three
   platforms from the current sync contract.
7. Product integration for assistant, recommendation, set builder and analysis
   workflows, with clear read/write permissions.
8. Structured local logs, rotation, diagnostic export boundaries and recovery UX.
9. Retire/consolidate legacy modules and duplicate APIs before expanding surface.

## Recommended implementation order

1. **Stabilize boundaries:** retire or quarantine legacy scanner/gui/library,
   unify tool and music-analysis APIs, and update roadmap/docs.
2. **Library v1 core:** implement editor + bulk metadata + durable analysis audit
   and restore, then content-hash duplicate review.
3. **Safety operations:** database/media backup and verified restore; persistent
   configuration and structured local logs.
4. **Playback:** preview player and history integration, because it unlocks
   meaningful DJ workflow validation.
5. **Productize intelligence:** connect analysis/recommendations/set builder to
   coherent UI flows and whole-library candidate strategies.
6. **External ecosystems:** ship one adapter end-to-end with fixtures and backup
   policy before adding Traktor, Rekordbox or Serato breadth.
7. **Assistant expansion:** preserve local/read-only defaults; add real provider
   capabilities only after permissions, logging and support policy are complete.
