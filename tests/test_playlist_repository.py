import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, PlaylistTrack, Track
from app.repository.playlist_repository import PlaylistRepository


class PlaylistRepositoryTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session = sessionmaker(bind=engine)()
        self.repository = PlaylistRepository(session=self.session)
        self.tracks = [
            Track(title="First", artist="Artist", filepath="first.mp3"),
            Track(title="Second", artist="Artist", filepath="second.mp3"),
            Track(title="Third", artist="Artist", filepath="third.mp3"),
        ]
        self.session.add_all(self.tracks)
        self.session.commit()

    def tearDown(self):
        self.session.close()

    def test_create_rename_list_and_delete_playlist(self):
        playlist = self.repository.create_playlist("Opening", "First hour")
        self.assertEqual([item.name for item in self.repository.list_playlists()], ["Opening"])
        renamed = self.repository.rename_playlist(playlist.id, "Warmup")
        self.assertEqual(renamed.name, "Warmup")
        self.repository.delete_playlist(playlist.id)
        self.assertEqual(self.repository.list_playlists(), [])

    def test_membership_is_duplicate_free_and_preserves_insert_order(self):
        playlist = self.repository.create_playlist("Set")
        self.repository.add_track(playlist.id, self.tracks[1].id)
        self.repository.add_track(playlist.id, self.tracks[0].id)
        self.repository.add_track(playlist.id, self.tracks[1].id)
        self.assertEqual(self.repository.count_tracks(playlist.id), 2)
        self.assertEqual([track.id for track in self.repository.list_tracks(playlist.id)], [self.tracks[1].id, self.tracks[0].id])

    def test_move_track_reorders_contiguous_positions(self):
        playlist = self.repository.create_playlist("Set")
        for track in self.tracks:
            self.repository.add_track(playlist.id, track.id)
        self.repository.move_track(playlist.id, self.tracks[2].id, 0)
        self.assertEqual([track.id for track in self.repository.list_tracks(playlist.id)], [self.tracks[2].id, self.tracks[0].id, self.tracks[1].id])
        positions = self.session.query(PlaylistTrack.position).order_by(PlaylistTrack.position).all()
        self.assertEqual([position for (position,) in positions], [0, 1, 2])

    def test_remove_track_compacts_positions_and_relationships(self):
        playlist = self.repository.create_playlist("Set")
        for track in self.tracks:
            self.repository.add_track(playlist.id, track.id)
        self.repository.remove_track(playlist.id, self.tracks[1].id)
        self.assertEqual([track.id for track in self.repository.list_tracks(playlist.id)], [self.tracks[0].id, self.tracks[2].id])
        self.assertEqual(self.repository.count_tracks(playlist.id), 2)
        self.assertEqual([position for (position,) in self.session.query(PlaylistTrack.position).order_by(PlaylistTrack.position)], [0, 1])

    def test_invalid_membership_and_position_are_rejected(self):
        playlist = self.repository.create_playlist("Set")
        self.repository.add_track(playlist.id, self.tracks[0].id)
        with self.assertRaises(ValueError):
            self.repository.add_track(playlist.id, 999)
        with self.assertRaises(ValueError):
            self.repository.move_track(playlist.id, self.tracks[0].id, 1)
        with self.assertRaises(ValueError):
            self.repository.remove_track(playlist.id, self.tracks[1].id)
