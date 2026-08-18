import inspect
import json
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
    genre: str | None = None
    primary_genre_confidence: float | None = None
    secondary_genres_json: str | None = None
    styles_json: str | None = None


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
        result = self.engine.score(self.reference, Track(2, 125, "8A", 75, genre="organic_house"))

        self.assertIsInstance(result, RecommendationScoreDTO)
        self.assertEqual(result.score, 100)
        self.assertEqual([reason.criterion for reason in result.reasons], ["genre", "key", "bpm", "energy", "history"])
        self.assertEqual(self.history.calls, [(2, "played")])

    def test_missing_and_distant_values_reduce_score_deterministically(self):
        result = self.engine.score(self.reference, Track(3, 140, "9A", None, genre="peak_time_techno"))

        self.assertEqual(result.score, 0)
        self.assertIn("BPM distante", result.reasons[2].explanation)
        self.assertEqual(result.reasons[3].contribution, 0)
        self.assertEqual(result.reasons[4].contribution, 0)

    def test_genres_equal(self):
        result = self.engine.score(self.reference, Track(2, 124, "8A", 70, genre="organic_house"))
        self.assertEqual(result.reasons[0].criterion, "genre")
        self.assertEqual(result.reasons[0].contribution, 35)

    def test_compatible_transition(self):
        reference = Track(1, 124, "8A", 70, genre="organic_house")
        candidate = Track(2, 124, "8A", 70, genre="progressive_house")
        result = self.engine.score(reference, candidate)
        self.assertGreater(result.score, 80)
        self.assertEqual(result.reasons[0].contribution, 35)

    def test_directed_transition(self):
        reference = Track(1, 124, "8A", 70, genre="progressive_house")
        candidate = Track(2, 124, "8A", 70, genre="melodic_house_and_techno")
        result = self.engine.score(reference, candidate)
        self.assertGreater(result.score, 80)

    def test_strong_genre_incompatibility_limits_final_score(self):
        reference = Track(1, 124, "8A", 70, genre="peak_time_techno")
        candidate = Track(2, 124, "8A", 70, genre="progressive_trance")
        result = self.engine.score(reference, candidate)
        self.assertLess(result.score, 80)
        self.assertEqual(result.reasons[0].contribution, 7)

    def test_styles_improve_compatibility(self):
        reference = Track(1, 124, "8A", 70, genre="organic_house", styles_json=json.dumps([("deep", "Deep", 0.9)]))
        candidate = Track(2, 124, "8A", 70, genre="progressive_trance", styles_json=json.dumps([("deep", "Deep", 0.9)]))
        result = self.engine.score(reference, candidate)
        self.assertGreater(result.score, 70)

    def test_missing_genre_reduces_confidence(self):
        with_genre = self.engine.score(self.reference, Track(2, 124, "8A", 70, genre="organic_house"))
        without_genre = self.engine.score(self.reference, Track(2, 124, "8A", 70))
        self.assertGreater(with_genre.confidence, without_genre.confidence)

    def test_missing_genre_keeps_a_concrete_harmonic_and_tempo_match(self):
        result = self.engine.score(self.reference, Track(2, 125, "8A", 82))
        self.assertGreater(result.score, 0)
        self.assertLess(result.confidence, 1)

    def test_genre_incompatible_and_key_bpm_compatible_do_not_produce_high_score(self):
        reference = Track(1, 124, "8A", 70, genre="peak_time_techno")
        candidate = Track(2, 124, "8A", 70, genre="progressive_trance")
        result = self.engine.score(reference, candidate)
        self.assertLess(result.score, 70)

    def test_result_is_deterministic(self):
        reference = Track(1, 124, "8A", 70, genre="organic_house")
        candidate = Track(2, 124, "8A", 70, genre="progressive_house")
        first = self.engine.score(reference, candidate)
        second = self.engine.score(reference, candidate)
        self.assertEqual(first, second)

    def test_validates_service_history_and_has_no_ranking_or_repository_access(self):
        with self.assertRaises(TypeError):
            RecommendationScoringEngine(object(), self.history)
        with self.assertRaises(RecommendationScoringError):
            self.engine.score(self.reference, Track(0, 120, "8A", 60))
        source = inspect.getsource(__import__("app.services.recommendation_scoring", fromlist=["*"]))
        for forbidden in ("app.repository", "sqlite3", "sorted(", "ranking", "generate"):
            self.assertNotIn(forbidden, source.casefold())
