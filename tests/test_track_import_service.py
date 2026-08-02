import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, Playlist, PlaylistTrack, Track, TrackHistory
from app.database.unit_of_work import UnitOfWork
from app.repository.import_repository import ImportRepository
from app.services.metadata_service import TrackMetadata
from app.services.filepath_normalization import normalize_filepath
from app.services.track_import_service import TrackImportService


class TrackImportServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.session = self.session_factory()
        self.imports = ImportRepository(session=self.session)
        self.service = TrackImportService(
            unit_of_work_factory=lambda: UnitOfWork(session_factory=self.session_factory)
        )
        self.metadata = TrackMetadata(
            title="Imported Title",
            artist="Imported Artist",
            album="Imported Album",
            genre="House",
            bpm=124.0,
            key="8A",
            duration=210.0,
            bitrate=320000,
            sample_rate=44100,
        )

    def tearDown(self):
        self.session.close()

    def test_new_file_creates_track_history_and_imported_item(self):
        with tempfile.TemporaryDirectory() as directory:
            filepath = self._write_file(directory, "new.mp3", b"new")
            item = self._reading_item(filepath)
            result = self.service.process(item.id, self.metadata)

        self.session.expire_all()
        track = self.session.get(Track, result.track_id)
        self.assertEqual(result.action, "created")
        self.assertEqual(track.title, "Imported Title")
        self.assertEqual(track.genre, "House")
        self.assertEqual(self.session.query(TrackHistory).filter_by(track_id=track.id, event_type="added").count(), 1)
        self.assertEqual(self.imports.get_item(item.id).status, "imported")

    def test_intact_file_is_skipped_without_library_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            filepath = self._write_file(directory, "same.mp3", b"same")
            size, modified_at = self._snapshot(filepath)
            track = Track(
                title="Original",
                artist="Artist",
                filepath=normalize_filepath(filepath),
                rating=4,
                is_favorite=True,
                import_file_size=size,
                import_file_modified_at=modified_at,
            )
            self.session.add(track)
            self.session.commit()
            item = self._reading_item(filepath)
            result = self.service.process(item.id, self.metadata)

        self.session.expire_all()
        self.assertEqual(result.action, "skipped")
        self.assertEqual(self.session.get(Track, track.id).title, "Original")
        self.assertEqual(self.imports.get_item(item.id).status, "skipped")
        self.assertEqual(self.session.query(TrackHistory).filter_by(track_id=track.id).count(), 0)

    def test_relative_legacy_filepath_matches_an_absolute_import_path(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            filepath = self._write_file(directory, "legacy.mp3", b"same")
            relative_filepath = str(Path(filepath).relative_to(Path.cwd()))
            size, modified_at = self._snapshot(filepath)
            track = Track(
                title="Original",
                artist="Artist",
                filepath=relative_filepath,
                import_file_size=size,
                import_file_modified_at=modified_at,
            )
            self.session.add(track)
            self.session.commit()
            item = self._reading_item(filepath)

            result = self.service.process(item.id, self.metadata)

        self.session.expire_all()
        self.assertEqual(result.action, "skipped")
        self.assertEqual(self.session.query(Track).count(), 1)
        self.assertEqual(self.imports.get_item(item.id).filepath, str(Path(filepath).resolve()))

    def test_modified_file_updates_metadata_and_preserves_user_data(self):
        with tempfile.TemporaryDirectory() as directory:
            filepath = self._write_file(directory, "changed.mp3", b"changed-content")
            track = Track(
                title="Old Title",
                artist="Old Artist",
                filepath=normalize_filepath(filepath),
                rating=5,
                is_favorite=True,
                import_file_size=1,
                import_file_modified_at=datetime(2020, 1, 1),
            )
            playlist = Playlist(name="Keep me")
            self.session.add_all((track, playlist))
            self.session.flush()
            self.session.add(PlaylistTrack(playlist_id=playlist.id, track_id=track.id, position=0))
            self.session.add(TrackHistory(track_id=track.id, event_type="selected"))
            self.session.commit()
            item = self._reading_item(filepath)
            result = self.service.process(item.id, self.metadata)

        self.session.expire_all()
        updated = self.session.get(Track, track.id)
        self.assertEqual(result.action, "updated")
        self.assertEqual(updated.title, "Imported Title")
        self.assertEqual(updated.genre, "House")
        self.assertEqual(updated.bitrate, 320000)
        self.assertEqual(updated.sample_rate, 44100)
        self.assertEqual(updated.rating, 5)
        self.assertTrue(updated.is_favorite)
        self.assertEqual(self.session.query(PlaylistTrack).filter_by(track_id=track.id).count(), 1)
        self.assertEqual(self.session.query(TrackHistory).filter_by(track_id=track.id, event_type="selected").count(), 1)
        self.assertEqual(self.imports.get_item(item.id).status, "imported")

    def test_rolls_back_track_history_and_item_state_when_history_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            filepath = self._write_file(directory, "rollback.mp3", b"rollback")
            item = self._reading_item(filepath)
            with patch(
                "app.database.unit_of_work.HistoryRepository.record_event",
                side_effect=RuntimeError("history failed"),
            ):
                with self.assertRaises(RuntimeError):
                    self.service.process(item.id, self.metadata)

        self.session.expire_all()
        self.assertEqual(self.session.query(Track).count(), 0)
        self.assertEqual(self.session.query(TrackHistory).count(), 0)
        self.assertEqual(self.imports.get_item(item.id).status, "reading_metadata")

    def _reading_item(self, filepath):
        job = self.imports.create_job()
        item = self.imports.add_item(job.id, filepath)
        return self.imports.update_item_status(item.id, "reading_metadata")

    def _write_file(self, directory, filename, content):
        filepath = Path(directory) / filename
        filepath.write_bytes(content)
        return str(filepath)

    def _snapshot(self, filepath):
        stat_result = Path(filepath).stat()
        return stat_result.st_size, datetime.fromtimestamp(stat_result.st_mtime, timezone.utc).replace(tzinfo=None)
