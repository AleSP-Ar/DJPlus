import unittest
from dataclasses import dataclass

from app.services.assistant_facade import AssistantError
from app.services.library_tools import FavoriteTool, HistoryTool, ImportTool
from app.services.tool_dispatcher import ToolCallDTO, ToolDispatcher, ToolRegistry


@dataclass(frozen=True)
class FavoriteTrack:
    id: int


@dataclass(frozen=True)
class ImportJob:
    id: int
    status: str
    total_items: int
    error_count: int


@dataclass(frozen=True)
class ImportDetail:
    job: ImportJob


class FakeFavoriteService:
    def __init__(self):
        self.write_calls = []

    def list_favorites(self):
        return (FavoriteTrack(1), FavoriteTrack(2))

    def is_favorite(self, track_id):
        return track_id == 1

    def mark_favorite(self, track_id):
        self.write_calls.append(("mark", track_id))

    def remove_favorite(self, track_id):
        self.write_calls.append(("remove", track_id))


class FakeHistoryService:
    def __init__(self):
        self.recorded = []

    def list_history(self, track_id=None, event_type=None, limit=None):
        return tuple(range(min(limit, 2)))

    def count_history(self, track_id=None, event_type=None):
        return 7

    def record_track_played(self, track_id):
        self.recorded.append(track_id)


class FakeImportManagerFacade:
    def __init__(self):
        self.recovered = False

    def list_jobs(self, limit=100):
        return (ImportJob(10, "imported", 4, 0), ImportJob(11, "failed", 3, 1))[:limit]

    def get_job_detail(self, job_id):
        return ImportDetail(ImportJob(job_id, "reading_metadata", 5, 1))

    def recover_incomplete_jobs(self):
        self.recovered = True


class Sprint2ToolsTests(unittest.TestCase):
    def setUp(self):
        self.favorites = FakeFavoriteService()
        self.history = FakeHistoryService()
        self.imports = FakeImportManagerFacade()

    def test_new_tools_are_registered_in_the_complete_default_allowlist(self):
        registry = ToolRegistry.default(
            object(), object(), object(), self.favorites, self.history, self.imports
        )

        self.assertEqual(registry.registered_tool_names(), (
            "library_query", "playlist", "collection", "favorite", "history", "import"
        ))

    def test_favorite_tool_reads_and_proposes_without_writing(self):
        tool = FavoriteTool(self.favorites)
        summary = tool.execute({})
        check = tool.execute({"action": "check", "track_id": 1})
        proposal = tool.execute({"action": "propose_mark", "track_id": 3})

        self.assertEqual(summary.data_used, {"favorite_count": 2})
        self.assertTrue(check.data_used["is_favorite"])
        self.assertEqual(proposal.proposed_actions[0].action_type, "mark_favorite")
        self.assertEqual(self.favorites.write_calls, [])

    def test_history_tool_returns_statistics_without_recording_events(self):
        result = HistoryTool(self.history).execute({"track_id": 2, "event_type": "played", "limit": 2})

        self.assertEqual(result.data_used["history_count"], 7)
        self.assertEqual(result.data_used["returned_entries"], 2)
        self.assertEqual(self.history.recorded, [])

    def test_import_tool_reads_detail_and_proposes_recovery_without_recovering(self):
        tool = ImportTool(self.imports)
        detail = tool.execute({"action": "detail", "job_id": 11})
        proposal = tool.execute({"action": "propose_recover"})

        self.assertEqual(detail.data_used["status"], "reading_metadata")
        self.assertEqual(proposal.data_used, {"job_count": 2, "failed_job_count": 1})
        self.assertEqual(proposal.proposed_actions[0].action_type, "recover_import_jobs")
        self.assertFalse(self.imports.recovered)

    def test_new_tool_input_dtos_reject_invalid_write_like_requests(self):
        with self.assertRaises(AssistantError):
            FavoriteTool(self.favorites).execute({"action": "propose_remove"})
        with self.assertRaises(AssistantError):
            HistoryTool(self.history).execute({"limit": 0})
        with self.assertRaises(AssistantError):
            ImportTool(self.imports).execute({"action": "detail"})
