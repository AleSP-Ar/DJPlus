import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, Track
from app.repository.collection_repository import CollectionRepository


class CollectionRepositoryTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session = sessionmaker(bind=engine)()
        self.repository = CollectionRepository(session=self.session)
        self.track_one = Track(title="First", artist="Artist A", filepath="first.mp3")
        self.track_two = Track(title="Second", artist="Artist B", filepath="second.mp3")
        self.session.add_all((self.track_one, self.track_two))
        self.session.commit()

    def tearDown(self):
        self.session.close()

    def test_create_list_rename_and_delete_collection(self):
        collection = self.repository.create_collection("Warmup", description="Opening tracks")
        self.assertEqual([item.name for item in self.repository.list_collections()], ["Warmup"])
        renamed = self.repository.rename_collection(collection.id, "Opening")
        self.assertEqual(renamed.name, "Opening")
        self.repository.delete_collection(collection.id)
        self.assertIsNone(self.repository.get_collection(collection.id))

    def test_collection_names_are_required_and_unique_case_insensitively(self):
        self.repository.create_collection("House")
        with self.assertRaises(ValueError):
            self.repository.create_collection(" house ")
        with self.assertRaises(ValueError):
            self.repository.create_collection("   ")

    def test_add_remove_and_list_tracks(self):
        collection = self.repository.create_collection("Set")
        self.repository.add_track(collection.id, self.track_two.id)
        self.repository.add_track(collection.id, self.track_one.id)
        self.repository.add_track(collection.id, self.track_one.id)
        self.assertEqual(self.repository.count_tracks(collection.id), 2)
        self.assertEqual([track.id for track in self.repository.list_tracks(collection.id)], [self.track_one.id, self.track_two.id])
        self.repository.remove_track(collection.id, self.track_one.id)
        self.assertEqual(self.repository.count_tracks(collection.id), 1)

    def test_unknown_collection_or_track_is_rejected(self):
        collection = self.repository.create_collection("Set")
        with self.assertRaises(ValueError):
            self.repository.add_track(collection.id, 999)
        with self.assertRaises(ValueError):
            self.repository.count_tracks(999)
