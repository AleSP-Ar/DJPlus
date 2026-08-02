import unittest

from app.services.collection_service import CollectionService


class FakeCollectionRepository:
    def __init__(self):
        self.calls = []

    def create_collection(self, *args, **kwargs):
        self.calls.append(("create_collection", args, kwargs))
        return "collection"

    def __getattr__(self, name):
        def method(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return name
        return method


class CollectionServiceTests(unittest.TestCase):
    def setUp(self):
        self.repository = FakeCollectionRepository()
        self.service = CollectionService(repository=self.repository)

    def test_create_collection_is_manual_and_delegated(self):
        self.assertEqual(self.service.create_collection("Warmup"), "collection")
        name, args, kwargs = self.repository.calls[0]
        self.assertEqual(name, "create_collection")
        self.assertEqual(args, ("Warmup", None, None, None))
        self.assertEqual(kwargs, {"collection_type": "manual"})

    def test_membership_and_collection_operations_delegate_to_repository(self):
        self.service.rename_collection(1, "Opening")
        self.service.delete_collection(1)
        self.service.add_track(1, 10)
        self.service.remove_track(1, 10)
        self.service.list_tracks(1)
        self.service.count_tracks(1)
        self.assertEqual([call[0] for call in self.repository.calls], ["rename_collection", "delete_collection", "add_track", "remove_track", "list_tracks", "count_tracks"])
