from app.repository.collection_repository import CollectionRepository


class CollectionService:
    """Application API used by the UI to manage manual collections."""

    def __init__(self, repository=None):
        self.repository = repository or CollectionRepository()

    def create_collection(self, name, description=None, color=None, icon=None):
        return self.repository.create_collection(name, description, color, icon, collection_type="manual")

    def create_smart_collection(self, name, description=None, color=None, icon=None):
        return self.repository.create_collection(name, description, color, icon, collection_type="smart")

    def rename_collection(self, collection_id, name):
        return self.repository.rename_collection(collection_id, name)

    def delete_collection(self, collection_id):
        return self.repository.delete_collection(collection_id)

    def get_collection(self, collection_id):
        return self.repository.get_collection(collection_id)

    def list_collections(self):
        return self.repository.list_collections()

    def add_track(self, collection_id, track_id):
        return self.repository.add_track(collection_id, track_id)

    def remove_track(self, collection_id, track_id):
        return self.repository.remove_track(collection_id, track_id)

    def list_tracks(self, collection_id):
        return self.repository.list_tracks(collection_id)

    def count_tracks(self, collection_id):
        return self.repository.count_tracks(collection_id)

    def close(self):
        self.repository.close()
