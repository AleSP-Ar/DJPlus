import os
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

        if search.genre or filters.genre:
            raise ValueError("El filtro genre requiere una migración de esquema aprobada.")

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
        if sort.column == "genre":
            raise ValueError("El orden genre requiere una migración de esquema aprobada.")

        order_column = columns[sort.column]
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

    def close(self):
        self.session.close()

    def _finish(self, commit):
        if commit:
            self.session.commit()
        else:
            self.session.flush()
