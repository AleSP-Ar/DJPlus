from sqlalchemy import func

from app.database import SessionLocal
from app.database.models import Collection, Track


class CollectionRepository:
    """Persistence boundary for manual collection membership."""

    def __init__(self, session=None):
        self.session = session or SessionLocal()

    def create_collection(self, name, description=None, color=None, icon=None, collection_type="manual"):
        collection = Collection(
            name=self._validate_name(name),
            description=description,
            color=color,
            icon=icon,
            type=collection_type,
        )
        self.session.add(collection)
        self.session.commit()
        return collection

    def rename_collection(self, collection_id, name):
        collection = self._require_collection(collection_id)
        collection.name = self._validate_name(name, excluding_id=collection_id)
        self.session.commit()
        return collection

    def delete_collection(self, collection_id):
        collection = self._require_collection(collection_id)
        self.session.delete(collection)
        self.session.commit()

    def get_collection(self, collection_id):
        return self.session.get(Collection, collection_id)

    def list_collections(self):
        return self.session.query(Collection).order_by(Collection.name.asc(), Collection.id.asc()).all()

    def add_track(self, collection_id, track_id):
        collection = self._require_collection(collection_id)
        track = self._require_track(track_id)
        if track not in collection.tracks:
            collection.tracks.append(track)
            self.session.commit()
        return collection

    def remove_track(self, collection_id, track_id):
        collection = self._require_collection(collection_id)
        track = self._require_track(track_id)
        if track in collection.tracks:
            collection.tracks.remove(track)
            self.session.commit()
        return collection

    def list_tracks(self, collection_id):
        collection = self._require_collection(collection_id)
        return sorted(collection.tracks, key=lambda track: (track.artist.casefold(), track.title.casefold(), track.id))

    def count_tracks(self, collection_id):
        self._require_collection(collection_id)
        return (
            self.session.query(Track)
            .join(Track.collections)
            .filter(Collection.id == collection_id)
            .count()
        )

    def close(self):
        self.session.close()

    def _require_collection(self, collection_id):
        collection = self.get_collection(collection_id)
        if collection is None:
            raise ValueError("La colección no existe.")
        return collection

    def _require_track(self, track_id):
        track = self.session.get(Track, track_id)
        if track is None:
            raise ValueError("La pista no existe.")
        return track

    def _validate_name(self, name, excluding_id=None):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("El nombre de la colección es obligatorio.")
        cleaned = name.strip()
        query = self.session.query(Collection).filter(func.lower(Collection.name) == cleaned.casefold())
        if excluding_id is not None:
            query = query.filter(Collection.id != excluding_id)
        if query.first() is not None:
            raise ValueError("Ya existe una colección con ese nombre.")
        return cleaned
