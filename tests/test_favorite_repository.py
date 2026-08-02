import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, Track
from app.repository.favorite_repository import FavoriteRepository


class FavoriteRepositoryTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session = sessionmaker(bind=engine)()
        self.repository = FavoriteRepository(session=self.session)
        self.first = Track(title="First", artist="Bravo", filepath="first.mp3")
        self.second = Track(title="Second", artist="Alpha", filepath="second.mp3")
        self.session.add_all((self.first, self.second))
        self.session.commit()

    def tearDown(self):
        self.session.close()

    def test_mark_remove_and_list_favorites(self):
        self.repository.mark_favorite(self.first.id)
        self.repository.mark_favorite(self.second.id)
        self.assertTrue(self.repository.is_favorite(self.first.id))
        self.assertEqual([track.id for track in self.repository.list_favorites()], [self.second.id, self.first.id])
        self.repository.remove_favorite(self.first.id)
        self.assertFalse(self.repository.is_favorite(self.first.id))
        self.assertEqual([track.id for track in self.repository.list_favorites()], [self.second.id])

    def test_unknown_track_is_rejected(self):
        with self.assertRaises(ValueError):
            self.repository.mark_favorite(999)
