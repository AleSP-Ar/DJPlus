import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, Track
from app.repository.collection_repository import CollectionRepository
from app.repository.collection_rule_repository import CollectionRuleRepository
from app.repository.favorite_repository import FavoriteRepository
from app.repository.history_repository import HistoryRepository
from app.repository.playlist_repository import PlaylistRepository
from app.repository.track_repository import TrackRepository
from app.services.collection_service import CollectionService
from app.services.favorite_service import FavoriteService
from app.services.history_service import HistoryService
from app.services.library_service import LibraryService
from app.services.playlist_service import PlaylistService
from app.services.smart_collection_service import SmartCollectionService


class ReleaseIntegrationTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session = sessionmaker(bind=engine)()

    def tearDown(self):
        self.session.close()

    def test_import_library_favorite_playlist_history_and_smart_collection_flow(self):
        imported = Track(title="Peak Time", artist="DJ Plus", filepath="peak.mp3", bpm=124, rating=5)
        excluded = Track(title="Warmup", artist="DJ Plus", filepath="warmup.mp3", bpm=118, rating=5)
        self.session.add_all((imported, excluded))
        self.session.commit()

        history = HistoryService(HistoryRepository(session=self.session))
        history.record_track_added(imported.id)
        favorite = FavoriteService(FavoriteRepository(session=self.session))
        favorite.mark_favorite(imported.id)

        library = LibraryService(repository=TrackRepository(session=self.session))
        tracks, has_more = library.search("Peak")
        self.assertEqual([track.id for track in tracks], [imported.id])
        self.assertFalse(has_more)

        playlist = PlaylistService(
            repository=PlaylistRepository(session=self.session),
            history_service=history,
        )
        created_playlist = playlist.create_playlist("Saturday")
        playlist.add_track(created_playlist.id, imported.id)
        self.assertEqual([track.id for track in playlist.list_tracks(created_playlist.id)], [imported.id])

        collection_service = CollectionService(CollectionRepository(session=self.session))
        smart = SmartCollectionService(
            collection_service=collection_service,
            rule_repository=CollectionRuleRepository(session=self.session),
            library_service=LibraryService(repository=TrackRepository(session=self.session)),
        )
        smart_collection = smart.create_smart_collection(
            "Favorite peak time",
            rules=[
                {"field": "favorite", "operator": "=", "value": True},
                {"field": "bpm", "operator": ">=", "value": 122},
            ],
        )
        smart_tracks, smart_has_more, total = smart.evaluate(smart_collection.id)

        self.assertEqual([track.id for track in favorite.list_favorites()], [imported.id])
        self.assertEqual([track.id for track in smart_tracks], [imported.id])
        self.assertFalse(smart_has_more)
        self.assertEqual(total, 1)
        self.assertEqual(history.count_history(track_id=imported.id), 2)
