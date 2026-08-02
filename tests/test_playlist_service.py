import unittest

from app.services.playlist_service import PlaylistService


class FakePlaylistRepository:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def method(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return name
        return method


class FakeHistoryService:
    def __init__(self):
        self.track_ids = []

    def record_track_used_in_playlist(self, track_id):
        self.track_ids.append(track_id)

    def close(self):
        pass


class PlaylistServiceTests(unittest.TestCase):
    def setUp(self):
        self.repository = FakePlaylistRepository()
        self.history_service = FakeHistoryService()
        self.service = PlaylistService(repository=self.repository, history_service=self.history_service)

    def test_playlist_operations_delegate_to_repository(self):
        self.service.create_playlist("Set")
        self.service.rename_playlist(1, "Opening")
        self.service.delete_playlist(1)
        self.service.add_track(1, 10)
        self.service.remove_track(1, 10)
        self.service.move_track(1, 10, 0)
        self.service.list_tracks(1)
        self.service.count_tracks(1)
        self.assertEqual(
            [call[0] for call in self.repository.calls],
            ["create_playlist", "rename_playlist", "delete_playlist", "add_track", "remove_track", "move_track", "list_tracks", "count_tracks"],
        )
        self.assertEqual(self.history_service.track_ids, [10])
