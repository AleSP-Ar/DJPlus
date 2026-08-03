import json
import logging
import sqlite3
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

from sqlalchemy import create_engine, text

from app.database.migrations import run_migrations
from app.services.app_logging_service import AppLoggingService
from app.services.backup_restore_service import (
    BackupRequestDTO,
    BackupRestoreService,
    RestoreConfirmationError,
)
from app.services.settings_service import LoggingSettingsDTO, SettingsService


class _Cancelled:
    def is_cancelled(self):
        return True


class BackupRestoreServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.database = self.root / "state" / "library.sqlite"
        self.database.parent.mkdir()
        self._migrate(self.database)
        self.settings = SettingsService(self.root / "config" / "config.json")
        self.settings.update({"backup": {"directory": str(self.root / "backups"), "retention": 2}, "logging": {"directory": str(self.root / "logs")}})
        self.logging_service = AppLoggingService(LoggingSettingsDTO(directory=str(self.root / "logs"), max_bytes=4096, retained_files=2))
        self.closed, self.closed_titles = 0, []
        self.service = BackupRestoreService(self.settings, self.database, self.logging_service.get_logger("backup"), close_connections=self._closed)

    def tearDown(self):
        self.logging_service.shutdown()
        self.temp.cleanup()

    @staticmethod
    def _migrate(path):
        engine = create_engine(f"sqlite:///{path.as_posix()}")
        try:
            run_migrations(engine)
        finally:
            engine.dispose()

    def _closed(self):
        self.closed += 1
        if self.database.is_file():
            try:
                self.closed_titles.append(self._title())
            except (sqlite3.Error, TypeError):
                self.closed_titles.append(None)

    def _insert_title(self, title):
        connection = sqlite3.connect(self.database)
        try:
            connection.execute("INSERT OR REPLACE INTO tracks (id, title, artist, filepath) VALUES (1, ?, 'artist', 'C:/private/music.mp3')", (title,))
            connection.commit()
        finally:
            connection.close()

    def _title(self):
        connection = sqlite3.connect(self.database)
        try:
            return connection.execute("SELECT title FROM tracks WHERE id=1").fetchone()[0]
        finally:
            connection.close()

    def test_create_verify_manifest_checksums_and_private_exclusions(self):
        self._insert_title("original")
        result = self.service.create_backup()
        self.assertTrue(result.success)
        self.assertTrue(result.verification.valid)
        self.assertEqual(result.included_files, ("database.sqlite", "settings.json"))
        with zipfile.ZipFile(result.filepath) as archive:
            self.assertEqual(set(archive.namelist()), {"database.sqlite", "settings.json", "manifest.json", "checksums.sha256"})
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual((manifest["backup_format_version"], manifest["reason"]), (1, "manual"))
            self.assertNotIn("private", archive.read("settings.json").decode("utf-8"))
            self.assertNotIn("ffmpeg.exe", " ".join(archive.namelist()))
        self.assertIn("backup_completed", self.logging_service.get_current_log_file().read_text(encoding="utf-8"))

    def test_sqlite_wal_copy_is_consistent_and_cancel_cleans_temporaries(self):
        connection = sqlite3.connect(self.database)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("INSERT OR REPLACE INTO tracks (id, title, artist, filepath) VALUES (2, 'wal', 'artist', 'C:/x.wav')")
            connection.commit()
        finally:
            connection.close()
        result = self.service.create_backup()
        self.assertTrue(result.success)
        cancelled = self.service.create_backup(BackupRequestDTO(cancellation_token=_Cancelled()))
        self.assertTrue(cancelled.cancelled)
        self.assertFalse(list(self.service.get_backup_directory().glob("*.tmp")))

    def test_missing_or_corrupt_settings_produces_partial_database_backup(self):
        self.settings.get_config_path().write_text("{broken", encoding="utf-8")
        result = self.service.create_backup()
        self.assertTrue(result.success)
        self.assertIn("settings_corrupt_omitted", result.warnings)
        self.assertEqual(result.included_files, ("database.sqlite",))
        self.assertEqual(result.verification.status, "valid_with_warnings")

    def test_malicious_zip_checksum_failure_and_foreign_file_are_rejected(self):
        target = self.service.get_backup_directory() / "DJPlus_Backup_bad.zip"
        target.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(target, "w") as archive:
            archive.writestr("../escape.txt", "bad")
            archive.writestr("manifest.json", "{}")
            archive.writestr("checksums.sha256", "")
        self.assertEqual(self.service.verify_backup(target).status, "unsafe")
        result = self.service.create_backup()
        tampered = Path(result.filepath)
        with zipfile.ZipFile(tampered, "a") as archive:
            archive.writestr("unexpected.txt", "bad")
        self.assertIn(self.service.verify_backup(tampered).status, {"unsafe", "corrupt"})

    def test_retention_only_deletes_recognized_backups_and_keeps_foreign_files(self):
        first = self.service.create_backup(BackupRequestDTO(reason="manual"))
        second = self.service.create_backup(BackupRequestDTO(reason="manual"))
        third = self.service.create_backup(BackupRequestDTO(reason="manual"))
        foreign = self.service.get_backup_directory() / "keep.txt"; foreign.write_text("keep", encoding="utf-8")
        retention = self.service.apply_retention(protected_paths=(third.filepath,))
        self.assertTrue(foreign.is_file())
        self.assertIn(third.filepath, retention.retained_files)
        self.assertLessEqual(len(self.service.list_backups()), 2)
        self.assertTrue(first.success and second.success and third.success)

    def test_restore_requires_plan_confirmation_and_creates_pre_action_backup(self):
        self._insert_title("before")
        self.settings.update({"general": {"theme": "dark"}})
        backup = self.service.create_backup()
        self._insert_title("after")
        self.settings.update({"general": {"theme": "light"}})
        plan = self.service.plan_restore(backup.filepath)
        with self.assertRaises(RestoreConfirmationError):
            self.service.restore_backup(plan, "wrong")
        restored = self.service.restore_backup(plan, plan.confirmation_token)
        self.assertTrue(restored.success)
        self.assertIsNotNone(restored.pre_action_backup_id)
        self.assertEqual(self._title(), "before")
        self.assertEqual(self.settings.load(recover_corrupt=False).general.theme, "dark")
        self.assertGreaterEqual(self.closed, 1)
        self.assertEqual(self.closed_titles[-1], "after")

    def test_restore_exclusivity_rejects_second_active_restore(self):
        backup = self.service.create_backup()
        plan = self.service.plan_restore(backup.filepath)
        self.assertTrue(self.service._restore_lock.acquire(blocking=False))
        try:
            with self.assertRaises(Exception) as caught:
                self.service.restore_backup(plan, plan.confirmation_token)
            self.assertEqual(type(caught.exception).__name__, "RestoreBusyError")
        finally:
            self.service._restore_lock.release()
