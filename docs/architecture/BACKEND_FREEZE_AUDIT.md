# Backend Freeze Audit — Sprint 1

**Baseline audited:** `bd0459d213ed2d886c1b6e6fd95312597733c2c8` (`v0.21.0`). This audit is read-only with respect to product behaviour: no schema, API, scoring, UI or external integration changes are proposed here.

## Repository inventory

| Area | Count | Classification | Notes |
| --- | ---: | --- | --- |
| `app/services` | 73 | CANONICAL / ACTIVE | Application boundaries, DTOs, workers, assistant and local media infrastructure. |
| `app/database` | 5 | CANONICAL | Engine/session composition, ORM models, UoW and ordered migrations. |
| `app/repository` | 7 | CANONICAL | SQLAlchemy-only persistence adapters. |
| `app/ui` | 24 | ACTIVE | PySide6 consumers; excluded from this backend freeze. |
| `tests` | 82 modules | TEST/TOOL | Unit, integration, migration and headless coverage. |
| `docs` | 113 Markdown files | ACTIVE / HISTORICAL | Release records must remain historical. |
| `tools` | 4 entry scripts | TEST/TOOL | Benchmarks and manual preview check. |

There is no `app/models` package: canonical ORM models are `app.database.models`. There is no separate `app/repositories` package: canonical adapters are under singular `app.repository`.

### Canonical operational modules

- Startup: `app.main`, `app.database.init_database`, `SettingsService`, `AppLoggingService`, `MainWindow` and optional `PreviewPlayerService` composition.
- Library: `LibraryService`, `TrackRepository`, query/filter/sort engines, import services and UoW.
- Local audio: `audio_analysis_service`, `audio_decoder`, FFmpeg resolver/decoder and `MultiFormatAudioAnalysisFacade`.
- Local recovery/configuration: `SettingsService`, `BackupRestoreService`, `AppLoggingService`, `DiagnosticsService`.
- Assistant boundaries: `assistant_runtime`, provider/transport/credential contracts, `ToolRegistry` and `ToolDispatcher`.
- DJ intelligence: `RecommendationService`, `RecommendationFacade`, `GlobalRankingService`, `SetBuilderFacade`, planning/journey services.

### Compatibility and legacy modules

| Module | Internal consumers / tests | Replacement | Risk | Action |
| --- | --- | --- | --- | --- |
| `app.gui` | Only its own direct launcher; compatibility test imports it | `python -m app.main` / `MainWindow` | High: external Tkinter launcher may exist | Keep warning; inventory external launchers before removal. |
| `app.library` | `app.gui`; compatibility test | `LibraryService` + `TrackRepository` | High: direct-session scripts may import helpers | Keep warning; provide migration guide before removal. |
| `app.scanner` | Compatibility test only internally | `ImportService` / `TrackImportService` | High: script performs direct persistence and writes `scan_errors.txt` | Keep warning; never remove until external usage window is closed. |
| `music_analysis_service.MusicAnalysisService` | Provider/mock tests and compatibility test | `ProviderMusicAnalysisService` | Medium: name collides with file DSP service | Preserve alias; make new callers use explicit provider/file names. |
| Tool aliases in `assistant_facade` | Compatibility tests | `library_tools` + `ToolRegistry` | Medium | Preserve aliases until a deprecation release has elapsed. |

## Dependency map and duplication findings

`app.main -> SettingsService/AppLoggingService -> init_database -> HistoryService/PreviewPlayerService -> MainWindow` is the supported application composition. `ToolRegistry` is the assistant allowlist; tools rely on services, not repositories. `GlobalRankingService <- LibraryService <- TrackRepository` streams scalar rows and is independent of UI paging.

- `RecommendationService` is score/rank policy for a supplied candidate set. `RecommendationFacade` is Library/History orchestration. `GlobalRankingService` is canonical whole-library streaming. These responsibilities are complementary, not duplicates.
- `DiagnosticsService` exposes in-memory health metrics; `AppLoggingService` owns persistent local JSONL and diagnostic export. Do not merge them without a retention/privacy decision.
- `SettingsService` and `BackupRestoreService` have different ownership: preferences vs verified recovery packages.
- `MusicAnalysisService` has two historical meanings: provider/mock feature contract and local PCM file analysis. This is the highest naming-consolidation candidate, but aliases and tests prove compatibility is currently intentional.

## DTO/model review

Public immutable DTO families are concentrated in service modules. Public boundary DTOs include settings, logging/backup, audio decoding/analysis, assistant/provider/tool, metadata, duplicate, recommendation/global ranking and set planning. ORM models are canonical in `app.database.models` (`Track`, playlists, collections, history, imports and metadata history).

No DTO is classified removable solely from text search. Candidates requiring a consumer migration audit are: the provider-era analysis DTOs and legacy assistant tool DTO aliases. Tests `test_backend_boundary_compatibility.py`, audio tests and tool tests cover their compatibility risk.

## Dependencies

| Dependency | Evidence | Classification |
| --- | --- | --- |
| SQLAlchemy | database, repositories, tests, benchmarks | Required canonical. |
| PySide6 | UI, `app.main`, headless tests | Required desktop/optional multimedia runtime. |
| mutagen | `MetadataService`, legacy scanner | Required for metadata import; legacy scanner is not sole consumer. |
| greenlet | SQLAlchemy runtime dependency | Transitive/runtime; review lock policy later. |
| python-dotenv | Declared; no project import found | Candidate for dependency review, not removal this sprint. |
| typing_extensions | Declared; no project import found | Candidate for dependency review, may be transitive compatibility support. |
| FFmpeg | Optional external executable, resolver/decoder tests | Not a Python dependency; bundled executable is ignored by Git. |

## Entry points

Supported: `python -m app.main`; benchmark tools under `tools/`; `tools/manual_preview_player_check.py` for operator checks. Compatibility-only entry points: `python -m app.gui`, `python -m app.library`, `python -m app.scanner`. No `.bat` or `.ps1` launcher was found. No entry point must be removed in this sprint.

## Migrations and compatibility matrix

| Origin | Required ordered migrations | Expected result | Coverage |
| --- | --- | --- | --- |
| Empty / baseline | 0001 | tracks, playlists, collections, history, rules | `test_migrations` |
| v0.5 baseline | 0002, 0003 | import jobs/items and track snapshots | migration/import tests |
| Pre-analysis | 0004 | nullable analysis provenance | migration/analysis persistence tests |
| Pre-metadata history | 0005 | durable `track_metadata_history` | migration/metadata tests |
| Settings schema 1/2 | in-service 1→2→3 | current immutable settings | settings tests |

Historical migrations are idempotent and must not be edited. Remaining audit action: add a single documented matrix test that begins from each published schema snapshot, only after freeze planning approves test cost.

## Documentation and test status

Current: v0.21 release, global-ranking design/checklist, settings/logging/backup, preview and multiformat documents. Historical: release documents and prior epic sprint records. Must update/archive during future cleanup: `README` and architecture headers that still describe v0.20 as current, and the old v0.5 architecture title; do not delete historical releases.

Functional coverage exists for library/import/metadata/audio/duplicates/settings/logging/backup/preview/global ranking/tools/migrations/headless UI. The full suite is broad and can vary in duration because real local FFmpeg and headless UI paths are included. Global-ranking tests intentionally access one private composed service for benchmark/integration assertions; retain until a public diagnostics seam is designed.

## Risks and recommended plan

1. **Safe deletion candidates:** first determine whether `python-dotenv` and `typing_extensions` are transitive requirements; do not delete legacy launchers yet.
2. **API consolidation:** introduce explicit provider-vs-file analysis names at public boundaries, then deprecate compatibility aliases over a release window.
3. **Legacy containment:** document unsupported legacy launchers and direct sessions; collect external usage before removal.
4. **Documentation:** normalize current-version headers, maintain an index separating current architecture from historical releases.
5. **Hardening:** audit global `SessionLocal()` ownership, launch shutdown paths, import cycles and test isolation before any broad refactor.
6. **Frozen-backend release:** only after the above has migration, compatibility and full-suite evidence.

Deferred backlog remains unchanged: Traktor, Rekordbox, Serato, other DJ databases, external metadata APIs, Gemini and ChatGPT/OpenAI.

## Sprint 2 safe consolidation record

- Removed one duplicate public-list entry: `PlaylistToolInputDTO` appeared twice in `app.services.__all__`; the symbol, import and compatibility surface remain unchanged. Evidence: same symbol, no dynamic registration, and a uniqueness regression test. Risk: low.
- Renamed the canonical local PCM/file service to `AudioFileMusicAnalysisService`; `audio_analysis_service.MusicAnalysisService` remains an identity alias for published callers. Provider/mock `music_analysis_service.MusicAnalysisService` remains its historical alias to `ProviderMusicAnalysisService`. Canonical facades/settings now import the explicit local name.
- No module, DTO, dependency, migration, launcher or assistant-tool alias was removed. `python-dotenv` and `typing_extensions` remain declared pending an environment-clean dependency audit.

## Sprint 3 migration and import hardening record

- `run_migrations()` now rejects future/unknown records, non-contiguous known history and non-empty databases without migration history through typed errors. Prefix fixtures cover 0001–0005 plus idempotent reruns.
- Historical migration functions and persistent models were not edited. The migration record is still written only after a migration function succeeds.
- Moved canonical database directory creation from module import to explicit `init_database()`. This removes a demonstrated import side effect without changing the startup contract.

## Sprint 3 completion record

- `DatabaseMigrationCoordinator` is a UI-independent, injected startup boundary with `CURRENT`, `MIGRATED`, `FAILED`, `INCOMPATIBLE` and `BACKUP_FAILED` results. It requires a verified pre-action backup only when an existing database requires migration.
- Historical restore now extracts then copies the database; only the copied temporary candidate is migrated and foreign keys are checked before replacement. Original ZIP and extracted source remain unchanged.
- End-to-end restore fixtures cover 0001, 0003 and 0005 plus future-schema rejection and a temporal migration that fails to reach the current schema. The active database and original archive remain unchanged on the tested failure path.
- A fresh-process import smoke test covers canonical services/database/UI modules and legacy shims with redirected user folders. It found no created configuration, database, logs or backups. It is not a full clean-installer test because `MainWindow` still composes global library services.
- A controlled 0002 DDL/index failure confirms the migration history is not falsely recorded; SQLite DDL rollback is not asserted.
