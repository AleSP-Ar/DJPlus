import inspect
import unittest
from dataclasses import dataclass

from app.services.dj_intelligence_service import DJIntelligenceService
from app.services.recommendation_scoring import RecommendationScoringEngine, RecommendationScoringError, RecommendationScoreDTO


@dataclass(frozen=True)
class Track:
    id: int
    bpm: float | None
    key: str | None
    energy: float | None


class HistoryServiceDouble:
    def __init__(self, counts=None):
        self.counts = counts or {}
        self.calls = []

    def count_history(self, track_id=None, event_type=None):
        self.calls.append((track_id, event_type))
        return self.counts.get(track_id, 0)


class RecommendationScoringTests(unittest.TestCase):
    def setUp(self):
        self.history = HistoryServiceDouble({2: 6, 3: 1})
        self.engine = RecommendationScoringEngine(DJIntelligenceService(), self.history)
        self.reference = Track(1, 124, "8A", 70)

    def test_scores_all_criteria_with_explainable_reasons(self):
        result = self.engine.score(self.reference, Track(2, 125, "8A", 75))

        self.assertIsInstance(result, RecommendationScoreDTO)
        self.assertEqual(result.score, 100)
        self.assertEqual([reason.criterion for reason in result.reasons], ["bpm", "key", "energy", "history"])
        self.assertEqual(self.history.calls, [(2, "played")])

    def test_missing_and_distant_values_reduce_score_deterministically(self):
        result = self.engine.score(self.reference, Track(3, 140, "9A", None))

        self.assertEqual(result.score, 8)
        self.assertIn("BPM distante", result.reasons[0].explanation)
        self.assertEqual(result.reasons[2].contribution, 0)
        self.assertEqual(result.reasons[3].contribution, 8)

    def test_validates_service_history_and_has_no_ranking_or_repository_access(self):
        with self.assertRaises(TypeError):
            RecommendationScoringEngine(object(), self.history)
        with self.assertRaises(RecommendationScoringError):
            self.engine.score(self.reference, Track(0, 120, "8A", 60))
        source = inspect.getsource(__import__("app.services.recommendation_scoring", fromlist=["*"]))
        for forbidden in ("app.repository", "sqlite3", "sorted(", "ranking", "generate"):
            self.assertNotIn(forbidden, source.casefold())
