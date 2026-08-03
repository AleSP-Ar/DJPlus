# Epic 12 - Final: Controlled Analysis Persistence

`AnalysisPersistenceService` consumes only an immutable `AnalysisChangeSetDTO`
and creates an explicit `ActionPipeline` proposal. Applying requires that exact
registered proposal and a matching `ConfirmationManager` confirmation. It writes
only `new` changes and specifically authorized `conflict` fields through one
UnitOfWork per track; `skipped` and `unchanged` are never sent to persistence.

Migration `0004_analysis_provenance` adds nullable `analyzed_at`,
`analyzer_version`, `bpm_confidence`, `key_confidence`, and `energy_confidence`
to existing and new `tracks` databases. Older tracks retain NULL provenance.
`AnalysisMetadataBackupDTO` captures both prior metadata and prior provenance,
so restore returns the complete previous state atomically. Provenance is updated
only for fields being applied; skipped and unchanged fields are untouched.
Batch callers receive one typed apply result per entry and a failure for one
track does not prevent another entry from being attempted.

No service accesses SQLite directly, no UI is added, and no write occurs without
the explicit confirmation boundary.
