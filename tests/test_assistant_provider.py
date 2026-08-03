import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

from app.services.assistant_context import AssistantContextDTO
from app.services.assistant_provider import (
    AssistantProvider,
    AssistantProviderError,
    MockAssistantProvider,
    ProviderCapabilitiesDTO,
    ProviderRequestDTO,
    ProviderResponseDTO,
)
from app.services.prompt_builder import PromptBuilder
from app.services.tool_dispatcher import ToolRegistry


class AssistantProviderTests(unittest.TestCase):
    def setUp(self):
        context = AssistantContextDTO(available_data={}, data_sources=("library",))
        runtime_request = type(
            "RuntimeRequest",
            (),
            {
                "user_query": "Suggest a warmup track",
                "assistant_context": context,
                "session_id": "session-1",
                "timestamp_utc": datetime.now(timezone.utc),
            },
        )()
        self.prompt = PromptBuilder(ToolRegistry()).build(runtime_request)
        self.request = ProviderRequestDTO("request-1", self.prompt)

    def test_provider_is_abstract(self):
        with self.assertRaises(TypeError):
            AssistantProvider()

    def test_contract_dtos_are_immutable_and_validate_their_inputs(self):
        capabilities = ProviderCapabilitiesDTO("test", "0.1", max_context_tokens=128)
        response = ProviderResponseDTO("request-1", "Done", "test", "0.1")

        self.assertEqual(capabilities.max_context_tokens, 128)
        self.assertEqual(response.tool_calls, ())
        with self.assertRaises(FrozenInstanceError):
            self.request.request_id = "other"
        with self.assertRaises(AssistantProviderError):
            ProviderRequestDTO("", self.prompt)
        with self.assertRaises(AssistantProviderError):
            ProviderCapabilitiesDTO("test", "0.1", max_context_tokens=0)
        with self.assertRaises(AssistantProviderError):
            ProviderResponseDTO("request-1", "", "test", "0.1")

    def test_mock_provider_returns_configured_response_deterministically(self):
        provider = MockAssistantProvider({"Suggest a warmup track": "Try a 118 BPM house track."})

        first = provider.complete(self.request)
        second = provider.complete(self.request)

        self.assertEqual(first, second)
        self.assertEqual(first.content, "Try a 118 BPM house track.")
        self.assertEqual(first.provider_name, "mock")
        self.assertEqual(provider.calls, [self.request, self.request])

    def test_mock_provider_exposes_local_capabilities_and_rejects_invalid_requests(self):
        provider = MockAssistantProvider(default_response="Fallback")

        self.assertEqual(provider.capabilities(), ProviderCapabilitiesDTO("mock", "1.0"))
        self.assertEqual(provider.complete(self.request).content, "Fallback")
        with self.assertRaises(TypeError):
            provider.complete(object())
