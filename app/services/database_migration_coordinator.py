"""Explicit startup migration coordinator with verified pre-action backup."""

from dataclasses import dataclass
import logging
from pathlib import Path

from app.database.migrations import (
    MIGRATIONS,
    MigrationError,
    MigrationFutureVersionError,
    run_migrations,
)


@dataclass(frozen=True)
class DatabaseMigrationResultDTO:
    status: str
    backup_id: str | None = None
    error_type: str | None = None

    def __post_init__(self):
        if self.status not in {"CURRENT", "MIGRATED", "FAILED", "INCOMPATIBLE", "BACKUP_FAILED"}:
            raise ValueError("Estado de migracion no valido.")


class DatabaseMigrationCoordinator:
    """Coordinates only startup safety; it owns neither UI nor a backup engine."""

    def __init__(self, database_path, backup_service=None, migration_runner=None, close_connections=None, logger=None):
        self._database_path = Path(database_path)
        self._backup_service = backup_service
        self._migration_runner = migration_runner or self._migrate
        self._close_connections = close_connections or (lambda: None)
        self._logger = logger or logging.getLogger("djplus.database")

    def prepare_database_for_startup(self):
        try:
            current = self._schema()
            if self._database_path.exists() and current == MIGRATIONS[-1][0]:
                return DatabaseMigrationResultDTO("CURRENT")
            backup_id = None
            if self._database_path.exists():
                if self._backup_service is None:
                    return DatabaseMigrationResultDTO("BACKUP_FAILED", error_type="backup_service_missing")
                backup = self._backup_service.create_pre_action_backup(operation_id="startup_migration")
                if not backup.success or backup.verification is None or not backup.verification.valid:
                    return DatabaseMigrationResultDTO("BACKUP_FAILED", error_type="backup_verification_failed")
                backup_id = backup.backup_id
            self._close_connections()
            self._migration_runner(self._database_path)
            if self._schema() != MIGRATIONS[-1][0]:
                return DatabaseMigrationResultDTO("FAILED", backup_id, "schema_not_current")
            self._integrity_check()
            return DatabaseMigrationResultDTO("MIGRATED", backup_id)
        except MigrationFutureVersionError as error:
            self._event("migration_incompatible", type(error).__name__)
            return DatabaseMigrationResultDTO("INCOMPATIBLE", error_type=type(error).__name__)
        except (MigrationError, OSError, ValueError, RuntimeError) as error:
            self._event("migration_failed", type(error).__name__)
            return DatabaseMigrationResultDTO("FAILED", error_type=type(error).__name__)

    def _schema(self):
        if not self._database_path.exists():
            return None
        from app.services.backup_restore_service import BackupRestoreService
        return BackupRestoreService._database_schema(self._database_path)

    def _migrate(self, path):
        from sqlalchemy import create_engine
        engine = create_engine(f"sqlite:///{Path(path).as_posix()}")
        try:
            run_migrations(engine)
        finally:
            engine.dispose()

    def _integrity_check(self):
        import sqlite3
        connection = sqlite3.connect(self._database_path)
        try:
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("integrity_check_failed")
            if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise ValueError("foreign_key_check_failed")
        finally:
            connection.close()

    def _event(self, name, error_type):
        self._logger.info(name, extra={"event_name": name, "component": "database", "context": {"exception_type": error_type}})
