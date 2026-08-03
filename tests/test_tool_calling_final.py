import unittest
from dataclasses import dataclass
from datetime import datetime, timezone

from app.services.assistant_context import AssistantContextDTO
from app.services.assistant_facade import AssistantTool, AssistantToolResultDTO
from app.services.assistant_runtime import AssistantRuntime, RuntimeRequestDTO
from app.services.dj_intelligence_service import DJIntelligenceService
from app.services.library_tools import DJCompatibilityTool, MusicAnalysisTool
from app.services.tool_dispatcher import (
    ToolCallDTO,
    ToolDispatcher,
    ToolRegistry,
    ToolSchemaValidationError,
    ToolSchemaValidator,
)


@dataclass(frozen=True)
class AnalysisFeature:
    value: str


@dataclass(frozen=True)
class AnalysisResult:
    feature_type: AnalysisFeature
    value: object
    provider: str = "mock"


class FakeMusicAnalysisService:
    def __init__(self):
        self.calls = []

    def analyze(self, track, features):
        self.calls.append((track, tuple(features)))
        return tuple(AnalysisResult(AnalysisFeature(feature), f"value:{feature}") for feature in features)


class BadSchemaTool(AssistantTool):
    name = "bad_schema"
    description = "invalid"
    input_schema = {"type": "invalid"}

    def execute(self, input_data):
        return AssistantToolResultDTO("never", {})


class ToolCallingFinalTests(unittest.TestCase):
    def setUp(self):
        self.analysis = FakeMusicAnalysisService()
        self.registry = ToolRegistry((
            DJCompatibilityTool(DJIntelligenceService()),
            MusicAnalysisTool(self.analysis),
        ))
        self.dispatcher = ToolDispatcher(self.registry)

    def test_dj_compatibility_tool_uses_dto_tracks_and_returns_immutable_read_only_result(self):
        result = self.dispatcher.dispatch(ToolCallDTO("dj_compatibility", {
            "track_a": {"id": 1, "bpm": 124, "key": "8A", "energy": 70},
            "track_b": {"id": 2, "bpm": 125, "key": "8A", "energy": 75},
        }))

        self.assertTrue(result.success)
        self.assertEqual(result.result.data_used["score"], 100)
        self.assertEqual(result.result.proposed_actions, ())
        with self.assertRaises(TypeError):
            result.result.data_used["score"] = 0

    def test_music_analysis_tool_uses_service_only_and_returns_typed_values(self):
        result = self.dispatcher.dispatch(ToolCallDTO("music_analysis", {
            "track_id": 7,
            "features": ["bpm", "key"],
        }))

        self.assertTrue(result.success)
        self.assertEqual(result.result.data_used["analysis"], (("bpm", "value:bpm"), ("key", "value:key")))
        self.assertEqual(self.analysis.calls[0][0].id, 7)
        self.assertEqual(self.analysis.calls[0][1], ("bpm", "key"))

    def test_schema_validator_rejects_invalid_definitions_and_invalid_calls_before_execution(self):
        with self.assertRaises(ToolSchemaValidationError):
            ToolRegistry((BadSchemaTool(),))
        with self.assertRaises(ToolSchemaValidationError):
            ToolSchemaValidator().validate_call(
                {"type": "object", "required": ["track_id"], "properties": {"track_id": {"type": "integer"}}},
                {"track_id": "not-an-int"},
            )

        invalid = self.dispatcher.dispatch(ToolCallDTO("music_analysis", {"track_id": 7, "features": ["bpm"], "extra": True}))
        self.assertFalse(invalid.success)
        self.assertIn("argumentos no permitidos", invalid.error)
        self.assertEqual(self.analysis.calls, [])

    def test_runtime_dispatches_validated_tool_calls_from_injected_registry(self):
        context = AssistantContextDTO(available_data={}, data_sources=("library",))
        request = RuntimeRequestDTO(
            "Analyze this track",
            context,
            "session-final",
            datetime.now(timezone.utc),
            tool_calls=(ToolCallDTO("music_analysis", {"track_id": 9, "features": ["energy"]}),),
        )

        result = AssistantRuntime(tool_registry=self.registry).process(request)

        self.assertTrue(result.tool_results[0].success)
        self.assertEqual(result.tool_results[0].result.data_used["track_id"], 9)
        self.assertEqual(self.analysis.calls[-1][0].id, 9)
