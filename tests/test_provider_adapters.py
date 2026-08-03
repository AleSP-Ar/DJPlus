import unittest
from dataclasses import replace
from datetime import datetime, timezone

from app.services.assistant_context import AssistantContextDTO
from app.services.assistant_provider import ProviderConfigDTO, ProviderInvalidResponseError, ProviderRequestDTO
from app.services.provider_adapters import (
    LMStudioProvider,
    OpenAIProvider,
    OllamaProvider,
    ProviderCapabilityError,
    ProviderCapabilityResolver,
    ProviderFactory,
)
from app.services.provider_transport import MockProviderTransport
from app.services.prompt_builder import PromptBuilder
from app.services.tool_dispatcher import ToolRegistry


class ProviderAdapterTests(unittest.TestCase):
    def setUp(self):
        context = AssistantContextDTO(available_data={}, data_sources=("library",))
        runtime_request = type(
            "RuntimeRequest",
            (),
            {
                "user_query": "Count tracks",
                "assistant_context": context,
                "session_id": "session-1",
                "timestamp_utc": datetime.now(timezone.utc),
            },
        )()
        self.prompt = PromptBuilder(ToolRegistry()).build(runtime_request)

    def request(self, **config_values):
        return ProviderRequestDTO("provider-1", self.prompt, ProviderConfigDTO(**config_values))

    def test_factory_selects_each_adapter_and_routes_only_to_mock_transport(self):
        expected = {
            "openai": OpenAIProvider,
            "ollama": OllamaProvider,
            "lmstudio": LMStudioProvider,
        }
        for name, provider_type in expected.items():
            with self.subTest(provider=name):
                transport = MockProviderTransport(text_body=f"{name} response", duration_ms=4)
                provider = ProviderFactory.create(name.upper(), transport)

                response = provider.complete(self.request())

                self.assertIsInstance(provider, provider_type)
                self.assertEqual(response.content, f"{name} response")
                self.assertEqual(response.provider_name, name)
                self.assertEqual(transport.calls[0].url, provider.endpoint)
                self.assertEqual(transport.calls[0].json_body["model"], "mock-model")

    def test_capability_resolver_validates_declared_token_limit(self):
        provider = OpenAIProvider(MockProviderTransport())
        resolver = ProviderCapabilityResolver()

        capabilities = resolver.validate(provider, self.request(max_tokens=16384))

        self.assertEqual(capabilities.provider_name, "openai")
        with self.assertRaises(ProviderCapabilityError):
            resolver.validate(provider, self.request(max_tokens=16385))
        request_with_tool = ProviderRequestDTO(
            "provider-2",
            replace(self.prompt, available_tools=(object(),)),
            ProviderConfigDTO(),
        )
        with self.assertRaises(ProviderCapabilityError):
            resolver.validate(LMStudioProvider(MockProviderTransport()), request_with_tool)

    def test_factory_and_adapter_reject_unknown_invalid_or_unsuccessful_contracts(self):
        with self.assertRaises(ProviderCapabilityError):
            ProviderFactory.create("unknown", MockProviderTransport())
        with self.assertRaises(TypeError):
            OpenAIProvider(object())
        with self.assertRaises(ProviderInvalidResponseError):
            OpenAIProvider(MockProviderTransport(json_body={"unexpected": "shape"})).complete(self.request())

    def test_transport_failures_remain_typed_provider_failures(self):
        provider = OllamaProvider(MockProviderTransport(scenario="timeout"))

        with self.assertRaises(Exception) as error:
            provider.complete(self.request(timeout_ms=10))

        self.assertEqual(getattr(error.exception, "code", None), "timeout")
