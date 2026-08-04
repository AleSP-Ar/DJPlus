import unittest

from PySide6.QtWidgets import QApplication

from app.services.preview_player import PlaybackBackendUnavailableError, QtMultimediaPlaybackBackend
from PySide6.QtMultimedia import QMediaPlayer
from qt_test_helpers import ensure_qapplication


class _Signal:
    def __init__(self): self._slots = []
    def connect(self, slot): self._slots.append(slot)
    def disconnect(self, slot): self._slots.remove(slot)
    def emit(self, *args):
        for slot in tuple(self._slots): slot(*args)


class _Player:
    def __init__(self):
        self.positionChanged, self.durationChanged, self.playbackStateChanged, self.mediaStatusChanged, self.errorOccurred = (_Signal(), _Signal(), _Signal(), _Signal(), _Signal())
        self.position_value, self.duration_value, self.deleted = 0, 0, False
    def setAudioOutput(self, value): self.audio = value
    def setSource(self, value): self.source = value
    def play(self): self.playbackStateChanged.emit(QMediaPlayer.PlaybackState.PlayingState)
    def pause(self): self.playbackStateChanged.emit(QMediaPlayer.PlaybackState.PausedState)
    def stop(self): self.playbackStateChanged.emit(QMediaPlayer.PlaybackState.StoppedState)
    def setPosition(self, value): self.position_value = value; self.positionChanged.emit(value)
    def position(self): return self.position_value
    def duration(self): return self.duration_value
    def deleteLater(self): self.deleted = True


class _Audio:
    def setVolume(self, value): self.volume = value
    def deleteLater(self): self.deleted = True


class QtMultimediaPlaybackBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = ensure_qapplication()
        if not isinstance(cls.application, QApplication):
            raise AssertionError("El fixture multimedia requiere QApplication.")

    def test_unavailable_qt_multimedia_is_typed(self):
        with self.assertRaises(PlaybackBackendUnavailableError):
            QtMultimediaPlaybackBackend(qt_available=False)

    def test_controlled_creation_volume_seek_and_idempotent_close_without_playback(self):
        backend = QtMultimediaPlaybackBackend()
        self.assertEqual(backend.name, "qt_multimedia")
        backend.set_volume(0.25); backend.seek(0)
        backend.close(); backend.close()
        self.assertEqual((backend.get_position(), backend.get_duration()), (0, 0))

    def test_injected_qt_signals_translate_and_disconnect_without_media_playback(self):
        player, audio, events = _Player(), _Audio(), []
        backend = QtMultimediaPlaybackBackend(lambda: player, lambda: audio)
        backend.set_event_callback(lambda event, payload: events.append((event, payload)))
        player.duration_value = 900; player.durationChanged.emit(900)
        player.setPosition(120); player.play(); player.pause(); player.errorOccurred.emit()
        self.assertEqual(events[0], ("duration", {"duration_ms": 900}))
        self.assertIn(("state", {"state": "playing"}), events)
        self.assertEqual(events[-1], ("error", {"error": "qt_multimedia_error"}))
        backend.close(); count = len(events); player.positionChanged.emit(200)
        self.assertEqual((len(events), player.deleted, audio.deleted), (count, True, True))
