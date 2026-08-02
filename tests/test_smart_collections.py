import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, Collection, Track
from app.repository.collection_repository import CollectionRepository
from app.repository.collection_rule_repository import CollectionRuleRepository
from app.repository.track_repository import TrackRepository
from app.services.collection_service import CollectionService
from app.services.library_service import LibraryService
from app.services.smart_collection_service import SmartCollectionService
from app.services.smart_rule_engine import SmartRuleEngine


class Rule:
    def __init__(self, field, operator, value):
        self.field = field
        self.operator = operator
        self.value = value


class SmartRuleEngineTests(unittest.TestCase):
    def test_combines_supported_rules_with_and_filters(self):
        criteria = SmartRuleEngine().build_filters(
            [Rule("bpm", ">=", "122"), Rule("rating", ">=", "4"), Rule("favorite", "=", "true")]
        )
        self.assertEqual(criteria.bpm_min, 122.0)
        self.assertEqual(criteria.rating_min, 4)
        self.assertTrue(criteria.favorite)

    def test_rejects_unsupported_or_duplicate_rules(self):
        engine = SmartRuleEngine()
        with self.assertRaises(ValueError):
            engine.build_filters([Rule("genre", "=", "Progressive")])
        with self.assertRaises(ValueError):
            engine.build_filters([Rule("bpm", ">=", "120"), Rule("bpm", ">=", "122")])


class SmartCollectionTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session = sessionmaker(bind=engine)()
        tracks = [
            Track(title="Matches", artist="Artist", filepath="match.mp3", bpm=124, rating=5, is_favorite=True),
            Track(title="Low rating", artist="Artist", filepath="low.mp3", bpm=124, rating=3, is_favorite=True),
            Track(title="Low bpm", artist="Artist", filepath="slow.mp3", bpm=120, rating=5, is_favorite=True),
        ]
        self.session.add_all(tracks)
        self.session.commit()
        collection_service = CollectionService(CollectionRepository(session=self.session))
        rule_repository = CollectionRuleRepository(session=self.session)
        library_service = LibraryService(repository=TrackRepository(session=self.session))
        self.service = SmartCollectionService(
            collection_service=collection_service,
            rule_repository=rule_repository,
            library_service=library_service,
        )
        self.collection_service = collection_service

    def tearDown(self):
        self.session.close()

    def test_creates_rules_and_evaluates_expected_and_results(self):
        collection = self.service.create_smart_collection(
            "Favorites 122+",
            rules=[
                {"field": "bpm", "operator": ">=", "value": 122},
                {"field": "rating", "operator": ">=", "value": 4},
                {"field": "favorite", "operator": "=", "value": True},
            ],
        )
        tracks, has_more, total = self.service.evaluate(collection.id)
        self.assertEqual(collection.type, "smart")
        self.assertEqual(len(self.service.list_rules(collection.id)), 3)
        self.assertEqual([track.title for track in tracks], ["Matches"])
        self.assertFalse(has_more)
        self.assertEqual(total, 1)

    def test_manual_collections_cannot_receive_rules(self):
        manual = self.collection_service.create_collection("Manual")
        with self.assertRaises(ValueError):
            self.service.add_rule(manual.id, "bpm", ">=", 122)
