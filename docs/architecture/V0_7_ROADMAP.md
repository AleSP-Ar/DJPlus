# DJPlus v0.7 — Architecture Roadmap

## Goal

v0.7 turns the completed v0.6.1 Import Engine into a visible, extensible DJ workflow without changing its import rules, SQLite contracts, or existing library UI. This document is an architecture proposal only; it authorizes no schema, UI, service, or migration change.

## Completion update — Epic 1 AI Runtime

The AI Assistant foundation proposed in this roadmap was completed and extended through the v0.8.0 AI Runtime Core release. The completed scope includes Assistant Runtime, Prompt Builder, Tool Registry, Tool Dispatcher, Conversation Session, Action Pipeline, Confirmation Manager, architectural audit, and ADRs. The Runtime remains provider-neutral and does not implement model connections, persistence, autonomous actions, or direct infrastructure access.

## Design principles

- UI, analysis, sync, and AI are edge layers that depend on public application-service contracts.
- Long-running I/O and CPU work stays outside the Qt GUI thread.
- Track identity remains normalized filepath until an explicitly approved duplicate policy exists.
- Analysis results and external data are provenance-aware: their source, version, timestamp, and confidence must be visible to the service layer.
- AI and external connectors never obtain a raw SQLAlchemy session or direct widget access.
- Every future persistence change needs a dedicated additive migration and compatibility test from v0.6.1.

## Target shape

```text
PySide6 views
  ImportManagerView / future analysis and sync views
        |
Qt signal adapters and application services
  ImportManagerController / AnalysisService / SyncService / AssistantFacade
        |
Domain services and adapters
  ImportService / AnalysisProvider / SyncAdapter / LibraryQueryFacade
        |
Repositories + UnitOfWork
        |
SQLite
```

## 1. Import Manager UI

### Scope

Expose the already implemented import lifecycle: folder selection, progress, cancellation, terminal summaries, failed items, and recovery/resume of incomplete jobs.

### Integration contract

`ImportWorker` remains the execution boundary. A Qt-specific adapter subscribes to its data-only `ImportEvent` events and relays them through Qt signals to an `ImportManagerController`. The view never calls repositories, starts threads, or mutates import status directly.

```text
ImportManagerView -> ImportManagerController -> ImportWorker
                                                |
                                          ImportEvent callback
                                                |
                                   Qt signal adapter -> view model -> view
```

The controller reads job summaries and item lists through a dedicated read-only facade over `ImportRepository`. Cancellation remains cooperative. Resume is enabled only for jobs returned by the existing incomplete-job recovery flow.

### Non-goals

- No change to import identity, metadata refresh, hashing, duplicate policy, or job semantics.
- No background worker pool; one active import worker remains the default.

## 2. Music Analysis Engine

Analysis is a separate asynchronous pipeline, never a hidden step inside import. It consumes stable track references and publishes typed results to an `AnalysisService`. Initial provider capabilities are BPM, key, duration verification, energy features, waveform references, and optional low-level musical features.

Providers must be replaceable because algorithms, licenses, and platform support vary. Analysis writes require their own Unit of Work and an approved migration only after an ownership/provenance contract is selected. See [MUSIC_ANALYSIS_DESIGN.md](MUSIC_ANALYSIS_DESIGN.md).

## 3. DJ Intelligence Layer

The intelligence layer is deterministic first. It evaluates analysis results and existing user-owned library data through read-only query DTOs, producing explanations as well as scores.

Initial proposed outputs:

- track compatibility score: BPM distance, harmonic/key relation, energy delta, genre/tag compatibility when available;
- transition suggestion: candidate ordering and rationale, not automatic playback control;
- energy-curve recommendation: tracks that fit a requested range or session phase;
- smart crates: saved, inspectable rule/query definitions rather than opaque materialized memberships.

No recommendation may overwrite ratings, favorites, playlists, history, or manual collections. A future write path must be explicit and user initiated.

## 4. External Sync

Traktor, Rekordbox, and Serato are adapter targets, not core dependencies. A `SyncAdapter` contract should have separate read, plan, and apply phases:

```text
external source -> adapter read -> normalized DTOs -> SyncService plan
                                          |                 |
                                          +-> conflict report +-> explicit apply
```

Import/export is opt-in, previewable, cancellable, and logged. Each adapter must preserve source identifiers and never assume that filepath, playlist order, cue points, ratings, or beat grids have the same ownership rules across products. No connector, file parser, or database schema is approved in this roadmap.

## 5. AI Assistant Foundation

An `AssistantFacade` sits above a controlled `LibraryQueryFacade` and `RecommendationFacade`. It receives structured tools and DTOs, not database access. Read operations can answer library questions; proposed playlist or crate changes are returned as drafts requiring user confirmation. See [AI_ASSISTANT_DESIGN.md](AI_ASSISTANT_DESIGN.md).

## Proposed implementation order

1. **v0.7.1 Import Manager UI** — consume the stable v0.6.1 events and recovery model; add controller/view-model tests without changing the import core.
2. **v0.7.2 Analysis foundations** — approve result ownership and persistence migration; build one provider behind a deterministic test fixture.
3. **v0.7.3 DJ Intelligence** — deterministic compatibility and explainable crate/query proposals using analysis DTOs.
4. **v0.7.4 External Sync contract** — define adapter fixtures and dry-run planning; implement one product only after format and license review.
5. **v0.7.5 AI Assistant foundation** — read-only tools, audit trail, draft generation, and confirmation boundary.

## Cross-cutting risks and gates

| Area | Principal risk | Required gate |
|---|---|---|
| Import UI | cross-thread Qt updates | signal-adapter tests and cancellation/resume integration tests |
| Analysis | CPU load, unstable algorithms, large assets | benchmark, provider fixture tests, explicit migration review |
| Intelligence | opaque or surprising recommendations | deterministic scoring and human-readable explanations |
| External sync | data loss and ownership conflicts | dry-run plan, backup/export policy, product-specific fixtures |
| AI | privacy, unsafe writes, hallucinated actions | least-privilege tools, confirmation, audit events, redaction policy |

## Explicitly deferred

- Content-hash duplicate handling.
- Parallel import workers.
- Automatic external synchronization.
- Autonomous AI writes or playback control.
- Any v0.6.1 migration rewrite.
