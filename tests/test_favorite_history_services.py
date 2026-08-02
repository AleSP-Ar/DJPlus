import unittest

from app.services.favorite_service import FavoriteService
from app.services.history_service import HistoryService


class FakeRepository:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def method(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return name
        return method


class FavoriteAndHistoryServiceTests(unittest.TestCase):
    def test_favorite_service_delegates(self):
        repository = FakeRepository()
        service = FavoriteService(repository=repository)
        service.mark_favorite(1)
        service.remove_favorite(1)
        service.list_favorites()
        self.assertEqual([call[0] for call in repository.calls], ["mark_favorite", "remove_favorite", "list_favorites"])

    def test_history_service_uses_typed_events_and_queries(self):
        repository = FakeRepository()
        service = HistoryService(repository=repository)
        service.record_track_selected(1)
        service.record_track_played(1)
        service.record_track_added(1)
        service.record_track_used_in_playlist(1)
        service.list_history(track_id=1, event_type="played", limit=5)
        self.assertEqual(
            repository.calls,
            [
                ("record_event", (1, "selected"), {}),
                ("record_event", (1, "played"), {}),
                ("record_event", (1, "added"), {"commit": True}),
                ("record_event", (1, "playlist_used"), {}),
                ("list_history", (1, "played", 5), {}),
            ],
        )
