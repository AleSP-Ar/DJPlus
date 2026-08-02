from app.repository.history_repository import HistoryRepository


class HistoryService:
    """Application API for append-only track activity events."""

    def __init__(self, repository=None):
        self.repository = repository or HistoryRepository()

    def record_track_selected(self, track_id):
        return self.repository.record_event(track_id, "selected")

    def record_track_played(self, track_id):
        return self.repository.record_event(track_id, "played")

    def record_track_added(self, track_id, commit=True):
        return self.repository.record_event(track_id, "added", commit=commit)

    def record_track_used_in_playlist(self, track_id):
        return self.repository.record_event(track_id, "playlist_used")

    def list_history(self, track_id=None, event_type=None, limit=None):
        return self.repository.list_history(track_id, event_type, limit)

    def count_history(self, track_id=None, event_type=None):
        return self.repository.count_history(track_id, event_type)

    def close(self):
        self.repository.close()
