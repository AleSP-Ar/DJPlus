import json
import hashlib
import logging
import sqlite3
import tempfile
import threading
import unittest
import zipfile
from dataclasses import replace
from pathlib import Path

from sqlalchemy import create_engine, text

from app.database.migrations import run_migrations
from app.services.app_logging_service import AppLoggingService
from app.services.backup_restore_service import (
    BackupRequestDTO,
    BackupRestoreService,
    BackupVerificationError,
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

    def test_historical_restore_preserves_zip_and_migrates_only_candidate_copy(self):
        from app.database.migrations import MIGRATIONS
        for count in (1, 3, 5):
            with self.subTest(schema=MIGRATIONS[count - 1][0]):
                self.database.unlink(missing_ok=True)
                engine = create_engine(f"sqlite:///{self.database.as_posix()}")
                try:
                    with engine.begin() as connection:
                        connection.execute(text("CREATE TABLE schema_migrations (version VARCHAR(64) PRIMARY KEY NOT NULL)"))
                        module = __import__("app.database.migrations", fromlist=["MIGRATIONS"])
                        for version, _description, function_name in MIGRATIONS[:count]:
                            getattr(module, function_name)(connection)
                            connection.execute(text("INSERT INTO schema_migrations (version) VALUES (:version)"), {"version": version})
                        connection.execute(text("INSERT INTO tracks (id,title,artist,filepath,is_favorite) VALUES (7,'histÃ³ric âœ“','artista','historic.wav',1)"))
                        connection.execute(text("INSERT INTO playlists (id,name) VALUES (3,'Lista histÃ³rica')"))
                        connection.execute(text("INSERT INTO playlist_tracks (playlist_id,track_id,position) VALUES (3,7,2)"))
                        connection.execute(text("INSERT INTO collections (id,name,type) VALUES (4,'ColecciÃ³n','smart')"))
                        connection.execute(text("INSERT INTO collection_tracks (collection_id,track_id) VALUES (4,7)"))
                        connection.execute(text("INSERT INTO collection_rules (collection_id,field,operator,value) VALUES (4,'rating','gte','0')"))
                        connection.execute(text("INSERT INTO track_history (track_id,event_type) VALUES (7,'played')"))
                        if count >= 3:
                            connection.execute(text("UPDATE tracks SET genre='House', bitrate=NULL WHERE id=7"))
                        if count >= 5:
                            connection.execute(text("INSERT INTO track_metadata_history (track_id,fields_json,previous_json,new_json,origin,status) VALUES (7,:fields,:previous,:new,'manual','applied')"), {"fields": '["title"]', "previous": '{"title":null}', "new": '{"title":"histÃ³ric âœ“"}'})
                finally:
                    engine.dispose()
                backup = self.service.create_backup()
                original = Path(backup.filepath).read_bytes()
                self._migrate(self.database); self._insert_title("current")
                plan = self.service.plan_restore(backup.filepath)
                restored = self.service.restore_backup(plan, plan.confirmation_token)
                self.assertTrue(restored.success)
                connection = sqlite3.connect(self.database)
                try:
                    self.assertEqual(connection.execute("SELECT title,is_favorite FROM tracks WHERE id=7").fetchone(), ("histÃ³ric âœ“", 1))
                    self.assertEqual(connection.execute("SELECT position FROM playlist_tracks WHERE playlist_id=3 AND track_id=7").fetchone()[0], 2)
                    self.assertEqual(connection.execute("SELECT count(*) FROM collection_tracks WHERE collection_id=4 AND track_id=7").fetchone()[0], 1)
                    self.assertEqual(connection.execute("SELECT count(*) FROM collection_rules WHERE collection_id=4").fetchone()[0], 1)
                    self.assertEqual(connection.execute("SELECT count(*) FROM track_history WHERE track_id=7").fetchone()[0], 1)
                    self.assertIsNone(connection.execute("PRAGMA foreign_key_check").fetchone())
                    if count >= 3:
                        self.assertEqual(connection.execute("SELECT genre,bitrate FROM tracks WHERE id=7").fetchone(), ("House", None))
                    if count >= 5:
                        self.assertEqual(connection.execute("SELECT count(*) FROM track_metadata_history WHERE track_id=7").fetchone()[0], 1)
                finally:
                    connection.close()
                self.assertEqual(Path(backup.filepath).read_bytes(), original)

    def test_restore_rejects_future_history_and_keeps_current_database(self):
        self._insert_title("current")
        valid_backup = self.service.create_backup()
        with zipfile.ZipFile(valid_backup.filepath) as archive:
            database_payload = archive.read("database.sqlite")
            settings_payload = archive.read("settings.json")
        future_database = self.root / "future.sqlite"
        future_database.write_bytes(database_payload)
        connection = sqlite3.connect(future_database)
        try:
            connection.execute("INSERT INTO schema_migrations (version) VALUES ('0006_future')")
            connection.commit()
        finally:
            connection.close()
        future_archive = self.root / "future.zip"
        manifest = replace(
            valid_backup.verification.manifest,
            backup_id="future_fixture",
            database_schema_version="0006_future",
            files=(
                ("database.sqlite", future_database.stat().st_size, self.service._sha256_path(future_database)),
                ("settings.json", len(settings_payload), hashlib.sha256(settings_payload).hexdigest()),
            ),
        )
        settings_file = self.root / "future-settings.json"
        settings_file.write_bytes(settings_payload)
        self.service._write_zip(future_archive, (("database.sqlite", future_database), ("settings.json", settings_file)), manifest)
        with self.assertRaises(BackupVerificationError):
            self.service.plan_restore(future_archive)
        self.assertEqual(self._title(), "current")

    def test_restore_migration_failures_preserve_active_database_and_archive(self):
        from app.database.migrations import MIGRATIONS
        self.database.unlink(missing_ok=True)
        engine = create_engine(f"sqlite:///{self.database.as_posix()}")
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE schema_migrations (version VARCHAR(64) PRIMARY KEY NOT NULL)"))
            for version, _description, function_name in MIGRATIONS[:1]:
                getattr(__import__("app.database.migrations", fromlist=[function_name]), function_name)(connection)
                connection.execute(text("INSERT INTO schema_migrations (version) VALUES (:version)"), {"version": version})
            connection.execute(text("INSERT INTO tracks (id,title,artist,filepath) VALUES (7,'historic','artist','historic.wav')"))
        engine.dispose()
        backup = self.service.create_backup()
        archive_bytes = Path(backup.filepath).read_bytes()
        self._migrate(self.database)
        self._insert_title("current")

        failing = BackupRestoreService(
            self.settings, self.database, self.logging_service.get_logger("backup-failure"),
            close_connections=self._closed, migration_runner=lambda _candidate: None,
        )
        plan = failing.plan_restore(backup.filepath)
        result = failing.restore_backup(plan, plan.confirmation_token)
        self.assertFalse(result.success)
        self.assertEqual(self._title(), "current")
        self.assertEqual(Path(backup.filepath).read_bytes(), archive_bytes)
        self.assertTrue(any(entry.reason == "pre_action" for entry in self.service.list_backups()))
