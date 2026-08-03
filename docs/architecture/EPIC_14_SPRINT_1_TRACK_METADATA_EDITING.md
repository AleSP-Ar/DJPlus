# Epic 14 - Sprint 1: Track Metadata Editing Core

`TrackMetadataEditorService` produces deterministic per-track previews from an
immutable patch, then requires an `ActionPipeline` proposal and matching
confirmation before using one UnitOfWork per track. It edits only database
metadata (title, artist, album, genre, rating, BPM, key and energy), never audio
files. Empty nullable values are represented as `None`; absent patch fields are
not changed. Previous selected values remain in transient backups for restore.

Batch entries are attempted independently. The service has no SQLite access,
UI, external dependency or audio-file mutation.
