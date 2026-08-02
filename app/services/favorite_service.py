from app.repository.favorite_repository import FavoriteRepository


class FavoriteService:
    """Application API for favorite tracks."""

    def __init__(self, repository=None):
        self.repository = repository or FavoriteRepository()

    def mark_favorite(self, track_id):
        return self.repository.mark_favorite(track_id)

    def remove_favorite(self, track_id):
        return self.repository.remove_favorite(track_id)

    def list_favorites(self):
        return self.repository.list_favorites()

    def is_favorite(self, track_id):
        return self.repository.is_favorite(track_id)

    def close(self):
        self.repository.close()
