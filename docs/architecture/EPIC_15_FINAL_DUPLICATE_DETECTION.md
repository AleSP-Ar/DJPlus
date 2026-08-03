# Epic 15 - Final: Duplicate Detection

Duplicate detection is read-only. It hashes content in blocks, caches fingerprints
by filepath/size/mtime, exposes progress/cancellation through its worker and
returns deterministic groups with recoverable-byte estimates. `DuplicateDetectionTool`
exports only fingerprints, groups, cancelled state and group fields. No deletion,
move, rename, SQLite access or retention policy exists.

The tool is exported by `app.services` and can be added to `ToolRegistry.default()`
through the optional `duplicate_detection_facade` argument. `MainWindow` creates the
same facade only when its existing `LibraryView` exposes a usable `LibraryService`;
the reference is intentionally optional and does not alter navigation or perform a
scan automatically. Text export is deterministic and is derived only from the
duplicate-result DTO fields.

The headless integration test covers optional `MainWindow` construction, worker
start/progress, typed result/text export, and cooperative cancellation. Its
deterministic smoke benchmark processes 1,000 simulated entries in memory; it is a
regression guard, not a filesystem throughput claim.
