from app.database import SessionLocal
from app.database.models import Track


class TrackRepository:
    def __init__(self):
        self.session = SessionLocal()

    def get_tracks(self, limit=None):
        query = self.session.query(Track)

        if limit:
            query = query.limit(limit)

        return query.all()

    def search_tracks(self, text, limit=500):
        return (
            self.session.query(Track)
            .filter(
                (Track.artist.ilike(f"%{text}%")) |
                (Track.title.ilike(f"%{text}%")) |
                (Track.album.ilike(f"%{text}%"))
            )
            .limit(limit)
            .all()
        )

    def count_tracks(self):
        return self.session.query(Track).count()

    def close(self):
        self.session.close()
