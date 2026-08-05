import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from app.core.user_paths import LegacyDatabaseMigrationError, USER_DATA_ENV, get_user_data_paths, migrate_legacy_database


class UserDataPathsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def _sqlite(self, path):
        connection = sqlite3.connect(path)
        try:
            connection.execute("CREATE TABLE marker (value TEXT)")
            connection.execute("INSERT INTO marker VALUES ('legacy')")
            connection.commit()
        finally:
            connection.close()

    def test_windows_paths_use_local_appdata_and_create_directories(self):
        paths = get_user_data_paths({"LOCALAPPDATA": str(self.root / "local")}, platform_name="nt", home=self.root)
        self.assertEqual(paths.root, self.root / "local" / "DJPlus")
        paths.ensure_directories()
        self.assertTrue(all(path.is_dir() for path in (paths.root, paths.database.parent, paths.logs, paths.backups)))

    def test_environment_override_is_canonical_for_isolated_runs(self):
        override = self.root / "isolated"
        paths = get_user_data_paths({USER_DATA_ENV: str(override)}, platform_name="nt", home=self.root)
        self.assertEqual((paths.root, paths.config), (override, override / "config.json"))

    def test_first_migration_copies_a_valid_legacy_database_without_removing_it(self):
        legacy, destination = self.root / "legacy.db", self.root / "new" / "djplus.db"
        self._sqlite(legacy)
        self.assertTrue(migrate_legacy_database(legacy, destination))
        self.assertTrue(legacy.is_file() and destination.is_file())
        connection = sqlite3.connect(destination)
        try:
            self.assertEqual(connection.execute("SELECT value FROM marker").fetchone(), ("legacy",))
        finally:
            connection.close()

    def test_existing_destination_is_never_overwritten(self):
        legacy, destination = self.root / "legacy.db", self.root / "existing.db"
        self._sqlite(legacy); destination.write_bytes(b"keep-existing")
        self.assertFalse(migrate_legacy_database(legacy, destination))
        self.assertEqual(destination.read_bytes(), b"keep-existing")

    def test_copy_failure_keeps_legacy_and_does_not_create_destination(self):
        legacy, destination = self.root / "legacy.db", self.root / "new" / "djplus.db"
        self._sqlite(legacy); original = legacy.read_bytes()
        with self.assertRaises(LegacyDatabaseMigrationError):
            migrate_legacy_database(legacy, destination, copy_func=lambda *_: (_ for _ in ()).throw(OSError("denied")))
        self.assertEqual(legacy.read_bytes(), original)
        self.assertFalse(destination.exists())
