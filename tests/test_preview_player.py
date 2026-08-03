import json
import tempfile
import unittest
from pathlib import Path

from app.services.app_logging_service import AppLoggingService
from app.services.preview_player import (
    DeterministicPlaybackBackend,
    PlaybackBackendUnavailableError,
    PlaybackClosedError,
    PlaybackOperationError,
    PreviewPlayerService,
    PreviewPlayerState,
    PreviewTrackDTO,
    TrackFileNotFoundError,
    TrackNotLoadedError,
    UnsupportedAudioFormatError,
)
from app.services.settings_service import LoggingSettingsDTO


class PreviewPlayerServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.track = self.root / "private_song.mp3"; self.track.write_bytes(b"not audio; fake backend only")
        self.track_two = self.root / "other.flac"; self.track_two.write_bytes(b"fake")
        self.backend = DeterministicPlaybackBackend(duration_ms=1200)
        self.service = PreviewPlayerService(self.backend, initial_volume=0.4)

    def tearDown(self):
        self.service.close(); self.temp.cleanup()

    def _load(self, path=None):
        return self.service.load_track(PreviewTrackDTO(str(path or self.track), track_id=7, title="Private title"))

    def test_initial_load_and_supported_file_validation(self):
        self.assertEqual(self.service.snapshot().state, PreviewPlayerState.EMPTY)
        loaded = self._load()
        self.assertEqual((loaded.state, loaded.duration_ms, loaded.volume), (PreviewPlayerState.READY, 1200, 0.4))
        self.assertEqual(self._load().state, PreviewPlayerState.READY)
        with self.assertRaises(TrackFileNotFoundError): self.service.load_track(PreviewTrackDTO(str(self.root / "missing.wav")))
        bad = self.root / "bad.ogg"; bad.write_bytes(b"x")
        with self.assertRaises(UnsupportedAudioFormatError): self.service.load_track(PreviewTrackDTO(str(bad)))

    def test_play_pause_resume_toggle_stop_and_unload(self):
        self._load(); self.assertEqual(self.service.play().state, PreviewPlayerState.PLAYING)
        self.assertEqual(self.service.pause().state, PreviewPlayerState.PAUSED)
        self.assertEqual(self.service.toggle_play_pause().state, PreviewPlayerState.PLAYING)
        self.assertEqual(self.service.stop().state, PreviewPlayerState.STOPPED)
        self.assertEqual(self.service.unload().state, PreviewPlayerState.EMPTY)
        with self.assertRaises(TrackNotLoadedError): self.service.play()

    def test_seek_volume_track_change_end_and_backend_error(self):
        self._load(); self.assertEqual(self.service.seek(-10).position_ms, 0)
        self.assertEqual(self.service.seek(99999).position_ms, 1200)
        self.assertEqual(self.service.set_volume(0.0).volume, 0.0)
        self.assertEqual(self.service.set_volume(1.0).volume, 1.0)
        with self.assertRaises(PlaybackOperationError): self.service.set_volume(1.1)
        self._load(self.track_two); self.assertEqual(self.service.snapshot().volume, 1.0)
        self.backend.finish(); self.assertEqual(self.service.snapshot().state, PreviewPlayerState.ENDED)
        self.backend.emit_error(); self.assertEqual((self.service.snapshot().state, self.service.snapshot().error), (PreviewPlayerState.ERROR, "playback_error"))

    def test_non_seekable_close_idempotence_and_no_late_events(self):
        service = PreviewPlayerService(DeterministicPlaybackBackend(seekable=False))
        events = []
        service.subscribe(lambda event, _snapshot: events.append(event))
        try:
            service.load_track(PreviewTrackDTO(str(self.track)))
            with self.assertRaises(PlaybackOperationError): service.seek(10)
            service.close(); size = len(events); service.close()
            with self.assertRaises(PlaybackClosedError): service.play()
            self.assertEqual(len(events), size)
        finally:
            service.close()

    def test_events_are_ordered_snapshot_is_immutable_and_logging_is_sanitized(self):
        log_directory = self.root / "logs"
        logging_service = AppLoggingService(LoggingSettingsDTO(directory=str(log_directory)))
        service = PreviewPlayerService(DeterministicPlaybackBackend(), logger=logging_service.get_logger("preview"))
        events = []
        service.subscribe(lambda event, snapshot: events.append((event, snapshot.state)))
        try:
            snapshot = service.load_track(PreviewTrackDTO(str(self.track), title="Private title")); service.play(); service.pause()
            self.assertEqual(events[:3], [("state_changed", PreviewPlayerState.LOADING), ("state_changed", PreviewPlayerState.READY), ("track_loaded", PreviewPlayerState.READY)])
            with self.assertRaises(Exception): snapshot.volume = 1.0
            logging_service.flush(); content = logging_service.get_current_log_file().read_text(encoding="utf-8")
            self.assertNotIn(str(self.track), content); self.assertNotIn("Private title", content)
            self.assertIn("preview_track_loaded", content)
        finally:
            service.close(); logging_service.shutdown()

    def test_unavailable_backend_is_controlled(self):
        service = PreviewPlayerService(DeterministicPlaybackBackend(available=False))
        try:
            self.assertEqual(service.snapshot().state, PreviewPlayerState.ERROR)
            with self.assertRaises(PlaybackBackendUnavailableError): service.set_volume(0.5)
        finally:
            service.close()

    def test_backend_load_failure_is_isolated_as_error_state(self):
        service = PreviewPlayerService(DeterministicPlaybackBackend(fail_load=True))
        try:
            result = service.load_track(PreviewTrackDTO(str(self.track)))
            self.assertEqual((result.state, result.error), (PreviewPlayerState.ERROR, "playback_error"))
        finally:
            service.close()
