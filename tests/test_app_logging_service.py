import json
import logging
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from app.services.app_logging_service import AppLoggingService, LoggingConfigurationError, StructuredLogSanitizer
from app.services.settings_service import LoggingSettingsDTO, SettingsService


class _BrokenRepr:
    def __repr__(self):
        raise AssertionError("repr must not run")


class AppLoggingServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name) / "logs"
        self.settings = LoggingSettingsDTO(directory=str(self.directory), max_bytes=1024, retained_files=2)
        self.service = AppLoggingService(self.settings, version="test-version")

    def tearDown(self):
        self.service.shutdown()
        self.temp.cleanup()

    def _events(self):
        self.service.flush()
        path = self.service.get_current_log_file()
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []

    def test_configuration_custom_directory_and_json_line_contract(self):
        logger = self.service.get_logger("analysis")
        logger.info("analysis finished", extra={"event_name": "analysis_done", "component": "analysis", "operation_id": "op-1", "context": {"tracks": 2}})
        event = self._events()[-1]
        self.assertEqual((event["logger"], event["event_name"], event["context"]), ("djplus.analysis", "analysis_done", {"tracks": 2}))
        self.assertTrue(event["timestamp_utc"].endswith("Z"))
        self.assertEqual((event["level"], event["version"]), ("INFO", "test-version"))
        self.assertEqual(self.service.get_log_directory(), self.directory)

    def test_sanitizer_redacts_recursively_limits_depth_and_never_calls_repr(self):
        sanitizer = StructuredLogSanitizer(max_depth=3, max_items=10, max_string_length=5)
        value = sanitizer.sanitize({"Authorization": "bearer", "safe": [{"token": "x"}, {"nested": {"more": "x"}}], "unknown": _BrokenRepr(), "long": "abcdef"})
        self.assertEqual(value["Authorization"], "[REDACTED]")
        self.assertEqual(value["safe"][0]["token"], "[REDACTED]")
        self.assertEqual(value["unknown"], "<_BrokenRepr>")
        self.assertEqual(value["long"], "abcde[TRUNCATED]")

    def test_rotation_retention_and_reconfiguration_prevent_duplicate_handlers(self):
        logger = self.service.get_logger("rotation")
        for index in range(60):
            logger.info("x" * 100, extra={"context": {"index": index}})
        self.service.flush()
        files = tuple(self.directory.glob("djplus.jsonl*"))
        self.assertLessEqual(len(files), 3)
        self.service.configure(LoggingSettingsDTO(directory=str(self.directory), max_bytes=2048, retained_files=1))
        root = logging.getLogger("djplus")
        self.assertEqual(len([handler for handler in root.handlers if handler.__class__.__name__ == "RotatingFileHandler"]), 1)

        replacement = AppLoggingService(LoggingSettingsDTO(directory=str(Path(self.temp.name) / "replacement")))
        try:
            self.assertEqual(len([handler for handler in root.handlers if handler.__class__.__name__ == "RotatingFileHandler"]), 1)
        finally:
            replacement.shutdown()

    def test_flush_shutdown_and_permission_failure_are_typed_and_idempotent(self):
        self.service.flush(); self.service.flush(); self.service.shutdown(); self.service.shutdown()
        with patch("app.services.app_logging_service.RotatingFileHandler", side_effect=PermissionError("denied")):
            with self.assertRaises(LoggingConfigurationError):
                AppLoggingService(LoggingSettingsDTO(directory=str(Path(self.temp.name) / "denied")))

    def test_concurrent_logging_and_exception_traceback(self):
        self.service.configure(LoggingSettingsDTO(directory=str(self.directory), max_bytes=64 * 1024, retained_files=1))
        logger = self.service.get_logger("worker")
        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(lambda index: logger.info("worker event", extra={"context": {"index": index}}), range(30)))
        try:
            raise RuntimeError("controlled")
        except RuntimeError:
            logger.error("worker failed", exc_info=True, extra={"event_name": "worker_error"})
        events = self._events()
        self.assertGreaterEqual(len(events), 31)
        self.assertEqual(events[-1]["exception_type"], "RuntimeError")
        self.assertIn("RuntimeError", events[-1]["traceback"])

    def test_explicit_sys_and_thread_hooks_preserve_previous_hooks(self):
        original_sys, original_thread = sys.excepthook, threading.excepthook
        calls = []
        try:
            sys.excepthook = lambda *_args: calls.append("sys")
            threading.excepthook = lambda _args: calls.append("thread")
            previous_sys, previous_thread = sys.excepthook, threading.excepthook
            self.service.install_exception_hooks()
            self.assertIsNot(sys.excepthook, original_sys)
            try:
                raise ValueError("hook")
            except ValueError as error:
                self.service._sys_hook(ValueError, error, error.__traceback__)
            self.assertIn("sys", calls)
            self.service.shutdown()
            self.assertIs(sys.excepthook, previous_sys)
            self.assertIs(threading.excepthook, previous_thread)
        finally:
            sys.excepthook, threading.excepthook = original_sys, original_thread

    def test_diagnostics_export_is_bounded_sanitized_and_excludes_audio_binary(self):
        settings = SettingsService(Path(self.temp.name) / "settings.json")
        settings.update({"library": {"music_paths": [str(Path(self.temp.name) / "private_music")]}, "logging": {"directory": str(self.directory)}})
        self.service.get_logger("ffmpeg").warning("decoder warning", extra={"context": {"token": "blocked", "filepath": "C:/private/song.mp3"}})
        target = Path(self.temp.name) / "support" / "diagnostics.json"
        result = self.service.export_diagnostics(target, settings, ffmpeg_diagnostics={"origin": "bundled", "access_token": "blocked"}, database_status={"status": "ready"}, max_bytes=4096)
        content = target.read_text(encoding="utf-8")
        self.assertEqual(result.size_bytes, target.stat().st_size)
        self.assertNotIn("blocked", content); self.assertNotIn("private_music", content); self.assertNotIn("song.mp3", content)
        self.assertNotIn("ffmpeg.exe", content); self.assertIn("[REDACTED]", content)
        self.assertEqual(len(result.sha256), 64)

    def test_settings_service_logging_defaults_are_consumed_explicitly(self):
        settings = SettingsService(Path(self.temp.name) / "settings.json")
        configured = settings.update({"logging": {"directory": str(Path(self.temp.name) / "configured"), "level": "WARNING", "max_bytes": 2048, "retained_files": 3}})
        service = AppLoggingService(configured.logging)
        try:
            self.assertEqual((service.get_log_directory(), logging.getLogger("djplus").level), (Path(configured.logging.directory), logging.WARNING))
        finally:
            service.shutdown()
