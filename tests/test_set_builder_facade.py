import time
import unittest
from dataclasses import dataclass

from app.services.dj_intelligence_service import DJIntelligenceService
from app.services.energy_journey import EnergyJourneyPlanner
from app.services.library_tools import SetBuilderTool
from app.services.recommendation_scoring import RecommendationScoringEngine
from app.services.recommendation_service import RecommendationService
from app.services.set_builder_facade import SetBuilderFacade, SetBuilderQueryDTO
from app.services.global_ranking_service import GlobalRankingService, RankingTrackDTO
from app.services.set_planning import SetPlanningEngine, SetPlanningPolicyDTO
from app.services.tool_dispatcher import ToolCallDTO, ToolDispatcher, ToolRegistry


@dataclass(frozen=True)
class _Track:
    id: int
    bpm: float
    key: str
    energy: float


class _Library:
    def __init__(self, rows): self.rows, self.calls = tuple(rows), []
    def query(self, text="", **filters): self.calls.append(filters); return self.rows, False
    def count_results(self): return len(self.rows)


class _History:
    def __init__(self, excluded=()): self.excluded = excluded
    def count_history(self, track_id=None, event_type=None): return 0
    def list_history(self, event_type=None, limit=None): return tuple({"track_id": item} for item in self.excluded[:limit])


class SetBuilderFacadeTests(unittest.TestCase):
    def setUp(self):
        self.initial = _Track(1, 120, "8A", 35)
        self.rows = (self.initial, _Track(2, 122, "8A", 48), _Track(3, 124, "8A", 66), _Track(4, 126, "8A", 85), _Track(5, 128, "8A", 55))
        self.library, self.history = _Library(self.rows), _History((3,))
        recommendation = RecommendationService(RecommendationScoringEngine(DJIntelligenceService(), self.history))
        facade = SetBuilderFacade(self.library, self.history, EnergyJourneyPlanner(SetPlanningEngine(recommendation, SetPlanningPolicyDTO(8, 30))))
        self.facade = facade

    def test_builds_read_only_partial_result_with_filters_history_and_export(self):
        result = self.facade.build(SetBuilderQueryDTO(self.initial, 5, "arc", genre="house"))

        self.assertEqual(self.library.calls, [{"genre": "house"}])
        self.assertEqual(result.excluded_recent_track_ids, (3,))
        self.assertTrue(result.journey.set_plan.is_partial)
        self.assertIn("Candidatas: 5", result.export_text())
        self.assertIn("desviacion=", result.export_text())

    def test_tool_registry_exposes_set_builder_without_actions(self):
        tool = SetBuilderTool(self.facade)
        result = ToolDispatcher(ToolRegistry((tool,))).dispatch(ToolCallDTO("set_builder", {
            "initial_track": self.initial.__dict__, "target_track_count": 5,
        }))

        self.assertTrue(result.success)
        self.assertEqual(result.result.proposed_actions, ())
        self.assertIn("set_builder_result", result.result.data_used)

    def test_benchmark_builds_100_in_memory_sets_deterministically(self):
        started = time.perf_counter()
        plans = [self.facade.build(SetBuilderQueryDTO(self.initial, 5, "arc")) for _ in range(100)]
        self.assertEqual(len(plans), 100)
        self.assertLess(time.perf_counter() - started, 2.0)

    def test_global_cancellation_returns_typed_non_final_result(self):
        class Token:
            def is_cancelled(self): return True
        class Source(_Library):
            def iter_ranking_candidates(self, **_kwargs):
                yield tuple(RankingTrackDTO(item.id, item.bpm, item.key, item.energy) for item in self.rows)
        source = Source(self.rows)
        recommendation = RecommendationService(RecommendationScoringEngine(DJIntelligenceService(), self.history))
        facade = SetBuilderFacade(
            source, self.history,
            EnergyJourneyPlanner(SetPlanningEngine(recommendation, SetPlanningPolicyDTO(8, 30))),
            GlobalRankingService(source, recommendation),
        )
        result = facade.build(SetBuilderQueryDTO(self.initial, 5, cancellation=Token()))
        self.assertEqual((result.status, result.completed, result.partial), ("CANCELLED", False, False))
        self.assertFalse(hasattr(result, "journey"))

    def test_global_cancellation_after_candidate_evaluation_is_not_a_partial_plan(self):
        class Token:
            def __init__(self): self.calls = 0
            def is_cancelled(self):
                self.calls += 1
                return self.calls >= 4
        class Source(_Library):
            def iter_ranking_candidates(self, **_kwargs):
                yield tuple(RankingTrackDTO(item.id, item.bpm, item.key, item.energy) for item in self.rows)
        recommendation = RecommendationService(RecommendationScoringEngine(DJIntelligenceService(), self.history))
        source = Source(self.rows)
        facade = SetBuilderFacade(source, self.history, EnergyJourneyPlanner(SetPlanningEngine(recommendation, SetPlanningPolicyDTO(8, 30))), GlobalRankingService(source, recommendation))
        result = facade.build(SetBuilderQueryDTO(self.initial, 5, cancellation=Token()))
        self.assertEqual((result.status, result.completed, result.partial), ("CANCELLED", False, False))
