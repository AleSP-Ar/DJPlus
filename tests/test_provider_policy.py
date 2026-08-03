import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

from app.services.assistant_context import AssistantContextDTO
from app.services.assistant_provider import (
    AssistantProviderError,
    MockAssistantProvider,
    ProviderCancellationToken,
    ProviderConfigDTO,
    ProviderPolicy,
    ProviderRequestDTO,
    RetryPolicyDTO,
)
from app.services.prompt_builder import PromptBuilder
from app.services.tool_dispatcher import ToolRegistry


class ProviderPolicyTests(unittest.TestCase):
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
        self.policy = ProviderPolicy()

    def request(self, config=None):
        return ProviderRequestDTO("request-1", self.prompt, config or ProviderConfigDTO())

    def test_config_and_retry_dtos_validate_and_are_immutable(self):
        config = ProviderConfigDTO("mock-v2", 0.5, 64, 20, RetryPolicyDTO(2, 3))

        self.assertEqual(config.retry_policy.max_retries, 2)
        with self.assertRaises(FrozenInstanceError):
            config.model = "other"
        with self.assertRaises(AssistantProviderError):
            ProviderConfigDTO("", 0, 1, 1)
        with self.assertRaises(AssistantProviderError):
            ProviderConfigDTO("mock", 2.1, 1, 1)
        with self.assertRaises(AssistantProviderError):
            ProviderConfigDTO("mock", 0, 0, 1)
        with self.assertRaises(AssistantProviderError):
            ProviderConfigDTO("mock", 0, 1, 0)
        with self.assertRaises(AssistantProviderError):
            RetryPolicyDTO(6, 0)
        with self.assertRaises(AssistantProviderError):
            RetryPolicyDTO(0, -1)

    def test_success_returns_deterministic_usage_duration_and_validated_config(self):
        provider = MockAssistantProvider(default_response="There are 42 tracks.", response_duration_ms=7)
        request = self.request(ProviderConfigDTO("mock-v2", 0.2, 32, 10))

        result = self.policy.execute(provider, request)

        self.assertEqual(result.response.content, "There are 42 tracks.")
        self.assertIsNone(result.error)
        self.assertEqual(result.attempts, 1)
        self.assertEqual(result.duration_ms, 7)
        self.assertEqual(result.usage.total_tokens, result.usage.prompt_tokens + result.usage.completion_tokens)
        self.assertEqual(provider.calls[0].config, request.config)

    def test_mock_failure_scenarios_return_typed_errors_without_network(self):
        expected = {
            "timeout": "timeout",
            "rate_limit": "rate_limit",
            "unavailable": "unavailable",
            "invalid_response": "invalid_response",
        }
        for scenario, code in expected.items():
            with self.subTest(scenario=scenario):
                result = self.policy.execute(MockAssistantProvider(scenario=scenario), self.request())
                self.assertIsNone(result.response)
                self.assertEqual(result.error.code, code)
                self.assertEqual(result.attempts, 1)
                self.assertEqual(result.usage.total_tokens, 0)

    def test_retryable_failure_can_succeed_with_deterministic_retry_delay(self):
        provider = MockAssistantProvider(
            default_response="Recovered",
            scenario="retry_success",
            response_duration_ms=7,
        )
        request = self.request(ProviderConfigDTO(timeout_ms=10, retry_policy=RetryPolicyDTO(1, 3)))

        result = self.policy.execute(provider, request)

        self.assertEqual(result.response.content, "Recovered")
        self.assertEqual(result.attempts, 2)
        self.assertEqual(result.duration_ms, 10)
        self.assertEqual(len(provider.calls), 2)

    def test_timeout_and_cancellation_are_cooperative_and_bounded(self):
        timeout = self.policy.execute(
            MockAssistantProvider(response_duration_ms=11),
            self.request(ProviderConfigDTO(timeout_ms=10, retry_policy=RetryPolicyDTO(1, 2))),
        )
        token = ProviderCancellationToken()
        token.cancel()
        provider = MockAssistantProvider()
        cancelled = self.policy.execute(provider, self.request(), token)

        self.assertEqual(timeout.error.code, "timeout")
        self.assertEqual(timeout.attempts, 2)
        self.assertEqual(timeout.duration_ms, 24)
        self.assertEqual(cancelled.error.code, "cancelled")
        self.assertEqual(cancelled.attempts, 0)
        self.assertEqual(provider.calls, [])
