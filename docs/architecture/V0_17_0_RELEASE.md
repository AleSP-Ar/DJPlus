# DJPlus v0.17.0 — Duplicate Detection

## Scope

This release candidate adds read-only content-duplicate discovery. `DuplicateDetectionService` obtains tracks through `LibraryService`, calculates SHA-256 in fixed blocks, isolates inaccessible-file errors and creates deterministic groups. `FingerprintCache` keys fingerprints by filepath, size and `mtime_ns`, invalidating safely when a file snapshot changes.

`DuplicateDetectionFacade` supplies cached scans and deterministic text export. `DuplicateDetectionWorker` exposes progress and cooperative cancellation. `DuplicateDetectionTool` is exported from `app.services` and can be added through the optional `duplicate_detection_facade` parameter of `ToolRegistry.default()`. Base tools initialize before optional tools, correcting the previous registry-order failure. `MainWindow` composes the facade optionally and does not perform automatic scans.

## Safety and limits

The implementation never deletes, moves, renames or modifies files, has no automatic retention policy, and does not access SQLite or Repository directly. Recoverable bytes estimate that one copy is kept per duplicate group; this is not a retention decision. A first scan of an uncached large library remains I/O-bound and linear in bytes read. When any selected snapshot is a cache miss, the current facade delegates that selection to canonical hashing, so large partial invalidations can still be costly. The current MainWindow integration has no dedicated visual panel.

## Release validation

The candidate requires the complete unittest suite, focused headless worker flow, deterministic 1,000-entry benchmark, `compileall`, `git diff --check`, and an architectural/file audit. Commit and annotated tag require separate approval.
