from sqlalchemy import func

from app.database import SessionLocal
from app.database.models import Playlist, PlaylistTrack, Track


class PlaylistRepository:
    """Persistence boundary for ordered, duplicate-free playlists."""

    def __init__(self, session=None):
        self.session = session or SessionLocal()

    def create_playlist(self, name, description=None):
        playlist = Playlist(name=self._validate_name(name), description=description)
        self.session.add(playlist)
        self.session.commit()
        return playlist

    def rename_playlist(self, playlist_id, name):
        playlist = self._require_playlist(playlist_id)
        playlist.name = self._validate_name(name, excluding_id=playlist_id)
        self.session.commit()
        return playlist

    def delete_playlist(self, playlist_id):
        playlist = self._require_playlist(playlist_id)
        self.session.delete(playlist)
        self.session.commit()

    def list_playlists(self):
        return self.session.query(Playlist).order_by(Playlist.name.asc(), Playlist.id.asc()).all()

    def add_track(self, playlist_id, track_id):
        self._require_playlist(playlist_id)
        self._require_track(track_id)
        existing = self._entry_for_track(playlist_id, track_id)
        if existing is not None:
            return existing
        position = self.count_tracks(playlist_id)
        entry = PlaylistTrack(playlist_id=playlist_id, track_id=track_id, position=position)
        self.session.add(entry)
        self.session.commit()
        return entry

    def remove_track(self, playlist_id, track_id):
        self._require_playlist(playlist_id)
        entry = self._entry_for_track(playlist_id, track_id)
        if entry is None:
            raise ValueError("La pista no pertenece a la playlist.")
        self.session.delete(entry)
        self.session.flush()
        self._normalize_positions(playlist_id)
        self.session.commit()

    def move_track(self, playlist_id, track_id, position):
        self._require_playlist(playlist_id)
        entries = self._entries(playlist_id)
        entry = self._entry_for_track(playlist_id, track_id)
        if entry is None:
            raise ValueError("La pista no pertenece a la playlist.")
        if not isinstance(position, int) or not 0 <= position < len(entries):
            raise ValueError("La posición de destino no es válida.")
        entries.remove(entry)
        entries.insert(position, entry)
        self._write_positions(entries)
        self.session.commit()
        return entry

    def list_tracks(self, playlist_id):
        self._require_playlist(playlist_id)
        return [entry.track for entry in self._entries(playlist_id)]

    def count_tracks(self, playlist_id):
        self._require_playlist(playlist_id)
        return self.session.query(PlaylistTrack).filter(PlaylistTrack.playlist_id == playlist_id).count()

    def close(self):
        self.session.close()

    def _entries(self, playlist_id):
        return (
            self.session.query(PlaylistTrack)
            .filter(PlaylistTrack.playlist_id == playlist_id)
            .order_by(PlaylistTrack.position.asc(), PlaylistTrack.id.asc())
            .all()
        )

    def _entry_for_track(self, playlist_id, track_id):
        return (
            self.session.query(PlaylistTrack)
            .filter(PlaylistTrack.playlist_id == playlist_id, PlaylistTrack.track_id == track_id)
            .one_or_none()
        )

    def _normalize_positions(self, playlist_id):
        self._write_positions(self._entries(playlist_id))

    def _write_positions(self, entries):
        offset = len(entries) + 1
        for entry in entries:
            entry.position += offset
        self.session.flush()
        for position, entry in enumerate(entries):
            entry.position = position
        self.session.flush()

    def _require_playlist(self, playlist_id):
        playlist = self.session.get(Playlist, playlist_id)
        if playlist is None:
            raise ValueError("La playlist no existe.")
        return playlist

    def _require_track(self, track_id):
        track = self.session.get(Track, track_id)
        if track is None:
            raise ValueError("La pista no existe.")
        return track

    def _validate_name(self, name, excluding_id=None):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("El nombre de la playlist es obligatorio.")
        cleaned = name.strip()
        query = self.session.query(Playlist).filter(func.lower(Playlist.name) == cleaned.casefold())
        if excluding_id is not None:
            query = query.filter(Playlist.id != excluding_id)
        if query.first() is not None:
            raise ValueError("Ya existe una playlist con ese nombre.")
        return cleaned
