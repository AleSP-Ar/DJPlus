# DJPlus v0.15.0 — Analysis Persistence & Library Enrichment

## Release scope

- `AnalysisChangePlanner`, immutable DTOs, policies `never_overwrite`, `overwrite_lower_confidence` and `force`, plus preview determinista.
- `AnalysisPersistenceService` with `ActionPipeline` confirmation, atomic per-track writes, typed apply results, backup and restore.
- `AnalysisChangePreviewTool` read-only.
- Migration `0004_analysis_provenance`: nullable `analyzed_at`, `analyzer_version`, `bpm_confidence`, `key_confidence` and `energy_confidence`.

## Safety and compatibility

Existing tracks receive NULL provenance and remain compatible. Backups are transient in memory: they support restoration while the service lives but are not a historical audit store. Batch operations isolate each track result. Skipped and unchanged fields never write metadata or provenance.

There is no UI in this version. Direct SQLite access and external dependencies are not added; writes require an explicit `ActionPipeline` proposal and confirmation.

## Release checks

The candidate requires complete unittest suite, migration from a prior database, compileall, git diff --check and release-file audit. Commit and tag require separate approval.
