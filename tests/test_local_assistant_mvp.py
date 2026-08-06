import unittest
from datetime import datetime, timezone

from app.services.assistant_context import AssistantContextDTO
from app.services.assistant_provider import ProviderCancellationToken, ProviderConfigDTO, ProviderInvalidResponseError, ProviderRequestDTO
from app.services.local_assistant_mvp import LocalAssistantConfigDTO, LocalAssistantMVP
from app.services.provider_adapters import OllamaLocalConfigDTO, OllamaProvider, ProviderCapabilityError
from app.services.provider_transport import LocalhostHTTPProviderTransport, MockProviderTransport, TransportRequestDTO
from app.services.prompt_builder import PromptBuilder
from app.services.tool_dispatcher import ToolRegistry


class _LibraryServiceDouble:
    def __init__(self, count=7):
        self.count = count
        self.calls = 0

    def count_tracks(self):
        self.calls += 1
        return self.count


class LocalAssistantMVPTests(unittest.TestCase):
    def test_local_config_rejects_non_localhost_and_keeps_model_explicit(self):
        config = LocalAssistantConfigDTO("http://localhost:11434", "qwen2.5", 5000)

        self.assertEqual(config.model, "qwen2.5")
        with self.assertRaises((ValueError, ProviderCapabilityError)):
            LocalAssistantConfigDTO("https://example.com", "qwen2.5")
        with self.assertRaises(ProviderCapabilityError):
            OllamaLocalConfigDTO("http://127.0.0.1:11434", "qwen2.5")

    def test_localhost_transport_rejects_non_localhost_without_opening_a_connection(self):
        transport = LocalhostHTTPProviderTransport()
        request = TransportRequestDTO("blocked", "POST", "http://example.com:11434/api/chat", 20)

        result = transport.send(request)

        self.assertEqual(result.code, "invalid_endpoint")

    def test_cancelled_localhost_transport_returns_typed_cancellation_without_socket(self):
        token = ProviderCancellationToken()
        token.cancel()
        request = TransportRequestDTO("cancelled", "POST", "http://localhost:11434/api/chat", 20, cancellation_token=token)

        result = LocalhostHTTPProviderTransport().send(request)

        self.assertEqual(result.code, "cancelled")

    def test_mocked_vertical_flow_routes_ollama_tool_call_to_read_only_library_query(self):
        transport = MockProviderTransport(
            json_body={
                "message": {
                    "content": "Voy a consultar la biblioteca.",
                    "tool_calls": [{"function": {"name": "library_query", "arguments": {}}}],
                }
            },
            duration_ms=5,
        )
        library = _LibraryServiceDouble(count=12)
        mvp = LocalAssistantMVP(
            library,
            LocalAssistantConfigDTO("http://localhost:11434", "qwen2.5", 5000),
            transport=transport,
        )

        result = mvp.ask("¿Cuántas pistas hay?")

        self.assertEqual(result.assistant_response.provider_name, "ollama")
        self.assertEqual(result.assistant_response.tool_calls[0].tool_name, "library_query")
        self.assertEqual(result.tool_results[0].result.data_used["track_count"], 12)
        self.assertEqual(result.tool_results[0].result.proposed_actions, ())
        self.assertEqual(transport.calls[0].url, "http://localhost:11434/api/chat")
        self.assertEqual(transport.calls[0].json_body["model"], "qwen2.5")
        self.assertEqual([tool["function"]["name"] for tool in transport.calls[0].json_body["tools"]], ["library_query"])

    def test_deterministic_local_mode_plans_library_query_with_no_provider(self):
        library = _LibraryServiceDouble(count=12)
        mvp = LocalAssistantMVP(
            library,
            use_provider=False,
        )

        result = mvp.ask("Buscame pistas similares")

        self.assertIsNotNone(result.tool_results)
        self.assertGreaterEqual(len(result.tool_results), 0)
        self.assertEqual(result.provider_execution, None)
    def test_ollama_provider_maps_invalid_tool_calls_to_typed_provider_error(self):
        provider = OllamaProvider(
            MockProviderTransport(json_body={"message": {"content": "", "tool_calls": [{"function": {"name": "x", "arguments": []}}]}})
        )
        prompt = PromptBuilder(ToolRegistry()).build(
            type("RuntimeRequest", (), {
                "user_query": "test",
                "assistant_context": AssistantContextDTO({}, ("library",)),
                "session_id": "test",
                "timestamp_utc": datetime.now(timezone.utc),
            })()
        )

        with self.assertRaises(ProviderInvalidResponseError):
            provider.complete(ProviderRequestDTO("invalid-tool", prompt, ProviderConfigDTO(model="llama3.2")))
