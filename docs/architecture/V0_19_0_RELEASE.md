# v0.19.0 - Backup Configuration and Logging

## Release summary

v0.19.0 closes Epic 17 with `SettingsService`, `AppLoggingService` and `BackupRestoreService`. Publication is local only: one commit and annotated tag, without GitHub, push, Git LFS or the FFmpeg executable in Git.

## Configuration and logging

Settings are immutable DTOs under schema version 2. They are atomically persisted at `%APPDATA%\\DJPlus\\config.json` by default, migrate `1 -> 2` with a previous-file backup, reject future/unknown input and provide sanitized export. Existing FFmpeg, analysis and assistant constructors use explicit compatible adapters.

`AppLoggingService` consumes `LoggingSettingsDTO` explicitly. It writes bounded rotating JSON Lines at `%APPDATA%\\DJPlus\\logs`, uses UTC/process/thread metadata, safely reconfigures one canonical handler and supports explicit sys/thread hooks. Recursive redaction removes credential, token, executable and music-path metadata. Diagnostic export is atomic, bounded, sanitized and checksummed.

## Backup and restore

`BackupRestoreService` uses `sqlite3.Connection.backup()` and `PRAGMA integrity_check`, never a raw copy of an open SQLite database. A standard ZIP contains only a SQLite copy when available, portable sanitized settings, `manifest.json` and `checksums.sha256`. Music, full library paths, FFmpeg, prompts, credentials, caches, complete logs, repository files and other backups are excluded.

Verification rejects corrupt/truncated ZIPs, invalid manifests, future formats/schemas, bad checksum/size, duplicate members, symlinks, absolute or traversal paths and undeclared entries. Retention only considers canonical backups under the configured directory.

Restore is inspect/plan then exact confirmation token. It re-verifies, creates a verified mandatory `pre_action` backup, disposes injected database connections, extracts only to a private temporary directory, validates or migrates a copied older SQLite schema and atomically replaces every selected file. The source backup is not modified.

## Limits and residual risks

- Database and settings are not a cross-file transaction; each replacement is atomic and the pre-action backup remains for recovery.
- Restore requires an inactive application or disposed relevant connections. No global write gate was added.
- Music paths are deliberately omitted from portable settings. No media is backed up.
- No UI, scheduler, remote backup or media backup is included. A future UI must show progress, confirmation and restart requirements.
- Operations are local and I/O-bound.

## Validation and publication

- Focused Settings, logging and backup suites passed.
- Full unittest suite: 318 tests passed.
- WAL, integrity, malicious ZIP, retention, complete/failed/exclusive restore, cancellation and dispose-before-replace checks use temporary paths.
- Real bundled MP3/FLAC, corrupt inputs, multiformat benchmark and headless MainWindow checks passed.
- `compileall app`, `git diff --check`, temporary-file audit and handler audit passed.
