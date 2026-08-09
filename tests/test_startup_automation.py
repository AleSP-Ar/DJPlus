import tempfile
import unittest
from pathlib import Path

from app.services.settings_service import SettingsService
from app.services.startup_automation import StartupAutomationService


class _Backup:
    def __init__(self):
        self.created = 0
        self.retained = 0

    def create_backup(self, _request):
        self.created += 1
        return type("Result", (), {"success": True, "backup_path": "backup.zip"})()

    def apply_retention(self, protected_paths):
        self.retained += 1
        self.protected_paths = protected_paths


class _Importer:
    def __init__(self):
        self.paths = []

    def start(self, folder):
        self.paths.append(folder)


class _Signal:
    def __init__(self): self.callbacks = []
    def connect(self, callback): self.callbacks.append(callback)
    def emit(self):
        for callback in tuple(self.callbacks): callback()


class _CompletingImporter(_Importer):
    def __init__(self):
        super().__init__()
        self.import_completed = _Signal()


class _Metadata:
    def __init__(self):
        self.calls = 0

    def run(self):
        self.calls += 1


class _Analysis(_Metadata):
    pass


class StartupAutomationTests(unittest.TestCase):
    def test_enabled_backup_retention_and_scan_start_without_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = SettingsService(Path(directory) / "config.json")
            music = str(Path(directory) / "music")
            settings.update({"library": {"music_paths": [music], "default_music_path": music, "scan_on_start": True, "auto_external_metadata_enabled": True}, "analysis": {"auto_analysis_enabled": True}, "backup": {"auto_backup_enabled": True}})
            backup, importer, metadata, analysis = _Backup(), _Importer(), _Metadata(), _Analysis()
            automation = StartupAutomationService(settings, backup, importer, automatic_metadata_service=metadata, automatic_analysis_service=analysis, directory_exists=lambda value: value == music)
            self.assertEqual(set(automation.start()), {"backup", "metadata", "analysis", "scan"})
            automation._backup_thread.join(1)
            automation._metadata_thread.join(1)
            automation._analysis_thread.join(1)
            self.assertEqual(importer.paths, [music])
            self.assertEqual((backup.created, backup.retained, backup.protected_paths), (1, 1, ("backup.zip",)))
            self.assertEqual(metadata.calls, 1)
            self.assertEqual(analysis.calls, 1)

    def test_disabled_or_missing_folder_starts_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = SettingsService(Path(directory) / "config.json")
            settings.update({"library": {"scan_on_start": False, "auto_external_metadata_enabled": False}, "analysis": {"auto_analysis_enabled": False}, "backup": {"auto_backup_enabled": False}})
            backup, importer = _Backup(), _Importer()
            self.assertEqual(StartupAutomationService(settings, backup, importer).start(), ())
            self.assertEqual((backup.created, importer.paths), (0, []))

    def test_completed_import_starts_enabled_metadata_automation(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = SettingsService(Path(directory) / "config.json")
            settings.update({"library": {"auto_external_metadata_enabled": True}, "analysis": {"auto_analysis_enabled": False}, "backup": {"auto_backup_enabled": False}})
            metadata = _Metadata()
            importer = _CompletingImporter()
            automation = StartupAutomationService(settings, _Backup(), importer, automatic_metadata_service=metadata)
            importer.import_completed.emit()
            automation._metadata_thread.join(1)
            self.assertEqual(metadata.calls, 1)
