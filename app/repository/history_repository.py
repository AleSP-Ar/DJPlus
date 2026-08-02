from app.database import SessionLocal
from app.database.models import Track, TrackHistory


class HistoryRepository:
    EVENT_TYPES = {"selected", "played", "added", "playlist_used"}

    def __init__(self, session=None):
        self.session = session or SessionLocal()

    def record_event(self, track_id, event_type, commit=True):
        self._require_track(track_id)
        if event_type not in self.EVENT_TYPES:
            raise ValueError("El tipo de evento de historial no es válido.")
        event = TrackHistory(track_id=track_id, event_type=event_type)
        self.session.add(event)
        if commit:
            self.session.commit()
        else:
            self.session.flush()
        return event

    def list_history(self, track_id=None, event_type=None, limit=None):
        query = self.session.query(TrackHistory)
        if track_id is not None:
            self._require_track(track_id)
            query = query.filter(TrackHistory.track_id == track_id)
        if event_type is not None:
            if event_type not in self.EVENT_TYPES:
                raise ValueError("El tipo de evento de historial no es válido.")
            query = query.filter(TrackHistory.event_type == event_type)
        query = query.order_by(TrackHistory.created_at.desc(), TrackHistory.id.desc())
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def count_history(self, track_id=None, event_type=None):
        query = self.session.query(TrackHistory)
        if track_id is not None:
            self._require_track(track_id)
            query = query.filter(TrackHistory.track_id == track_id)
        if event_type is not None:
            if event_type not in self.EVENT_TYPES:
                raise ValueError("El tipo de evento de historial no es válido.")
            query = query.filter(TrackHistory.event_type == event_type)
        return query.count()

    def close(self):
        self.session.close()

    def _require_track(self, track_id):
        track = self.session.get(Track, track_id)
        if track is None:
            raise ValueError("La pista no existe.")
        return track
