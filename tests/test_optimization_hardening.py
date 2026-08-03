import time
import unittest
from dataclasses import dataclass

from app.services.assistant_facade import AssistantTool, AssistantToolResultDTO
from app.services.dj_intelligence_service import DJIntelligenceService
from app.services.library_tools import LibraryQueryTool, RecommendationTool
from app.services.recommendation_facade import RecommendationFacade, RecommendationFacadeQueryDTO
from app.services.recommendation_scoring import RecommendationScoringEngine
from app.services.recommendation_service import RecommendationService
from app.services.tool_dispatcher import ToolCallDTO, ToolDispatcher, ToolRegistry
from app.services.tool_plan_executor import ToolPlanExecutor
from app.services.tool_planner import PlannedToolCallDTO, ToolPlanDTO


class _Library:
    def __init__(self, rows=()):
        self.rows = tuple(rows)
        self.query_calls = []

    def count_tracks(self):
        return len(self.rows)

    def query(self, text="", **filters):
        self.query_calls.append((text, filters))
        return self.rows, False

    def load_more(self):
        return (), False

    def count_results(self):
        return len(self.rows)


class _History:
    def count_history(self, track_id=None, event_type=None):
        return 0

    def list_history(self, track_id=None, event_type=None, limit=None):
        return ()


class _Tool(AssistantTool):
    name = "read"
    description = "read"
    input_schema = {"type": "object", "properties": {}, "additionalProperties": False}

    def execute(self, input_data):
        return AssistantToolResultDTO("ok", {}, ())


@dataclass(frozen=True)
class _Track:
    id: int
    bpm: float
    key: str
    energy: float


class OptimizationHardeningTests(unittest.TestCase):
    def test_library_query_caches_only_pure_interpretation_and_exposes_metrics(self):
        library = _Library()
        tool = LibraryQueryTool(library)

        tool.execute({"query": "BPM entre 120 y 128"})
        tool.execute({"query": "BPM entre 120 y 128"})

        self.assertEqual(len(tool._interpretation_cache), 1)
        self.assertEqual(tool._last_metrics.operation, "library_query")
        self.assertEqual({stage.stage for stage in tool._last_metrics.stages}, {"interpretation", "service"})
        self.assertGreaterEqual(tool._last_metrics.total_ms, 0)
        self.assertEqual(len(library.query_calls), 2)

    def test_executor_caches_dependency_topology_but_never_tool_results(self):
        executor = ToolPlanExecutor(ToolDispatcher(ToolRegistry((_Tool(),))))
        plan = ToolPlanDTO("read", (PlannedToolCallDTO("step", ToolCallDTO("read")),))

        first = executor.execute(plan)
        second = executor.execute(plan)

        self.assertTrue(first.successful and second.successful)
        self.assertEqual(len(executor._dependency_cache), 1)
        self.assertEqual(executor._last_metrics.operation, "tool_plan_execution")
        self.assertEqual(
            {stage.stage for stage in executor._last_metrics.stages},
            {"dependency_resolution", "dispatch", "total"},
        )

    def test_facade_requeries_when_filters_change_and_profiles_large_simulated_library(self):
        tracks = tuple(_Track(index, 124 + index % 3, "8A", 70) for index in range(1, 1001))
        library = _Library(tracks)
        history = _History()
        facade = RecommendationFacade(
            library,
            history,
            RecommendationService(RecommendationScoringEngine(DJIntelligenceService(), history)),
        )
        current = tracks[0]
        started = time.perf_counter()
        page = facade.recommend(RecommendationFacadeQueryDTO(current, genre="house", limit=20))
        facade.recommend(RecommendationFacadeQueryDTO(current, genre="techno", limit=20))
        tool = RecommendationTool(facade)
        tool.execute({"current_track": current.__dict__, "limit": 5})
        elapsed = time.perf_counter() - started

        self.assertEqual(len(page.recommendations), 20)
        self.assertEqual([call[1].get("genre") for call in library.query_calls[:2]], ["house", "techno"])
        self.assertEqual(facade._last_metrics.operation, "recommendation_facade")
        self.assertEqual(
            {stage.stage for stage in facade._last_metrics.stages},
            {"library", "history", "ranking", "total"},
        )
        self.assertEqual(tool._last_metrics.operation, "recommendation_tool")
        self.assertLess(elapsed, 2.0)
