import unittest
from dataclasses import dataclass

from app.services.dj_intelligence_service import DJIntelligenceService
from app.services.energy_journey import EnergyJourneyPlanner, SetJourneyPolicyDTO
from app.services.recommendation_scoring import RecommendationScoringEngine
from app.services.recommendation_service import RecommendationService
from app.services.set_planning import SetPlanQueryDTO, SetPlanningEngine, SetPlanningPolicyDTO


@dataclass(frozen=True)
class _Track:
    id: int
    bpm: float
    key: str
    energy: float


class _History:
    def count_history(self, track_id=None, event_type=None): return 0


class EnergyJourneyTests(unittest.TestCase):
    def _planner(self, curve="arc", tolerance=12):
        recommendation = RecommendationService(RecommendationScoringEngine(DJIntelligenceService(), _History()))
        return EnergyJourneyPlanner(SetPlanningEngine(recommendation, SetPlanningPolicyDTO(8, 30)), SetJourneyPolicyDTO(curve, tolerance))

    def test_arc_has_four_ordered_phases_and_deterministic_targets(self):
        initial = _Track(1, 120, "8A", 35)
        candidates = tuple(_Track(index, 120 + index, "8A", energy) for index, energy in enumerate((48, 66, 85, 55), 2))
        journey = self._planner().plan(SetPlanQueryDTO(initial, candidates, 5))

        self.assertEqual([phase.name for phase in journey.phases], ["warm-up", "build", "peak", "cooldown"])
        self.assertEqual([track.track_id for track in journey.set_plan.tracks], [1, 2, 3, 4, 5])
        self.assertFalse(journey.set_plan.is_partial)

    def test_descending_curve_returns_partial_with_explanation_when_target_is_unavailable(self):
        initial = _Track(1, 120, "8A", 92)
        journey = self._planner("descending", 3).plan(SetPlanQueryDTO(initial, (_Track(2, 122, "8A", 30),), 4))

        self.assertTrue(journey.set_plan.is_partial)
        self.assertIn("no hubo candidatas adecuadas", journey.explanation)
        self.assertTrue(journey.deviations)
