import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.services.automatic_metadata_service import AutomaticMetadataService
from app.services.metadata_candidate_proposal import MetadataProposalDTO
from app.services.settings_service import SettingsService
from app.services.track_metadata_editor import TrackMetadataDTO


class _Tracks:
    def __init__(self, track):
        self.track = track
        self.edits = []

    def get_tracks(self, limit):
        return [self.track][:limit]

    def get_by_id(self, track_id):
        return self.track if track_id == self.track.id else None

    def update_track_metadata(self, track, values, commit=False):
        for field, value in values.items():
            setattr(track, field, value)

    def record_metadata_edit(self, *values, **_kwargs):
        self.edits.append(values)


class _Unit:
    def __init__(self, tracks):
        self.tracks = tracks

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _ProposalService:
    def __init__(self, proposal):
        self.proposal = proposal

    def create_metadata_proposal(self, _track):
        return self.proposal


class AutomaticMetadataServiceTests(unittest.TestCase):
    def test_fills_only_empty_fields_when_proposal_reaches_threshold(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = SettingsService(Path(directory) / "config.json")
            settings.update({"library": {"auto_external_metadata_enabled": True, "external_metadata_confidence_threshold": 75}})
            track = SimpleNamespace(id=1, title="Directions", artist="1979", album=None, genre=None, rating=0, bpm=None, key=None, energy=0, label=None, secondary_genres_json=None, styles_json=None)
            proposal = MetadataProposalDTO(
                TrackMetadataDTO(1, "Directions", "1979", None, None, 0, None, None, 0),
                "progressive_house", "Progressive House", .80, 1, (),
                (("melodic_house", "Melodic House", .80),), (("progressive", "Progressive", .80),), (), (), (), (), proposed_label="Lost & Found", proposed_label_confidence=.80,
            )
            tracks = _Tracks(track)
            result = AutomaticMetadataService(settings, _ProposalService(proposal), lambda: _Unit(tracks)).run()
            self.assertEqual((result.inspected, result.updated, result.errors), (1, 1, 0))
            self.assertEqual((track.genre, track.label), ("Progressive House", "Lost & Found"))
            self.assertEqual(len(tracks.edits), 1)

    def test_does_not_overwrite_manual_values_or_low_confidence_proposals(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = SettingsService(Path(directory) / "config.json")
            settings.update({"library": {"auto_external_metadata_enabled": True, "external_metadata_confidence_threshold": 75}})
            track = SimpleNamespace(id=1, title="Directions", artist="1979", album=None, genre="House", rating=0, bpm=None, key=None, energy=0, label="Manual Label", secondary_genres_json="[]", styles_json="[]")
            proposal = MetadataProposalDTO(TrackMetadataDTO(1, "Directions", "1979", None, "House", 0, None, None, 0), "tech_house", "Tech House", .74, 1, (), (), (), (), (), (), ())
            tracks = _Tracks(track)
            result = AutomaticMetadataService(settings, _ProposalService(proposal), lambda: _Unit(tracks)).run()
            self.assertEqual((result.inspected, result.updated, result.skipped_low_confidence), (0, 0, 0))
            self.assertEqual((track.genre, track.label, tracks.edits), ("House", "Manual Label", []))

    def test_applies_a_confident_label_even_when_genre_is_not_resolved(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = SettingsService(Path(directory) / "config.json")
            settings.update({"library": {"auto_external_metadata_enabled": True, "external_metadata_confidence_threshold": 75}})
            track = SimpleNamespace(id=1, title="Track", artist="Artist", album=None, genre=None, rating=0, bpm=None, key=None, energy=0, label=None, secondary_genres_json=None, styles_json=None)
            proposal = MetadataProposalDTO(
                TrackMetadataDTO(1, "Track", "Artist", None, None, 0, None, None, 0),
                None, None, 0.0, 0, (), (), (), (), (), (), (),
                proposed_label="Lost & Found", proposed_label_confidence=.80,
            )
            tracks = _Tracks(track)
            result = AutomaticMetadataService(settings, _ProposalService(proposal), lambda: _Unit(tracks)).run()
            self.assertEqual((result.updated, track.label), (1, "Lost & Found"))

    def test_applies_a_confident_label_even_when_genre_is_not_resolved(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = SettingsService(Path(directory) / "config.json")
            settings.update({"library": {"auto_external_metadata_enabled": True, "external_metadata_confidence_threshold": 75}})
            track = SimpleNamespace(id=1, title="Track", artist="Artist", album=None, genre=None, rating=0, bpm=None, key=None, energy=0, label=None, secondary_genres_json=None, styles_json=None)
            proposal = MetadataProposalDTO(
                TrackMetadataDTO(1, "Track", "Artist", None, None, 0, None, None, 0),
                None, None, 0.0, 0, (), (), (), (), (), (), (),
                proposed_label="Lost & Found", proposed_label_confidence=.80,
            )
            tracks = _Tracks(track)
            result = AutomaticMetadataService(settings, _ProposalService(proposal), lambda: _Unit(tracks)).run()
            self.assertEqual((result.updated, track.label), (1, "Lost & Found"))
