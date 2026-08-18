import json
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import inspect, text

from app.database import init_database
from app.database.models import Track
from app.database.migrations import run_migrations
from app.services.metadata_candidate_proposal import MetadataProposalDTO
from app.services.music_classification_persistence_service import (
    ClassificationSelectionDTO,
    MusicClassificationPersistenceError,
    MusicClassificationPersistenceService,
)
from app.services.track_metadata_editor import TrackMetadataDTO


class MusicClassificationPersistenceServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="djplus-test-", dir=str(Path.cwd()))
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.engine = None
        self.session = None
        self._setup_database()

    def tearDown(self):
        if self.session is not None:
            self.session.close()
        if self.engine is not None:
            self.engine.dispose()
        self.temp_dir.cleanup()

    def _setup_database(self):
        import app.database as database_module
        from sqlalchemy import create_engine
        self.engine = create_engine(f"sqlite:///{self.db_path}")
        database_module.engine = self.engine
        database_module.SessionLocal = lambda: self.session_factory()
        database_module.Session = self.session_factory
        run_migrations(self.engine)
        self.session = self.session_factory()

    def session_factory(self):
        from sqlalchemy.orm import sessionmaker
        return sessionmaker(bind=self.engine)()

    def _create_track(self):
        track = Track(
            title="Song",
            artist="Artist",
            album="Album",
            genre="house",
            filepath="/tmp/test.mp3",
        )
        self.session.add(track)
        self.session.commit()
        return track

    def test_migration_creates_classification_columns(self):
        with self.engine.connect() as connection:
            columns = {column["name"] for column in inspect(connection).get_columns("tracks")}
        self.assertIn("primary_genre_confidence", columns)
        self.assertIn("secondary_genres_json", columns)
        self.assertIn("styles_json", columns)

    def test_apply_complete_proposal_persists_classification(self):
        track = self._create_track()
        service = MusicClassificationPersistenceService(unit_of_work_factory=lambda: self.session_factory())
        proposal = MetadataProposalDTO(
            current_metadata=TrackMetadataDTO(track_id=track.id, title=track.title, artist=track.artist, album=track.album, genre=track.genre, rating=0, bpm=None, key=None, energy=0),
            proposed_primary_genre_id="progressive_house",
            proposed_primary_genre_label="Progressive House",
            proposed_primary_confidence=0.91,
            proposed_evidence_count=2,
            candidate_genres=(("progressive_house", "Progressive House", 0.91, 2),),
            proposed_secondary_genres=(("deep_house", "Deep House", 0.8),),
            proposed_styles=(("deep", "Deep", 0.75),),
            conflicts=(),
            ambiguous_terms=(),
            unknown_terms=(),
            warnings=(),
        )

        result = service.apply_confirmed_proposal(proposal, confirmation=True)

        self.assertTrue(result["applied"])
        persisted = service.read_classification(track.id)
        self.assertEqual(persisted["primary_genre"], "Progressive House")
        self.assertEqual(persisted["primary_genre_confidence"], 0.91)
        self.assertEqual(persisted["secondary_genres"], [["deep_house", "Deep House", 0.8]])
        self.assertEqual(persisted["styles"], [["deep", "Deep", 0.75]])

    def test_apply_partial_selection_persists_only_selected_fields(self):
        track = self._create_track()
        service = MusicClassificationPersistenceService(unit_of_work_factory=lambda: self.session_factory())
        proposal = MetadataProposalDTO(
            current_metadata=TrackMetadataDTO(track_id=track.id, title=track.title, artist=track.artist, album=track.album, genre=track.genre, rating=0, bpm=None, key=None, energy=0),
            proposed_primary_genre_id="progressive_house",
            proposed_primary_genre_label="Progressive House",
            proposed_primary_confidence=0.91,
            proposed_evidence_count=1,
            candidate_genres=(),
            proposed_secondary_genres=(),
            proposed_styles=(),
            conflicts=(),
            ambiguous_terms=(),
            unknown_terms=(),
            warnings=(),
        )

        service.apply_confirmed_proposal(proposal, confirmation=True, selection=ClassificationSelectionDTO(genre=True, secondary_genres=False, styles=False))
        persisted = service.read_classification(track.id)

        self.assertEqual(persisted["primary_genre"], "Progressive House")
        self.assertEqual(persisted["secondary_genres"], None)
        self.assertEqual(persisted["styles"], None)

    def test_requires_confirmation(self):
        track = self._create_track()
        service = MusicClassificationPersistenceService(unit_of_work_factory=lambda: self.session_factory())
        proposal = MetadataProposalDTO(
            current_metadata=TrackMetadataDTO(track_id=track.id, title=track.title, artist=track.artist, album=track.album, genre=track.genre, rating=0, bpm=None, key=None, energy=0),
            proposed_primary_genre_id=None,
            proposed_primary_genre_label=None,
            proposed_primary_confidence=0.0,
            proposed_evidence_count=0,
            candidate_genres=(),
            proposed_secondary_genres=(),
            proposed_styles=(),
            conflicts=(),
            ambiguous_terms=(),
            unknown_terms=(),
            warnings=(),
        )

        with self.assertRaises(MusicClassificationPersistenceError):
            service.apply_confirmed_proposal(proposal, confirmation=False)

    def test_read_classification_returns_persisted_values(self):
        track = self._create_track()
        service = MusicClassificationPersistenceService(unit_of_work_factory=lambda: self.session_factory())
        with self.engine.begin() as connection:
            connection.execute(
                text("UPDATE tracks SET primary_genre_confidence = :value, secondary_genres_json = :secondary, styles_json = :styles WHERE id = :id"),
                {"value": 0.77, "secondary": json.dumps([("deep_house", "Deep House", 0.7)]), "styles": json.dumps([("deep", "Deep", 0.6)]), "id": track.id},
            )
        persisted = service.read_classification(track.id)
        self.assertEqual(persisted["primary_genre_confidence"], 0.77)
        self.assertEqual(persisted["secondary_genres"], [["deep_house", "Deep House", 0.7]])
        self.assertEqual(persisted["styles"], [["deep", "Deep", 0.6]])

    def test_undo_restores_previous_values(self):
        track = self._create_track()
        service = MusicClassificationPersistenceService(unit_of_work_factory=lambda: self.session_factory())
        proposal = MetadataProposalDTO(
            current_metadata=TrackMetadataDTO(track_id=track.id, title=track.title, artist=track.artist, album=track.album, genre=track.genre, rating=0, bpm=None, key=None, energy=0),
            proposed_primary_genre_id=None,
            proposed_primary_genre_label=None,
            proposed_primary_confidence=0.0,
            proposed_evidence_count=0,
            candidate_genres=(),
            proposed_secondary_genres=(),
            proposed_styles=(),
            conflicts=(),
            ambiguous_terms=(),
            unknown_terms=(),
            warnings=(),
        )
        service.apply_confirmed_proposal(proposal, confirmation=True)
        self.assertTrue(service.undo_last_classification(track.id))
        persisted = service.read_classification(track.id)
        self.assertEqual(persisted["primary_genre_confidence"], None)
        self.assertEqual(persisted["secondary_genres"], None)
        self.assertEqual(persisted["styles"], None)

    def test_undo_restores_artwork_bytes_from_an_authoritative_proposal(self):
        track = self._create_track()
        track.artwork_data = b"original-cover"
        track.artwork_mime = "image/jpeg"
        self.session.commit()
        service = MusicClassificationPersistenceService(unit_of_work_factory=lambda: self.session_factory())
        proposal = MetadataProposalDTO(
            current_metadata=TrackMetadataDTO(track.id, track.title, track.artist, track.album, track.genre, 0, None, None, 0),
            proposed_primary_genre_id=None, proposed_primary_genre_label=None, proposed_primary_confidence=0.0,
            proposed_evidence_count=0, candidate_genres=(), proposed_secondary_genres=(), proposed_styles=(),
            conflicts=(), ambiguous_terms=(), unknown_terms=(), warnings=(), source="beatport",
            identity_verified=True, auto_apply=True, artwork_data=b"beatport-cover", artwork_mime="image/png",
        )
        service.apply_confirmed_proposal(proposal, confirmation=True)
        self.assertTrue(service.undo_last_classification(track.id))
        with self.session_factory() as session:
            restored = session.get(Track, track.id)
            self.assertEqual(restored.artwork_data, b"original-cover")
            self.assertEqual(restored.artwork_mime, "image/jpeg")

    def test_does_not_modify_audio_file(self):
        track = self._create_track()
        service = MusicClassificationPersistenceService(unit_of_work_factory=lambda: self.session_factory())
        proposal = MetadataProposalDTO(
            current_metadata=TrackMetadataDTO(track_id=track.id, title=track.title, artist=track.artist, album=track.album, genre=track.genre, rating=0, bpm=None, key=None, energy=0),
            proposed_primary_genre_id=None,
            proposed_primary_genre_label=None,
            proposed_primary_confidence=0.0,
            proposed_evidence_count=0,
            candidate_genres=(),
            proposed_secondary_genres=(),
            proposed_styles=(),
            conflicts=(),
            ambiguous_terms=(),
            unknown_terms=(),
            warnings=(),
        )
        service.apply_confirmed_proposal(proposal, confirmation=True)
        self.assertEqual(Path("/tmp/test.mp3").exists(), False)


if __name__ == '__main__':
    unittest.main()
