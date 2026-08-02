from app.repository.playlist_repository import PlaylistRepository
from app.services.history_service import HistoryService


class PlaylistService:
    """Application API for ordered playlists."""

    def __init__(self, repository=None, history_service=None):
        self.repository = repository or PlaylistRepository()
        self.history_service = history_service or HistoryService()

    def create_playlist(self, name, description=None):
        return self.repository.create_playlist(name, description)

    def rename_playlist(self, playlist_id, name):
        return self.repository.rename_playlist(playlist_id, name)

    def delete_playlist(self, playlist_id):
        return self.repository.delete_playlist(playlist_id)

    def list_playlists(self):
        return self.repository.list_playlists()

    def add_track(self, playlist_id, track_id):
        entry = self.repository.add_track(playlist_id, track_id)
        self.history_service.record_track_used_in_playlist(track_id)
        return entry

    def remove_track(self, playlist_id, track_id):
        return self.repository.remove_track(playlist_id, track_id)

    def move_track(self, playlist_id, track_id, position):
        return self.repository.move_track(playlist_id, track_id, position)

    def list_tracks(self, playlist_id):
        return self.repository.list_tracks(playlist_id)

    def count_tracks(self, playlist_id):
        return self.repository.count_tracks(playlist_id)

    def close(self):
        self.repository.close()
        self.history_service.close()
