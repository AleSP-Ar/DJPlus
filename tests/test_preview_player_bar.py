import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from app.database import init_database
from app.services.preview_player import AudioOutputDeviceDTO, DeterministicPlaybackBackend, PreviewPlayerService, PreviewPlayerState, PreviewTrackDTO
from app.services.settings_service import SettingsService
from app.ui.main_window import MainWindow
from app.ui.widgets.preview_player_bar import PreviewPlayerBar, format_preview_time


class _History:
    def __init__(self): self.calls = []
    def record_played(self, track_id): self.calls.append(track_id)


class _LibraryHistory:
    def record_track_selected(self, _track_id): pass
    def close(self): pass


class PreviewPlayerBarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.track_path = Path(self.temp.name) / "private-title.mp3"; self.track_path.write_bytes(b"headless fake")
        self.devices = (
            AudioOutputDeviceDTO("default", "Default Output", True, True, "deterministic"),
            AudioOutputDeviceDTO("usb", "USB Output", False, True, "deterministic"),
        )
        self.history = _History()
        self.settings = SettingsService(Path(self.temp.name) / "settings.json")
        self.service = PreviewPlayerService(DeterministicPlaybackBackend(duration_ms=65000, devices=self.devices), history_port=self.history, settings_service=self.settings)
        self.bar = PreviewPlayerBar(self.service)

    def tearDown(self):
        self.bar.close(); self.service.close(); self.temp.cleanup()
    def _track(self, title="Title", artist="Artist"):
        return PreviewTrackDTO(str(self.track_path), track_id=5, title=title, artist=artist, duration_ms=65000)

    def test_time_format_and_empty_or_degraded_states(self):
        self.assertEqual((format_preview_time(None), format_preview_time(61000), format_preview_time(3661000)), ("--:--", "01:01", "1:01:01"))
        self.assertEqual(self.bar.track_label.text(), "Sin pista cargada")
        self.assertFalse(self.bar.play_button.isEnabled())
        degraded = PreviewPlayerService(DeterministicPlaybackBackend(available=False, devices=()))
        degraded_bar = PreviewPlayerBar(degraded)
        try:
            self.assertEqual(degraded_bar.state_label.text(), "Sin salida de audio")
            self.assertFalse(degraded_bar.play_button.isEnabled())
        finally:
            degraded_bar.close(); degraded.close()

    def test_explicit_load_transport_seek_volume_devices_and_no_filepath(self):
        self.bar.load_track(self._track())
        self.assertEqual(self.service.snapshot().state, PreviewPlayerState.READY)
        self.assertNotIn(str(self.track_path), self.bar.track_label.text())
        self.assertTrue(self.bar.play_button.isEnabled())
        self.bar.toggle_play_pause(); self.assertEqual(self.service.snapshot().state, PreviewPlayerState.PLAYING)
        self.bar.toggle_play_pause(); self.assertEqual(self.service.snapshot().state, PreviewPlayerState.PAUSED)
        self.bar.toggle_play_pause(); self.assertEqual(self.service.snapshot().state, PreviewPlayerState.PLAYING)
        self.bar.position_slider.setValue(12000); self.bar._finish_seek(); self.assertEqual(self.service.snapshot().position_ms, 12000)
        self.bar.volume_slider.setValue(0); self.assertEqual(self.service.snapshot().volume, 0.0)
        self.bar.volume_slider.setValue(100); self.bar._save_volume_preferences(); self.assertEqual(self.service.snapshot().volume, 1.0)
        self.assertEqual(self.settings.get().preview_player.volume, 1.0)
        self.bar.device_combo.setCurrentIndex(self.bar.device_combo.findData("usb")); self.assertEqual(self.service.snapshot().output_device_id, "usb")
        self.bar.stop(); self.assertEqual(self.service.snapshot().state, PreviewPlayerState.STOPPED)
        self.assertEqual(self.history.calls, [5])

    def test_fallbacks_errors_late_events_and_destroyed_callback(self):
        self.bar.load_track(self._track(title=None, artist=None))
        self.assertIn("Artista desconocido", self.bar.track_label.text())
        self.assertIn("Pista sin titulo", self.bar.track_label.text())
        missing = PreviewTrackDTO(str(Path(self.temp.name) / "missing.mp3"), track_id=1)
        self.bar.load_track(missing); self.assertTrue(self.bar.error_label.text())
        self.bar.load_track(self._track()); self.assertEqual(self.bar.error_label.text(), "")
        self.service._backend.emit_error("controlled")
        self.assertEqual(self.bar.state_label.text(), "Error")
        self.bar.close(); self.service._backend._emit("position", {"position_ms": 3})
        self.assertTrue(self.bar._closed)

    def test_main_window_integrates_bar_without_changing_library_layout(self):
        init_database(); window = MainWindow(preview_player_service=self.service)
        try:
            self.assertIsNotNone(window.preview_player_bar)
            self.assertFalse(window.library_view.load_preview_button.isHidden())
        finally:
            window.close()

    def test_library_explicit_active_row_loads_without_autoplay(self):
        init_database(); window = MainWindow(preview_player_service=self.service)
        try:
            library = window.library_view
            library.history_service.close(); library.history_service = _LibraryHistory()
            library.model.set_tracks([SimpleNamespace(id=5, filepath=str(self.track_path), title="From library", artist="DJ", album=None, bpm=None, key=None, duration=65, rating=0)])
            library.table.setCurrentIndex(library.model.index(0, 0))
            library.request_preview_load()
            self.assertEqual(self.service.snapshot().state, PreviewPlayerState.READY)
            self.assertEqual(self.history.calls, [])
            self.assertFalse(self.service.snapshot().state == PreviewPlayerState.PLAYING)
        finally:
            window.close()
