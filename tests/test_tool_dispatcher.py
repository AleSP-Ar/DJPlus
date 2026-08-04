import unittest
from dataclasses import FrozenInstanceError

from app.services.assistant_facade import AssistantTool, AssistantToolResultDTO
from app.services.tool_dispatcher import (
    ToolCallDTO,
    ToolDispatcher,
    ToolRegistry,
    ToolRegistryError,
    UnknownToolError,
)


class EchoTool(AssistantTool):
    name = "echo"
    description = "Returns its allowed input."
    input_schema = {"type": "object"}

    def execute(self, input_data):
        return AssistantToolResultDTO("ok", {"value": input_data["value"]})


class FailingTool(AssistantTool):
    name = "failing"
    description = "Fails predictably."
    input_schema = {"type": "object"}

    def execute(self, input_data):
        raise ValueError("controlled failure")


class InvalidTool(AssistantTool):
    name = "invalid"
    description = "Violates the result contract."
    input_schema = {"type": "object"}

    def execute(self, input_data):
        return "not a DTO"


class ToolDispatcherTests(unittest.TestCase):
    def test_default_registers_analysis_preview_after_base_tools(self):
        from app.services.analysis_change_planner import AnalysisChangePlanner
        class Library: pass
        class Playlists: pass
        class Collections: pass
        base = ToolRegistry.default(Library(), Playlists(), Collections())
        registry = ToolRegistry.default(Library(), Playlists(), Collections(), analysis_change_planner=AnalysisChangePlanner())
        self.assertEqual(base.registered_tool_names(), ("library_query", "playlist", "collection"))
        self.assertEqual(registry.registered_tool_names(), ("library_query", "playlist", "collection", "analysis_change_preview"))

    def test_default_composes_global_recommendation_without_duplicate_tool(self):
        from types import SimpleNamespace
        from app.services.dj_intelligence_service import DJIntelligenceService
        from app.services.global_ranking_service import RankingTrackDTO

        class Library:
            def query(self, *args, **kwargs): return (), False
            def load_more(self): return (), False
            def count_results(self): return 2
            def iter_ranking_candidates(self, **kwargs):
                yield (RankingTrackDTO(9, 124, "8A", 70), RankingTrackDTO(2, 90, "1A", 10))
        class History:
            def list_history(self, *args, **kwargs): return ()
            def count_history(self, *args, **kwargs): return 0
        registry = ToolRegistry.default(
            Library(), object(), object(),
            history_service=History(), dj_intelligence_service=DJIntelligenceService(),
        )
        self.assertEqual(registry.registered_tool_names().count("recommendation"), 1)
        self.assertIn("recommendation", registry.registered_tool_names())
        tool = registry.resolve("recommendation")
        result = tool.execute({"current_track": {"id": 1, "bpm": 124, "key": "8A", "energy": 70}})
        self.assertEqual(result.data_used["recommendation_page"].recommendations[0].candidate_track_id, 9)
    def setUp(self):
        self.registry = ToolRegistry([EchoTool(), FailingTool(), InvalidTool()])
        self.dispatcher = ToolDispatcher(self.registry)

    def test_registry_registers_unique_assistant_tools_and_resolves_by_name(self):
        self.assertEqual(self.registry.registered_tool_names(), ("echo", "failing", "invalid"))
        self.assertIsInstance(self.registry.resolve("echo"), EchoTool)
        with self.assertRaises(ToolRegistryError):
            self.registry.register(EchoTool())
        with self.assertRaises(ToolRegistryError):
            self.registry.register(object())

    def test_unknown_tool_is_rejected_and_call_dto_is_immutable(self):
        with self.assertRaises(UnknownToolError):
            self.dispatcher.dispatch(ToolCallDTO("missing"))
        call = ToolCallDTO("echo", {"value": "hello"})
        with self.assertRaises(FrozenInstanceError):
            call.tool_name = "other"
        with self.assertRaises(TypeError):
            call.arguments["value"] = "changed"

    def test_dispatcher_executes_registered_tool_and_returns_typed_result(self):
        outcome = self.dispatcher.dispatch(ToolCallDTO("echo", {"value": "hello"}))

        self.assertTrue(outcome.success)
        self.assertEqual(outcome.tool_name, "echo")
        self.assertEqual(outcome.result.data_used, {"value": "hello"})
        self.assertIsNone(outcome.error)

    def test_dispatcher_converts_execution_and_contract_errors_to_safe_typed_results(self):
        failed = self.dispatcher.dispatch(ToolCallDTO("failing"))
        invalid = self.dispatcher.dispatch(ToolCallDTO("invalid"))

        self.assertFalse(failed.success)
        self.assertEqual(failed.error, "controlled failure")
        self.assertFalse(invalid.success)
        self.assertIn("AssistantToolResultDTO", invalid.error)
