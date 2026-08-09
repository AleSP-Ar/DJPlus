import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.services.automatic_analysis_service import AutomaticAnalysisService
from app.services.settings_service import SettingsService


class _Tracks:
    def __init__(self, track):
        self.track, self.edits = track, []

    def get_tracks(self, limit): return [self.track][:limit]
    def get_by_id(self, track_id): return self.track if track_id == self.track.id else None
    def update_analysis_metadata(self, track, values, provenance, commit=False):
        for field, value in {**values, **provenance}.items(): setattr(track, field, value)
    def record_metadata_edit(self, *values, **_kwargs): self.edits.append(values)


class _Unit:
    def __init__(self, tracks): self.tracks = tracks
    def __enter__(self): return self
    def __exit__(self, *_args): return False


class _Analyzer:
    def analyze(self, _query):
        return SimpleNamespace(
            status="completed",
            features=SimpleNamespace(bpm=124.0, key="8A", energy=72),
            tempo_analysis=SimpleNamespace(confidence=.91),
            key_analysis=SimpleNamespace(confidence=.88),
        )


class AutomaticAnalysisServiceTests(unittest.TestCase):
    def test_fills_only_missing_analysis_values(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = SettingsService(Path(directory) / "config.json")
            settings.update({"analysis": {"auto_analysis_enabled": True}})
            track = SimpleNamespace(id=1, filepath="track.wav", bpm=None, key=None, energy=None)
            tracks = _Tracks(track)
            result = AutomaticAnalysisService(settings, _Analyzer(), lambda: _Unit(tracks)).run()
            self.assertEqual((result.inspected, result.updated, result.errors), (1, 1, 0))
            self.assertEqual((track.bpm, track.key, track.energy), (124.0, "8A", 72))
            self.assertEqual(len(tracks.edits), 1)

    def test_keeps_existing_analysis_values(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = SettingsService(Path(directory) / "config.json")
            settings.update({"analysis": {"auto_analysis_enabled": True}})
            track = SimpleNamespace(id=1, filepath="track.wav", bpm=120.0, key="7A", energy=65)
            tracks = _Tracks(track)
            result = AutomaticAnalysisService(settings, _Analyzer(), lambda: _Unit(tracks)).run()
            self.assertEqual((result.inspected, result.updated, tracks.edits), (0, 0, []))
            self.assertEqual((track.bpm, track.key, track.energy), (120.0, "7A", 65))
