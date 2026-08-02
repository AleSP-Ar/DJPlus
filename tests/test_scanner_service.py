import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.filepath_normalization import normalize_filepath
from app.services.scanner_service import ScannerService


class ScannerServiceTests(unittest.TestCase):
    def test_discovers_supported_files_recursively_and_ignores_others(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "nested"
            nested.mkdir()
            (root / "first.mp3").touch()
            (nested / "second.WAV").touch()
            (nested / "notes.txt").touch()

            events = list(ScannerService().discover(root))

        discovered = {Path(event.filepath).name for event in events if event.event_type == "item"}
        self.assertEqual(discovered, {"first.mp3", "second.WAV"})
        self.assertFalse(any(event.event_type == "error" for event in events))

    def test_reports_root_and_directory_access_errors(self):
        missing_events = list(ScannerService().discover("missing-import-root"))
        self.assertEqual(missing_events[0].event_type, "error")

        with tempfile.TemporaryDirectory() as directory:
            with patch("app.services.scanner_service.Path.iterdir", side_effect=PermissionError("blocked")):
                events = list(ScannerService().discover(directory))

        self.assertEqual(events[0].event_type, "error")
        self.assertIn("blocked", events[0].error_message)

    def test_supports_configured_extensions_and_cooperative_cancellation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "first.flac").touch()
            (root / "second.mp3").touch()

            configured_events = list(ScannerService(extensions=["flac"]).discover(root))
            cancelled_events = list(ScannerService().discover(root, cancel_requested=lambda: True))

        self.assertEqual([event.event_type for event in configured_events], ["item"])
        self.assertEqual(Path(configured_events[0].filepath).name, "first.flac")
        self.assertEqual([event.event_type for event in cancelled_events], ["cancelled"])

    def test_discovery_uses_centralized_absolute_filepath_normalization(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            audio_file = root / "first.mp3"
            audio_file.touch()
            relative_root = root.relative_to(Path.cwd())

            event = next(ScannerService().discover(relative_root))

        self.assertEqual(event.filepath, normalize_filepath(str(audio_file)))
