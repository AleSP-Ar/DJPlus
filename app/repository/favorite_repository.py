from app.database import SessionLocal
from app.database.models import Track


class FavoriteRepository:
    """Persistence boundary for the favorite state of tracks."""

    def __init__(self, session=None):
        self.session = session or SessionLocal()

    def mark_favorite(self, track_id):
        track = self._require_track(track_id)
        track.is_favorite = True
        self.session.commit()
        return track

    def remove_favorite(self, track_id):
        track = self._require_track(track_id)
        track.is_favorite = False
        self.session.commit()
        return track

    def list_favorites(self):
        return (
            self.session.query(Track)
            .filter(Track.is_favorite.is_(True))
            .order_by(Track.artist.asc(), Track.title.asc(), Track.id.asc())
            .all()
        )

    def is_favorite(self, track_id):
        return self._require_track(track_id).is_favorite

    def close(self):
        self.session.close()

    def _require_track(self, track_id):
        track = self.session.get(Track, track_id)
        if track is None:
            raise ValueError("La pista no existe.")
        return track
