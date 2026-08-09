import json
import hashlib
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from app.services.ffmpeg_audio_decoder import FFmpegResolver
from app.services.settings_service import (
    CURRENT_SETTINGS_SCHEMA_VERSION,
    SettingsFutureVersionError,
    SettingsLoadError,
    SettingsPermissionError,
    SettingsService,
    SettingsValidationError,
)


class SettingsServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "isolated" / "config.json"
        self.service = SettingsService(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, value):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(value), encoding="utf-8")

    def test_missing_file_defaults_creation_save_reload_and_atomic_write(self):
        defaults = self.service.load()
        self.assertEqual(defaults.schema_version, CURRENT_SETTINGS_SCHEMA_VERSION)
        self.assertFalse(self.path.exists())
        saved = self.service.save(defaults)
        self.assertTrue(self.path.is_file())
        self.assertEqual(SettingsService(self.path).load(), saved)
        self.assertFalse(list(self.path.parent.glob("*.tmp")))

    def test_custom_path_normalizes_music_paths_and_partial_update(self):
        result = self.service.update({"library": {"music_paths": [str(Path(self.temp.name) / "music" / ".." / "music")], "page_size": 50}})
        self.assertEqual(self.service.get_config_path(), self.path)
        self.assertEqual(result.library.page_size, 50)
        self.assertEqual(result.library.music_paths, (str(Path(self.temp.name) / "music"),))
        self.assertEqual(SettingsService(self.path).load().library.page_size, 50)

    def test_library_automation_preferences_require_a_known_default_folder(self):
        music = str(Path(self.temp.name) / "music")
        result = self.service.update({"library": {
            "music_paths": [music],
            "default_music_path": music,
            "scan_on_start": True,
            "auto_external_metadata_enabled": True,
            "external_metadata_confidence_threshold": 75,
        }})
        self.assertEqual(result.library.default_music_path, music)
        self.assertTrue(result.library.scan_on_start)
        self.assertTrue(result.library.auto_external_metadata_enabled)
        self.assertEqual(result.library.external_metadata_confidence_threshold, 75)
        with self.assertRaises(SettingsValidationError):
            self.service.update({"library": {"default_music_path": str(Path(self.temp.name) / "other")}})

    def test_corrupt_json_recovers_to_defaults_with_backup_or_raises_typed_error(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("{corrupt", encoding="utf-8")
        recovered = self.service.load()
        self.assertEqual(recovered.schema_version, CURRENT_SETTINGS_SCHEMA_VERSION)
        self.assertTrue(self.path.with_name("config.json.corrupt.backup").is_file())
        self.path.write_text("{corrupt", encoding="utf-8")
        with self.assertRaises(SettingsLoadError):
            self.service.load(recover_corrupt=False)

    def test_rejects_invalid_and_unknown_fields(self):
        with self.assertRaises(SettingsValidationError):
            self.service.validate({"schema_version": CURRENT_SETTINGS_SCHEMA_VERSION, "library": {"page_size": 0}})
        with self.assertRaises(SettingsValidationError):
            self.service.validate({"schema_version": CURRENT_SETTINGS_SCHEMA_VERSION, "unknown": True})
        with self.assertRaises(SettingsValidationError):
            self.service.update({"analysis": {"format_priority": ["wav", "mp3", "flac", "aiff"]}})

    def test_schema_migration_backs_up_v1_and_rejects_future_versions(self):
        self._write({"schema_version": 1, "general": {"locale": "en-US"}, "library": {"page_size": 25}})
        migrated = self.service.load()
        self.assertEqual((migrated.schema_version, migrated.general.theme, migrated.library.page_size), (3, "system", 25))
        self.assertEqual(migrated.preview_player.volume, 0.70)
        self.assertTrue(self.path.with_name("config.json.v1.backup").is_file())
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["schema_version"], 3)
        self._write({"schema_version": CURRENT_SETTINGS_SCHEMA_VERSION + 1})
        with self.assertRaises(SettingsFutureVersionError):
            SettingsService(self.path).load()

    def test_reset_sanitized_export_and_secret_absence(self):
        self.service.update({"assistant": {"provider": "ollama", "model": "qwen", "options": {"temperature": "0.2"}}})
        exported = self.service.export_sanitized()
        self.assertEqual(exported["assistant"]["options"], {"temperature": "0.2"})
        self.assertFalse(any("token" in key.casefold() or "secret" in key.casefold() for key in json.dumps(exported).split('"')[1::2]))
        with self.assertRaises(SettingsValidationError):
            self.service.update({"assistant": {"options": {"api_key": "not-allowed"}}})
        self.assertEqual(self.service.reset_to_defaults().assistant.model, "llama3.2")

    def test_atomic_write_permission_failure_is_typed(self):
        service = SettingsService(self.path, replace_func=lambda *_args: (_ for _ in ()).throw(PermissionError("denied")))
        with self.assertRaises(SettingsPermissionError):
            service.save(service.defaults())
        self.assertFalse(list(self.path.parent.glob("*.tmp")))

    def test_directory_permission_failure_is_typed(self):
        with patch.object(Path, "mkdir", side_effect=PermissionError("denied")):
            with self.assertRaises(SettingsPermissionError):
                self.service.save(self.service.defaults())

    def test_concurrent_reads_are_immutable_and_safe(self):
        self.service.save(self.service.defaults())
        with ThreadPoolExecutor(max_workers=4) as executor:
            values = list(executor.map(lambda _index: self.service.get(), range(20)))
        self.assertTrue(all(value == values[0] and value.schema_version == CURRENT_SETTINGS_SCHEMA_VERSION for value in values))

    def test_preview_player_settings_validate_and_migrate_from_schema_two(self):
        self._write({"schema_version": 2, "general": {}, "library": {}})
        migrated = self.service.load()
        self.assertEqual((migrated.schema_version, migrated.preview_player.volume, migrated.preview_player.output_device_id), (3, 0.70, None))
        saved = self.service.update({"preview_player": {"volume": 0.25, "output_device_id": "device-a", "output_device_description": "Output A"}})
        self.assertEqual((saved.preview_player.volume, saved.preview_player.output_device_id), (0.25, "device-a"))
        with self.assertRaises(SettingsValidationError): self.service.update({"preview_player": {"volume": 1.1}})

    def test_ffmpeg_analysis_and_assistant_adapters_preserve_existing_defaults(self):
        configured, system = str(Path(self.temp.name) / "configured.exe"), str(Path(self.temp.name) / "path.exe")
        configured_result = self.service.update({"ffmpeg": {"configured_path": configured, "allow_path": True, "allow_bundled": False, "detection_timeout_seconds": 20}, "analysis": {"max_concurrency": 2, "block_frames": 2048, "timeout_seconds": 10}, "assistant": {"model": "qwen2.5", "timeout_ms": 5000}})
        resolver = self.service.create_ffmpeg_resolver(which=lambda _name: system, path_exists=lambda value: value in {configured, system})
        self.assertEqual((resolver.resolve().origin, self.service.ffmpeg_decoder_config().timeout_seconds), ("configured", 20))
        self.assertEqual((self.service.analysis_hardening_config().max_concurrency, self.service.analysis_hardening_config().timeout_ms), (2, 10000))
        self.assertEqual((self.service.assistant_provider_config().model, self.service.assistant_provider_config().timeout_ms), ("qwen2.5", 5000))
        self.assertEqual(configured_result.analysis.format_priority, ("mp3", "flac", "aiff", "wav"))
        self.service.update({"ffmpeg": {"configured_path": None, "allow_path": True, "allow_bundled": False}})
        self.assertEqual(self.service.create_ffmpeg_resolver(which=lambda _name: system, path_exists=lambda value: value == system).resolve().origin, "path")
        bundled = Path(self.temp.name) / "runtime" / "ffmpeg.exe"; bundled.parent.mkdir(); bundled.write_bytes(b"settings-bundled")
        (bundled.parent / "CHECKSUM.sha256").write_text(f"{hashlib.sha256(bundled.read_bytes()).hexdigest()}  ffmpeg.exe\n", encoding="utf-8")
        self.service.update({"ffmpeg": {"allow_path": False, "allow_bundled": True}})
        bundled_resolver = self.service.create_ffmpeg_resolver(which=lambda _name: system, bundled_path=str(bundled))
        self.assertEqual((bundled_resolver.resolve().origin, bundled_resolver.resolve().checksum_verified), ("bundled", True))

    def test_bundled_checksum_policy_cannot_be_disabled_when_runtime_is_allowed(self):
        with self.assertRaises(SettingsValidationError):
            self.service.update({"ffmpeg": {"allow_bundled": True, "validate_bundled_checksum": False}})
