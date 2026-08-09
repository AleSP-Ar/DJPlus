import os
import json
from pathlib import Path

from app.database import SessionLocal
from app.database.models import Track
from app.services.filepath_normalization import normalize_filepath
from sqlalchemy import or_


class TrackRepository:
    def __init__(self, session=None):
        self.session = session or SessionLocal()

    def get_tracks(self, limit=None):
        query = self.session.query(Track)

        if limit:
            query = query.limit(limit)

        return query.all()

    def get_all_tracks(self):
        return self.session.query(Track).all()

    def get_by_filepath(self, filepath):
        normalized = normalize_filepath(filepath)
        candidates = {normalized}
        try:
            candidates.add(os.path.relpath(normalized, Path.cwd()))
        except ValueError:
            pass
        return self.session.query(Track).filter(Track.filepath.in_(candidates)).one_or_none()

    def get_by_id(self, track_id):
        """Resolve one track for an application service inside its UnitOfWork."""
        return self.session.get(Track, track_id)

    def update_analysis_metadata(self, track, values, provenance=None, commit=True):
        """Apply the already-authorized subset of analysis fields atomically."""
        for field in ("bpm", "key", "energy"):
            if field in values:
                setattr(track, field, values[field])
        for field, value in (provenance or {}).items():
            setattr(track, field, value)
        self._finish(commit)
        return track

    def update_track_metadata(self, track, values, commit=True):
        """Apply a validated user-metadata patch inside the caller UnitOfWork."""
        for field in ("title", "artist", "album", "label", "genre", "rating", "bpm", "key", "energy", "primary_genre_confidence", "secondary_genres_json", "styles_json"):
            if field in values:
                setattr(track, field, values[field])
        self._finish(commit)
        return track

    def record_metadata_edit(self, track_id, fields, previous, new, origin, status, commit=True):
        from app.database.models import TrackMetadataHistory
        entry = TrackMetadataHistory(track_id=track_id, fields_json=json.dumps(tuple(fields)), previous_json=json.dumps(previous), new_json=json.dumps(new), origin=origin, status=status)
        self.session.add(entry); self._finish(commit); return entry

    def latest_metadata_edit(self, track_id):
        from app.database.models import TrackMetadataHistory
        return self.session.query(TrackMetadataHistory).filter_by(track_id=track_id).order_by(TrackMetadataHistory.id.desc()).first()

    def create_from_import(self, filepath, metadata, file_size, modified_at, commit=True):
        track = Track(
            filepath=normalize_filepath(filepath),
            title=metadata.title,
            artist=metadata.artist,
            album=metadata.album,
            genre=metadata.genre,
            bpm=metadata.bpm,
            key=metadata.key,
            duration=metadata.duration,
            bitrate=metadata.bitrate,
            sample_rate=metadata.sample_rate,
            import_file_size=file_size,
            import_file_modified_at=modified_at,
        )
        self.session.add(track)
        self._finish(commit)
        return track

    def update_from_import(self, track, metadata, file_size, modified_at, commit=True):
        track.title = metadata.title
        track.artist = metadata.artist
        track.album = metadata.album
        track.genre = metadata.genre
        track.bpm = metadata.bpm
        track.key = metadata.key
        track.duration = metadata.duration
        track.bitrate = metadata.bitrate
        track.sample_rate = metadata.sample_rate
        track.import_file_size = file_size
        track.import_file_modified_at = modified_at
        self._finish(commit)
        return track

    def _build_library_query(self, search, filters):
        query = self.session.query(Track)

        if search.text:
            pattern = f"%{search.text}%"
            query = query.filter(or_(Track.artist.ilike(pattern), Track.title.ilike(pattern), Track.album.ilike(pattern)))

        for field in ("artist", "title", "album", "key"):
            value = getattr(search, field)
            if value:
                query = query.filter(getattr(Track, field).ilike(f"%{value}%"))

        if search.bpm is not None:
            query = query.filter(Track.bpm == search.bpm)
        if search.rating is not None:
            query = query.filter(Track.rating == search.rating)
        if search.date_added is not None:
            query = query.filter(Track.created_at == search.date_added)

        if search.genre:
            query = query.filter(Track.genre.ilike(f"%{search.genre}%"))
        if filters.genre:
            query = query.filter(Track.genre.ilike(f"%{filters.genre}%"))
        if filters.label:
            query = query.filter(Track.label.ilike(f"%{filters.label}%"))

        if filters.bpm_min is not None:
            query = query.filter(Track.bpm >= filters.bpm_min)
        if filters.bpm_max is not None:
            query = query.filter(Track.bpm <= filters.bpm_max)
        if filters.key:
            query = query.filter(Track.key.ilike(f"%{filters.key}%"))
        if filters.rating_min is not None:
            query = query.filter(Track.rating >= filters.rating_min)
        if filters.rating_max is not None:
            query = query.filter(Track.rating <= filters.rating_max)
        if filters.date_added_from is not None:
            query = query.filter(Track.created_at >= filters.date_added_from)
        if filters.date_added_to is not None:
            query = query.filter(Track.created_at <= filters.date_added_to)
        if filters.favorite is not None:
            query = query.filter(Track.is_favorite == filters.favorite)

        return query

    def query_tracks(self, search, filters, sort, limit=None, offset=0):
        query = self._build_library_query(search, filters)

        columns = {
            "title": Track.title,
            "artist": Track.artist,
            "album": Track.album,
            "bpm": Track.bpm,
            "key": Track.key,
            "rating": Track.rating,
            "duration": Track.duration,
            "date_added": Track.created_at,
        }
        order_column = Track.genre if sort.column == "genre" else columns[sort.column]
        order = order_column.desc() if sort.direction == "desc" else order_column.asc()
        query = query.order_by(order, Track.id.asc())
        if limit is not None:
            query = query.limit(limit).offset(offset)
        return query.all()

    def count_query_tracks(self, search, filters):
        """Return the total for the active library query without materializing tracks."""
        return self._build_library_query(search, filters).order_by(None).count()

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

    def iter_ranking_rows(self, *, batch_size, filters, excluded_track_ids=(), cancellation=None):
        """Yield only score-required scalar columns in stable id order."""
        query = self.session.query(Track.id, Track.bpm, Track.key, Track.energy, Track.rating, Track.genre, Track.is_favorite, Track.duration, Track.filepath)
        if excluded_track_ids: query = query.filter(~Track.id.in_(tuple(excluded_track_ids)))
        if filters.get("bpm_min") is not None: query = query.filter(Track.bpm >= filters["bpm_min"])
        if filters.get("bpm_max") is not None: query = query.filter(Track.bpm <= filters["bpm_max"])
        if filters.get("key"): query = query.filter(Track.key.ilike(f"%{filters['key']}%"))
        if filters.get("genre"): query = query.filter(Track.genre.ilike(f"%{filters['genre']}%"))
        if filters.get("favorite") is not None: query = query.filter(Track.is_favorite == filters["favorite"])
        query = query.order_by(Track.id.asc()).yield_per(batch_size)
        batch = []
        for row in query:
            if cancellation is not None and callable(getattr(cancellation, "is_cancelled", None)) and cancellation.is_cancelled(): break
            batch.append(row)
            if len(batch) == batch_size: yield tuple(batch); batch = []
        if batch: yield tuple(batch)

    def close(self):
        self.session.close()

    def _finish(self, commit):
        if commit:
            self.session.commit()
        else:
            self.session.flush()
