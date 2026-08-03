import inspect
import unittest
from dataclasses import dataclass

from app.services.dj_intelligence_service import DJIntelligenceService
from app.services.library_tools import RecommendationTool
from app.services.recommendation_facade import RecommendationFacade, RecommendationFacadeQueryDTO
from app.services.recommendation_scoring import RecommendationScoringEngine
from app.services.recommendation_service import RecommendationService
from app.services.tool_dispatcher import ToolCallDTO, ToolDispatcher, ToolRegistry


@dataclass(frozen=True)
class Track:
    id: int
    bpm: float
    key: str
    energy: float


@dataclass(frozen=True)
class HistoryEvent:
    track_id: int


class LibraryServiceDouble:
    def __init__(self, first, second):
        self.first, self.second = first, second
        self.calls = []

    def query(self, text="", **filters):
        self.calls.append(("query", text, filters))
        return self.first, True

    def load_more(self):
        self.calls.append(("load_more",))
        return self.second, False

    def count_results(self):
        return 4


class HistoryServiceDouble:
    def __init__(self):
        self.list_calls = []

    def count_history(self, track_id=None, event_type=None):
        return {3: 5, 4: 1}.get(track_id, 0)

    def list_history(self, track_id=None, event_type=None, limit=None):
        self.list_calls.append((event_type, limit))
        return (HistoryEvent(2),)


class RecommendationFacadeTests(unittest.TestCase):
    def setUp(self):
        self.current = Track(1, 124, "8A", 70)
        self.library = LibraryServiceDouble((self.current, Track(2, 125, "8A", 75), Track(3, 126, "8A", 72)), (Track(4, 123, "8A", 68),))
        self.history = HistoryServiceDouble()
        scorer = RecommendationScoringEngine(DJIntelligenceService(), self.history)
        self.facade = RecommendationFacade(self.library, self.history, RecommendationService(scorer))

    def test_searches_through_library_filters_excludes_recent_and_returns_explainable_page(self):
        page = self.facade.recommend(RecommendationFacadeQueryDTO(self.current, bpm_min=120, key="8A", genre="house", favorite=True))

        self.assertEqual([item.candidate_track_id for item in page.recommendations], [3])
        self.assertEqual(page.excluded_recent_track_ids, (2,))
        self.assertTrue(page.has_more)
        self.assertEqual(page.page_number, 1)
        self.assertEqual(self.library.calls[0], ("query", "", {"bpm_min": 120, "key": "8A", "genre": "house", "favorite": True}))
        self.assertIn("excluidas por historial: 1", page.explanation)

    def test_load_more_uses_library_service_and_returns_next_page(self):
        self.facade.recommend(RecommendationFacadeQueryDTO(self.current))
        page = self.facade.recommend(RecommendationFacadeQueryDTO(self.current, load_more=True))

        self.assertEqual(self.library.calls[-1], ("load_more",))
        self.assertEqual([item.candidate_track_id for item in page.recommendations], [4])
        self.assertEqual((page.page_number, page.has_more), (2, False))

    def test_recommendation_tool_is_allowlisted_read_only_in_tool_registry(self):
        dispatcher = ToolDispatcher(ToolRegistry((RecommendationTool(self.facade),)))
        result = dispatcher.dispatch(ToolCallDTO("recommendation", {
            "current_track": {"id": 1, "bpm": 124, "key": "8A", "energy": 70}, "limit": 5,
        }))

        self.assertTrue(result.success)
        self.assertEqual(result.result.proposed_actions, ())
        self.assertIn("recommendation_page", result.result.data_used)

    def test_facade_has_no_repository_persistence_or_playlist_access(self):
        source = inspect.getsource(__import__("app.services.recommendation_facade", fromlist=["*"])).casefold()
        for forbidden in ("app.repository", "sqlite3", "playlist", "persist"):
            self.assertNotIn(forbidden, source)
