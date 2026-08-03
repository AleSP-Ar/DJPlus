# Backup and Restore Design

## Scope and data classification

`BackupRestoreService` is the sole local backup boundary. Essential data is the SQLite library state; optional safe configuration is the versioned Settings JSON. Regenerable data (logs, diagnostics snapshots and caches), external media, the virtual environment, repository files, other backups and `runtime/ffmpeg/ffmpeg.exe` are never included. The service has no UI, scheduler or `MainWindow` dependency.

## Portable package

Every backup is a uniquely named standard ZIP: `DJPlus_Backup_YYYYMMDD_HHMMSS_<id>.zip`. It contains only `database.sqlite` when available, a sanitized `settings.json` when valid, `manifest.json` and `checksums.sha256`. Library paths are intentionally omitted from the settings copy, so restoring a portable package never creates music directories or reveals local paths.

`manifest.json` is strictly parsed and records format version, ID, UTC time, DJPlus/Python/platform versions, source database/settings schemas, per-file size and SHA-256, reason, consistency, warnings and minimum compatibility. The checksums file covers every payload and the manifest itself.

## Creation and verification

SQLite is copied through `sqlite3.Connection.backup()` into a process temporary directory; a raw copy of an open database is never used. This is compatible with WAL. The copied database must return exactly `ok` from `PRAGMA integrity_check` before packaging. ZIP creation writes a temporary file in the configured backup directory, verifies it fully, fsyncs it and atomically publishes its final unique name. Failures and cooperative cancellation clean temporary files.

Verification rejects missing manifests, bad ZIPs, duplicated members, absolute paths, traversal, backslash paths, symlinks, unexpected files, bad sizes/checksums, malformed manifests, corrupt SQLite and future backup/database schemas. Older database schemas are allowed with a migration-required warning. Verification never extracts into a final destination.

## Retention and restore

Retention only considers canonical `DJPlus_Backup_*.zip` files under the configured directory. It respects count, optional age and the pre-action retention policy, never follows symlinks or deletes foreign files, and reports each isolated failure.

Restore is deliberately two-step: `plan_restore()` re-verifies and creates a `RestorePlanDTO`; `restore_backup()` accepts only that plan's one-time confirmation token. Cooperative cancellation is checked before any protected replacement. Before any replacement it re-verifies the source and creates a verified `pre_action` backup of current state. It closes injected database connections, extracts only validated members to a private temporary directory, validates/migrates an older SQLite copy, and uses file-level atomic replacement. The original backup is never changed. Restart is recommended after a successful restore.

The default plan restores both valid components; callers can explicitly select database-only or settings-only. Configuration is replaced, never silently merged. The safe portable settings representation intentionally restores no music paths.

## Composition, logging and privacy

`app.database.create_backup_restore_service()` composes the service with `DATABASE_PATH`, `engine.dispose` and an optional `AppLoggingService` child logger. Tests inject all paths, a temporary logger and test databases. Events include identifiers, reason, duration, status, count and size only: `backup_started`, `backup_completed`, `backup_failed`, `backup_cancelled`, verification failure, retention, restore planning/start/completion/failure and pre-restore backup completion.

No configuration contents, track names, database rows, audio, complete music paths or credentials are logged. There is no remote storage, automatic scheduler, visual restore flow, media backup or cross-file transaction for database-plus-settings replacement; each protected file is atomic and the verified pre-action backup is preserved for recovery.
