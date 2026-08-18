import unittest
from dataclasses import dataclass

from app.services.dj_intelligence_service import DJIntelligenceService
from app.services.recommendation_scoring import RecommendationScoringEngine
from app.services.recommendation_service import RecommendationService
from app.services.set_planning import SetPlanQueryDTO, SetPlanningEngine, SetPlanningPolicyDTO, SetPlanningError


@dataclass(frozen=True)
class _Track:
    id: int
    bpm: float
    key: str
    energy: float


class _History:
    def count_history(self, track_id=None, event_type=None):
        return 0


class SetPlanningTests(unittest.TestCase):
    def setUp(self):
        service = RecommendationService(RecommendationScoringEngine(DJIntelligenceService(), _History()))
        self.engine = SetPlanningEngine(service, SetPlanningPolicyDTO(4, 12))
        self.initial = _Track(1, 120, "8A", 60)

    def test_builds_deterministic_sequence_with_transition_reasons(self):
        plan = self.engine.plan(SetPlanQueryDTO(self.initial, (_Track(3, 124, "8A", 70), _Track(2, 122, "8A", 65)), 3))

        self.assertEqual([track.track_id for track in plan.tracks], [1, 2, 3])
        self.assertFalse(plan.is_partial)
        self.assertEqual(tuple(reason.criterion for reason in plan.tracks[1].transition_reasons), ("bpm", "key", "energy", "history"))

    def test_returns_partial_plan_when_all_remaining_candidates_break_limits(self):
        plan = self.engine.plan(SetPlanQueryDTO(self.initial, (_Track(2, 140, "8A", 90),), 2))

        self.assertTrue(plan.is_partial)
        self.assertEqual([track.track_id for track in plan.tracks], [1])
        self.assertIn("no hay transiciones validas", plan.explanation)

    def test_validates_query_duplicates_and_uses_no_persistence(self):
        with self.assertRaises(SetPlanningError):
            SetPlanQueryDTO(self.initial, (_Track(2, 122, "8A", 65), _Track(2, 122, "8A", 65)), 2)

    def test_bounds_the_ranking_request_when_the_candidate_pool_exceeds_100(self):
        candidates = tuple(_Track(index, 122, "8A", 65) for index in range(2, 103))

        plan = self.engine.plan(SetPlanQueryDTO(self.initial, candidates, 2))

        self.assertEqual([track.track_id for track in plan.tracks], [1, 2])
