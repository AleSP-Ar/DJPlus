import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, text

from app.database.migrations import MIGRATIONS, _baseline_schema, run_migrations
from app.services.database_migration_coordinator import DatabaseMigrationCoordinator


class _Verification:
    valid = True


class _Backup:
    success = True
    backup_id = "preaction01"
    verification = _Verification()


class _BackupService:
    def __init__(self, success=True): self.success, self.calls = success, 0
    def create_pre_action_backup(self, operation_id=None):
        self.calls += 1
        value = _Backup(); value.success = self.success
        return value


class DatabaseMigrationCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.path = Path(self.temp.name) / "library.sqlite"
    def tearDown(self): self.temp.cleanup()

    def _historical(self):
        engine = create_engine(f"sqlite:///{self.path.as_posix()}")
        with engine.begin() as connection:
            _baseline_schema(connection)
            connection.execute(text("CREATE TABLE schema_migrations (version VARCHAR(64) PRIMARY KEY NOT NULL)"))
            connection.execute(text("INSERT INTO schema_migrations (version) VALUES ('0001_baseline_schema')"))
            connection.execute(text("INSERT INTO tracks (id,title,artist,filepath) VALUES (1,'old','test','old.wav')"))
        engine.dispose()

    def test_current_database_skips_backup(self):
        engine = create_engine(f"sqlite:///{self.path.as_posix()}"); run_migrations(engine); engine.dispose()
        backup, disposed = _BackupService(), []
        result = DatabaseMigrationCoordinator(self.path, backup, close_connections=lambda: disposed.append(True)).prepare_database_for_startup()
        self.assertEqual(result.status, "CURRENT")
        self.assertEqual((backup.calls, disposed), (0, []))

    def test_historical_database_backs_up_disposes_then_migrates(self):
        self._historical(); backup, disposed = _BackupService(), []
        result = DatabaseMigrationCoordinator(self.path, backup, close_connections=lambda: disposed.append(True)).prepare_database_for_startup()
        self.assertEqual((result.status, result.backup_id, backup.calls, disposed), ("MIGRATED", "preaction01", 1, [True]))

    def test_backup_failure_aborts_before_dispose_or_migration(self):
        self._historical(); backup, disposed = _BackupService(False), []
        result = DatabaseMigrationCoordinator(self.path, backup, close_connections=lambda: disposed.append(True)).prepare_database_for_startup()
        self.assertEqual(result.status, "BACKUP_FAILED")
        self.assertEqual(disposed, [])

    def test_fault_matrix_returns_failed_without_false_record_and_recovers(self):
        phases = (
            ("before_migration_run", None), ("before_migration", "0002_import_engine"),
            ("before_first_ddl", "0002_import_engine"), ("before_create_table", "0002_import_engine"),
            ("after_create_table", "0002_import_engine"), ("before_create_index", "0002_import_engine"),
            ("after_create_index", "0002_import_engine"), ("during_data_transformation", "0003_track_import_snapshots"),
            ("before_schema_migrations_record", "0002_import_engine"),
            ("after_schema_migrations_record", "0002_import_engine"),
            ("after_ddl_before_schema_current", "0002_import_engine"),
            ("before_final_validation", "0002_import_engine"),
        )
        for phase, target_version in phases:
            with self.subTest(phase=phase):
                self.path.unlink(missing_ok=True)
                self._historical()
                backup, disposed = _BackupService(), []

                def migrate(path, phase=phase, target_version=target_version):
                    engine = create_engine(f"sqlite:///{Path(path).as_posix()}")
                    try:
                        def fault(current_phase, version, _statement):
                            if current_phase == phase and (target_version is None or version == target_version):
                                raise RuntimeError(f"fault:{phase}")
                        run_migrations(engine, execution_hook=fault)
                    finally:
                        engine.dispose()

                result = DatabaseMigrationCoordinator(self.path, backup, migration_runner=migrate, close_connections=lambda: disposed.append(True)).prepare_database_for_startup()
                self.assertEqual((result.status, result.error_type, backup.calls, disposed), ("FAILED", "RuntimeError", 1, [True]))
                engine = create_engine(f"sqlite:///{self.path.as_posix()}")
                try:
                    with engine.connect() as connection:
                        versions = connection.execute(text("SELECT version FROM schema_migrations")).scalars().all()
                    self.assertNotIn(target_version or MIGRATIONS[0][0], versions[1:])
                    self.assertNotIn(MIGRATIONS[-1][0], versions)
                finally:
                    engine.dispose()
                retried = DatabaseMigrationCoordinator(self.path, _BackupService()).prepare_database_for_startup()
                self.assertEqual(retried.status, "MIGRATED")
