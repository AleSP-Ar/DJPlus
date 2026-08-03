import inspect
import unittest
from dataclasses import dataclass

from app.services.dj_intelligence_service import DJIntelligenceService
from app.services.recommendation_scoring import RecommendationScoringEngine
from app.services.recommendation_service import RecommendationQueryDTO, RecommendationService, RecommendationServiceError


@dataclass(frozen=True)
class Track:
    id: int
    bpm: float | None
    key: str | None
    energy: float | None


class HistoryServiceDouble:
    def __init__(self, counts):
        self.counts = counts

    def count_history(self, track_id=None, event_type=None):
        return self.counts.get(track_id, 0)


class RecommendationServiceTests(unittest.TestCase):
    def setUp(self):
        engine = RecommendationScoringEngine(DJIntelligenceService(), HistoryServiceDouble({2: 5, 3: 0, 4: 5}))
        self.service = RecommendationService(engine)
        self.current = Track(1, 124, "8A", 70)

    def test_ranks_descending_excludes_current_and_preserves_reasons_confidence(self):
        query = RecommendationQueryDTO(self.current, (
            self.current,
            Track(2, 125, "8A", 75),
            Track(3, 140, "9A", 30),
        ))

        ranked = self.service.recommend(query)

        self.assertEqual([(item.rank, item.candidate_track_id, item.score) for item in ranked], [(1, 2, 100), (2, 3, 0)])
        self.assertEqual(len(ranked[0].reasons), 4)
        self.assertEqual(ranked[0].confidence, 1.0)

    def test_limit_and_deterministic_tie_break_use_candidate_id(self):
        query = RecommendationQueryDTO(self.current, (
            Track(4, 125, "8A", 75),
            Track(2, 125, "8A", 75),
            Track(3, 140, "9A", 30),
        ), limit=2)

        ranked = self.service.recommend(query)

        self.assertEqual([item.candidate_track_id for item in ranked], [2, 4])
        self.assertEqual([item.rank for item in ranked], [1, 2])

    def test_query_validation_and_service_have_no_persistence_or_ai_access(self):
        with self.assertRaises(RecommendationServiceError):
            RecommendationQueryDTO(self.current, (Track(2, 120, "8A", 60), Track(2, 120, "8A", 60)))
        with self.assertRaises(TypeError):
            RecommendationService(object())
        source = inspect.getsource(__import__("app.services.recommendation_service", fromlist=["*"])).casefold()
        for forbidden in ("app.repository", "sqlite3", "generative", "persist"):
            self.assertNotIn(forbidden, source)
