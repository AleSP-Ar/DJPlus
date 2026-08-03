# DJPlus Architecture — v0.5.0 Release Candidate (pending approval)

## General structure

```text
PySide6 UI
  LibraryView / CollectionPanel / PlaylistPanel
        ↓
Application services
  LibraryService / CollectionService / PlaylistService
  FavoriteService / HistoryService / SmartCollectionService
        ↓
Repositories and engines
  Track, Collection, Playlist, Favorite, History and Rule repositories
  SearchEngine / SortEngine / FilterEngine / SmartRuleEngine
        ↓
SQLAlchemy + SQLite
```

The UI communicates through services. Services coordinate application workflows and own no SQL. Repositories isolate persistence. Engines validate and translate query or rule contracts. SQLAlchemy models define the data relationships.

## Assistant boundaries (v0.9.0)

The provider layer is DTO-based and uses a registry, capability validation, bounded policy, typed errors and secret redaction. The local MVP permits only HTTP to `localhost` and has no credentials. `ToolRegistry` is allowlisted and schema-validated; the local assistant exposes only `LibraryQueryTool`, resolving natural-language criteria through `LibraryService` without SQL generation or direct repository access. The execution boundary remains simulated and requires explicit confirmation and authorization. `AssistantPanel` delegates local queries to `AssistantWorker` in a `QThread` with cooperative cancellation.

## Advanced Tool Calling (v0.10.0)

`ToolPlanner` creates immutable ordered plans. `ToolPlanExecutor` invokes eligible plan steps only through `ToolDispatcher`; failed dependencies block downstream steps and every outcome is typed as `success`, `failed` or `blocked`. `ToolResultComposer` preserves plan order and creates a deterministic structured explanation. `AssistantRuntime` exposes planning execution and composition only when an optional plan is supplied. These modules do not execute actions, import persistence, or bypass the tool allowlist.

## DJ Recommendation Engine (v0.11.0)

`RecommendationScoringEngine` evaluates BPM, key, energy and play history with explicit weighted reasons. `RecommendationService` ranks candidates deterministically; `RecommendationFacade` obtains candidate pages from `LibraryService`, applies optional filters and excludes recently played IDs from `HistoryService`. `RecommendationTool` is read-only and `AssistantPanel` renders rank, score and confidence. Ranking is intentionally per candidate page, not global across the whole library.

## Data flow

Library search, sort, and filters flow from `LibraryView` to `LibraryService`, then `TrackRepository`, where SQLite performs the work. `TrackTableModel` retains only fetched rows and asks `LibraryService` for additional pages through `canFetchMore()` and `fetchMore()`.

Collection and playlist panels call their respective services. Smart Collections persist rules, convert them through `SmartRuleEngine` and `FilterEngine`, then evaluate through `LibraryService`; their membership is never materialized. Favorites are track state, while history is append-only activity data.

## Decisions

- SQLite owns global search, filtering, ordering, counting, and smart-rule evaluation.
- Virtual Library uses `LIMIT/OFFSET` with deterministic track ID tie-breakers. Keyset pagination remains the future option for deep navigation in very large libraries.
- Manual collections and playlists are separate aggregates: collection membership is unordered; playlist entries have manual positions.
- History writes are typed and indexed. Smart Collections currently support only fields backed by `FilterEngine` and the existing schema.
- `app.version.VERSION` is the single release version source.
- `schema_migrations` records ordered, idempotent schema upgrades. v0.5 starts with `0001_baseline_schema`, which safely upgrades prior `tracks` databases.

## Legacy modules and technical debt

- `app/gui.py` is the previous Tkinter interface and bypasses the service architecture.
- `app/library.py` exposes direct session helpers retained for compatibility.
- `app/scanner.py` still constructs `Track` persistence directly; it uses `HistoryService` for the event but should move to a dedicated import service in v0.6.
- Services currently create separate SQLAlchemy sessions by default. Multi-service operations therefore lack a unit-of-work transaction boundary.
- A first history write occurs synchronously during track selection and can add noticeable latency on cold SQLite connections.
- `LIMIT/OFFSET` may degrade for deep pages, and `LIKE '%text%'` does not use conventional B-tree indexes.
- Smart rules have AND semantics only; generic fields such as genre require a track-schema migration before support.

## v0.6 recommendations and risks

1. Introduce an import service and explicit unit-of-work/session scope for transactional multi-service workflows.
2. Move history recording off the selection interaction path or batch it to protect UI responsiveness.
3. Benchmark keyset pagination and SQLite FTS5 at 100k+ tracks.
4. Add controlled schema migrations for genre and richer smart-rule expressions only after product approval.
5. Retire or adapt the Tkinter/direct-session legacy paths after a compatibility decision.
