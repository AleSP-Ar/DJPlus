import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, Track
from app.repository.history_repository import HistoryRepository
from app.services.history_service import HistoryService
from app.services.preview_player import (
    AudioOutputDeviceDTO, DeterministicPlaybackBackend, HistoryPlaybackPortAdapter,
    PlaybackBackendUnavailableError, PreviewPlayerService, PreviewTrackDTO, create_preview_player_service,
)
from app.services.settings_service import SettingsService


class _HistoryPort:
    def __init__(self, fail=False): self.calls, self.fail = [], fail
    def record_played(self, track_id):
        self.calls.append(track_id)
        if self.fail: raise RuntimeError("history unavailable")


class PreviewDevicesAndHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "track.mp3"; self.path.write_bytes(b"fake")
        self.devices = (
            AudioOutputDeviceDTO("default", "Default", True, True, "deterministic"),
            AudioOutputDeviceDTO("usb", "USB Output", False, True, "deterministic"),
            AudioOutputDeviceDTO("gone", "Disconnected", False, False, "deterministic"),
        )

    def tearDown(self): self.temp.cleanup()
    def _track(self, track_id=7): return PreviewTrackDTO(str(self.path), track_id=track_id)

    def test_devices_select_default_and_persist_explicitly(self):
        settings = SettingsService(Path(self.temp.name) / "settings.json")
        backend = DeterministicPlaybackBackend(devices=self.devices)
        service = PreviewPlayerService(backend, settings_service=settings)
        try:
            self.assertEqual([item.device_id for item in service.list_output_devices()], ["default", "usb", "gone"])
            self.assertEqual(service.select_output_device("usb").output_device_id, "usb")
            service.set_volume(.25); service.save_preferences()
            persisted = settings.get().preview_player
            self.assertEqual((persisted.volume, persisted.output_device_id), (.25, "usb"))
            self.assertEqual(service.use_default_output_device().output_device_id, "default")
        finally: service.close()

    def test_missing_configured_device_falls_back_by_description_then_default(self):
        settings = SettingsService(Path(self.temp.name) / "settings.json")
        settings.update({"preview_player": {"volume": .4, "output_device_id": "missing", "output_device_description": "USB Output"}})
        service = PreviewPlayerService(DeterministicPlaybackBackend(devices=self.devices), settings_service=settings)
        try:
            self.assertEqual(service.load_preferences().output_device_id, "usb")
            settings.update({"preview_player": {"output_device_id": "missing", "output_device_description": "missing"}})
            self.assertEqual(service.load_preferences().output_device_id, "default")
        finally: service.close()

    def test_no_output_device_remains_controlled_and_degraded(self):
        service = PreviewPlayerService(DeterministicPlaybackBackend(devices=()))
        try:
            snapshot = service.snapshot()
            self.assertFalse(snapshot.output_available)
            self.assertEqual(snapshot.degraded_reason, "no_output_device")
            self.assertEqual(service.list_output_devices(), ())
        finally: service.close()

    def test_factory_keeps_application_composable_when_qt_is_unavailable(self):
        with patch("app.services.preview_player.QtMultimediaPlaybackBackend", side_effect=PlaybackBackendUnavailableError("missing")):
            service = create_preview_player_service()
        try:
            self.assertEqual(service.snapshot().error, "backend_unavailable")
            self.assertFalse(service.snapshot().output_available)
        finally: service.close()

    def test_history_is_recorded_once_only_after_backend_playing(self):
        history = _HistoryPort(); service = PreviewPlayerService(DeterministicPlaybackBackend(), history_port=history)
        try:
            service.load_track(self._track()); service.seek(1); service.set_volume(.1)
            self.assertEqual(history.calls, [])
            service.play(); service.pause(); service.play(); service.stop(); service.play()
            self.assertEqual(history.calls, [7])
            service.load_track(self._track()); service.play()
            self.assertEqual(history.calls, [7, 7])
        finally: service.close()

    def test_history_failure_does_not_interrupt_playback(self):
        service = PreviewPlayerService(DeterministicPlaybackBackend(), history_port=_HistoryPort(fail=True))
        try:
            service.load_track(self._track()); snapshot = service.play()
            self.assertEqual(snapshot.state.value, "PLAYING")
        finally: service.close()

    def test_real_history_adapter_records_once(self):
        engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)(); track = Track(title="Preview", artist="DJPlus", filepath=str(self.path)); session.add(track); session.commit()
        history = HistoryService(HistoryRepository(session=session))
        service = PreviewPlayerService(DeterministicPlaybackBackend(), history_port=HistoryPlaybackPortAdapter(history))
        try:
            service.load_track(self._track(track.id)); service.play(); service.pause(); service.play()
            self.assertEqual(history.count_history(track_id=track.id, event_type="played"), 1)
        finally:
            service.close(); history.close(); engine.dispose()
