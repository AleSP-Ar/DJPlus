# Database Migration and Compatibility

DJPlus supports ordered SQLite migrations `0001_baseline_schema` through `0005_track_metadata_history`. Historical migration bodies are immutable. `run_migrations()` applies one missing migration inside its own transaction and records its version only after its function completes; a failure therefore cannot mark that migration complete.

## Supported matrix

| Origin | Result | Guard |
| --- | --- | --- |
| Empty database | 0001→0005 current schema | Idempotent rerun. |
| 0001 / 0002 / 0003 / 0004 | Current schema | Prefix-upgrade integration test with preserved track fixture. |
| 0005 | Current schema unchanged | Double-run test. |
| Unknown/future record | Rejected | `MigrationFutureVersionError`; no repair or overwrite. |
| Non-contiguous known history | Rejected | `MigrationHistoryError`. |
| Non-empty database without history | Rejected | `MigrationHistoryError`. |

0001 creates the library, playlist, collection/history/rule tables and critical indexes. 0002 adds import jobs/items and indexes. 0003 adds import snapshots. 0004 adds nullable analysis provenance. 0005 adds durable metadata history and its index. No migration transforms existing user media; provenance fields remain nullable for historical tracks.

SQLite DDL transactional guarantees depend on the operation/version. DJPlus does not claim a global rollback across all filesystem and DDL effects. The safe guarantee is that the migration record is inserted after its function succeeds; failed histories are detected on next launch rather than silently declared current.

The fault-injection regression wraps the 0002 migration after its table and index DDL and before the version record. It proves that `schema_migrations` does not advance falsely and that a subsequent idempotent run converges. It does **not** prove rollback of every SQLite DDL side effect: SQLite can retain idempotent DDL after an interrupted operation, which is why a verified backup remains the recovery boundary.

`BackupRestoreService` remains the only backup/restore implementation. Restore creates and verifies a pre-action backup, disposes connections through its injected callback before replacement, verifies ZIP content/checksums and runs integrity checks. Its current restore-plan policy accepts the current schema; historical schema migration during restore remains a future coordinated hardening task and must first be performed on a temporary copy.

## Startup coordinator and historical restore

`DatabaseMigrationCoordinator` is the injected startup boundary. It returns `CURRENT` without backup for an already-current database; otherwise it requires a verified pre-action backup, invokes the supplied dispose callback, runs migrations and validates `integrity_check` plus `foreign_key_check`. Backup failure returns `BACKUP_FAILED`; future history returns `INCOMPATIBLE`; other failures remain `FAILED` and retain the preventive backup.

Historical restore verifies the ZIP first, extracts `database.sqlite` to a secure temporary directory, preserves that extraction, copies it to a second temporary candidate and migrates only the candidate. It validates integrity and foreign keys before connections are disposed and atomic replacement is attempted. ZIP and extracted source are never modified. A failure before replacement preserves the active database; filesystem/database replacement remains individually atomic rather than one cross-file transaction.

The end-to-end restore regression creates real verified ZIP fixtures at schema 0001, 0003 and 0005, confirms the plan token and pre-action backup, restores representative historical track data, and compares the original ZIP bytes before and after. Future schema archives are rejected during planning; a temporal migration that does not reach the current schema returns a typed failure without replacing the active database. Inconsistent historical records are rejected by the migration runner. These checks cover database replacement only; database and settings files are individually atomic, not one filesystem transaction.

The fixture matrix preserves the entities that existed in each historical schema: tracks (including Unicode, favorites and NULLs), playlists/positions, collections, smart rules and history are present from 0001; import metadata is populated from 0003; durable metadata history is populated at 0005. Later tables are created empty when absent from the historical source.
