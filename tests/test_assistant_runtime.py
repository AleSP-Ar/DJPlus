import inspect
import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

from app.services.assistant_context import AssistantContextDTO
from app.services.action_pipeline import ActionPipeline, ActionType
from app.services.assistant_facade import AssistantActionProposalDTO, AssistantTool, AssistantToolResultDTO
from app.services.conversation_session import ConversationSession, MessageRole
from app.services.confirmation_manager import ConfirmationManager, ConfirmationRequestDTO
from app.services.prompt_builder import PromptBuilder
from app.services.assistant_runtime import (
    AssistantRuntime,
    AssistantRuntimeError,
    RuntimeRequestDTO,
    RuntimeResultDTO,
)
from app.services.assistant_provider import MockAssistantProvider, ProviderResponseDTO
from app.services.assistant_provider import ProviderConfigDTO, ProviderCancellationToken, RetryPolicyDTO
from app.services.provider_registry import ProviderNotFoundError, ProviderRegistry
from app.services.tool_dispatcher import ToolCallDTO, ToolDispatcher, ToolRegistry, UnknownToolError


class RecordingDispatcher(ToolDispatcher):
    def __init__(self):
        super().__init__(ToolRegistry())
        self.calls = []

    def dispatch(self, call):
        self.calls.append(call)
        return super().dispatch(call)


class RecordingPromptBuilder(PromptBuilder):
    def __init__(self):
        super().__init__(ToolRegistry())
        self.requests = []

    def build(self, request):
        self.requests.append(request)
        return super().build(request)


class ProposalTool(AssistantTool):
    name = "proposal"
    description = "Returns a proposed action without executing it."
    input_schema = {"type": "object"}

    def execute(self, input_data):
        return AssistantToolResultDTO(
            "proposal",
            {},
            proposed_actions=(
                AssistantActionProposalDTO(
                    action_type=ActionType.CREATE_PLAYLIST.value,
                    label="Crear playlist Sunset",
                    payload={"name": "Sunset"},
                ),
            ),
        )


class AssistantRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.context = AssistantContextDTO(
            available_data={"library": {"track_count": 42}},
            data_sources=("library",),
        )
        self.request = RuntimeRequestDTO(
            user_query="¿Cuántas pistas hay?",
            assistant_context=self.context,
            session_id="session-1",
            timestamp_utc=datetime.now(timezone.utc),
        )

    def test_runtime_accepts_request_and_returns_empty_side_effect_free_result(self):
        result = AssistantRuntime().process(self.request)

        self.assertIsInstance(result, RuntimeResultDTO)
        self.assertEqual(result.generated_prompt.user_prompt, "¿Cuántas pistas hay?")
        self.assertEqual(result.tool_calls, ())
        self.assertEqual(result.tool_results, ())
        self.assertIsNone(result.assistant_response)
        self.assertEqual(result.proposed_actions, ())

    def test_dtos_are_immutable_and_request_requires_utc_context(self):
        with self.assertRaises(FrozenInstanceError):
            self.request.session_id = "another-session"
        with self.assertRaises(FrozenInstanceError):
            RuntimeResultDTO(None).tool_calls = ("tool",)
        with self.assertRaises(AssistantRuntimeError):
            RuntimeRequestDTO(
                "query", self.context, "session-1", datetime.now()
            )

    def test_runtime_rejects_invalid_request_and_never_mutates_context(self):
        original_data = {"library": {"track_count": 42}}

        with self.assertRaises(TypeError):
            AssistantRuntime().process(object())
        AssistantRuntime().process(self.request)

        self.assertEqual(self.context.available_data, original_data)

    def test_runtime_has_no_infrastructure_imports_or_tool_execution(self):
        source = inspect.getsource(__import__("app.services.assistant_runtime", fromlist=["*"]))

        self.assertNotIn("app.repository", source)
        self.assertNotIn("sqlalchemy", source.lower())
        self.assertNotIn("sqlite3", source.lower())
        self.assertNotIn(".complete(", source)
        self.assertNotIn("AssistantTool", source)

    def test_runtime_uses_only_the_injected_dispatcher_for_tool_calls(self):
        dispatcher = RecordingDispatcher()
        call = ToolCallDTO("unknown")
        request = RuntimeRequestDTO(
            self.request.user_query,
            self.context,
            self.request.session_id,
            self.request.timestamp_utc,
            tool_calls=(call,),
        )

        with self.assertRaises(UnknownToolError):
            AssistantRuntime(dispatcher).process(request)

        self.assertEqual(dispatcher.calls, [call])

    def test_runtime_uses_the_injected_prompt_builder(self):
        builder = RecordingPromptBuilder()

        result = AssistantRuntime(prompt_builder=builder).process(self.request)

        self.assertEqual(builder.requests, [self.request])
        self.assertEqual(result.generated_prompt.metadata.runtime_version, "1.0")

    def test_runtime_records_user_message_in_matching_conversation_session(self):
        session = ConversationSession("session-1")

        AssistantRuntime(conversation_session=session).process(self.request)

        self.assertEqual(session.message_count(), 1)
        self.assertEqual(session.history()[0].role, MessageRole.USER)
        self.assertEqual(session.history()[0].content, self.request.user_query)

    def test_runtime_stores_tool_proposals_in_action_pipeline_without_executing_them(self):
        pipeline = ActionPipeline()
        dispatcher = ToolDispatcher(ToolRegistry([ProposalTool()]))
        request = RuntimeRequestDTO(
            self.request.user_query,
            self.context,
            self.request.session_id,
            self.request.timestamp_utc,
            tool_calls=(ToolCallDTO("proposal"),),
        )

        result = AssistantRuntime(dispatcher=dispatcher, action_pipeline=pipeline).process(request)

        self.assertEqual(len(result.proposed_actions), 1)
        self.assertEqual(pipeline.list_proposals(), result.proposed_actions)
        self.assertTrue(result.proposed_actions[0].requires_confirmation)
        self.assertEqual(result.proposed_actions[0].action_type, ActionType.CREATE_PLAYLIST)

    def test_runtime_uses_confirmation_manager_without_executing_proposal(self):
        pipeline = ActionPipeline()
        proposal = pipeline.create_proposal(ActionType.CUSTOM, "Confirm", "Test", {})
        manager = ConfirmationManager(pipeline)
        request = RuntimeRequestDTO(
            self.request.user_query,
            self.context,
            self.request.session_id,
            self.request.timestamp_utc,
            confirmation_request=ConfirmationRequestDTO(proposal.action_id, self.request.timestamp_utc),
        )

        result = AssistantRuntime(
            action_pipeline=pipeline,
            confirmation_manager=manager,
        ).process(request)

        self.assertTrue(result.confirmation_result.confirmed)
        self.assertEqual(pipeline.get_proposal(proposal.action_id), proposal)

    def test_runtime_uses_explicit_registered_provider_and_maps_its_response(self):
        provider = MockAssistantProvider({self.request.user_query: "There are 42 tracks."})
        registry = ProviderRegistry([provider])
        request = RuntimeRequestDTO(
            self.request.user_query,
            self.context,
            self.request.session_id,
            self.request.timestamp_utc,
            provider_name="mock",
            request_id="provider-request-1",
        )

        result = AssistantRuntime(provider_registry=registry).process(request)

        self.assertIsInstance(result.assistant_response, ProviderResponseDTO)
        self.assertEqual(result.assistant_response.content, "There are 42 tracks.")
        self.assertEqual(provider.calls[0].request_id, "provider-request-1")
        self.assertEqual(provider.calls[0].prompt, result.generated_prompt)

    def test_runtime_uses_default_provider_and_rejects_missing_provider_selection(self):
        provider = MockAssistantProvider(default_response="Default response")
        runtime = AssistantRuntime(provider_registry=ProviderRegistry([provider], default_provider_name="mock"))

        self.assertEqual(runtime.process(self.request).assistant_response.content, "Default response")
        missing = RuntimeRequestDTO(
            self.request.user_query,
            self.context,
            self.request.session_id,
            self.request.timestamp_utc,
            provider_name="missing",
        )
        with self.assertRaises(ProviderNotFoundError):
            runtime.process(missing)

    def test_runtime_validates_provider_injection_and_generated_provider_request_identifier(self):
        with self.assertRaises(TypeError):
            AssistantRuntime(provider_registry=object())
        provider = MockAssistantProvider()
        runtime = AssistantRuntime(provider_registry=ProviderRegistry([provider], default_provider_name="mock"))

        result = runtime.process(self.request)

        self.assertEqual(
            result.assistant_response.request_id,
            f"{self.request.session_id}:{self.request.timestamp_utc.isoformat()}",
        )

    def test_runtime_passes_validated_config_and_maps_provider_execution_errors(self):
        config = ProviderConfigDTO("mock-v2", 0.4, 64, 10, RetryPolicyDTO(1, 2))
        provider = MockAssistantProvider(default_response="Recovered", scenario="retry_success")
        runtime = AssistantRuntime(provider_registry=ProviderRegistry([provider], default_provider_name="mock"))
        configured = RuntimeRequestDTO(
            self.request.user_query,
            self.context,
            self.request.session_id,
            self.request.timestamp_utc,
            provider_config=config,
        )
        failed_provider = MockAssistantProvider(scenario="invalid_response")
        failed_runtime = AssistantRuntime(
            provider_registry=ProviderRegistry([failed_provider], default_provider_name="mock")
        )

        result = runtime.process(configured)
        failed = failed_runtime.process(self.request)

        self.assertEqual(provider.calls[0].config, config)
        self.assertEqual(result.provider_execution.attempts, 2)
        self.assertEqual(result.assistant_response.content, "Recovered")
        self.assertIsNone(failed.assistant_response)
        self.assertEqual(failed.provider_execution.error.code, "invalid_response")
