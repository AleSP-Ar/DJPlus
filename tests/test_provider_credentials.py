import unittest
from dataclasses import fields
from datetime import datetime, timezone

from app.services.assistant_context import AssistantContextDTO
from app.services.assistant_provider import (
    MockAssistantProvider,
    ProviderConfigDTO,
    ProviderPolicy,
    ProviderRequestDTO,
)
from app.services.assistant_runtime import AssistantRuntime, RuntimeRequestDTO
from app.services.provider_credentials import (
    CredentialNotFoundError,
    CredentialProvider,
    InMemoryCredentialProvider,
    ProviderCredentialRefDTO,
    SecretRedactor,
)
from app.services.provider_registry import ProviderRegistry
from app.services.prompt_builder import PromptBuilder
from app.services.tool_dispatcher import ToolRegistry


class ProviderCredentialTests(unittest.TestCase):
    def setUp(self):
        context = AssistantContextDTO(available_data={}, data_sources=("library",))
        self.runtime_request = RuntimeRequestDTO(
            "Count tracks",
            context,
            "session-1",
            datetime.now(timezone.utc),
        )
        self.prompt = PromptBuilder(ToolRegistry()).build(self.runtime_request)
        self.reference = ProviderCredentialRefDTO("mock", "test-key")
        self.secret = "fake-secret-value"
        self.credentials = InMemoryCredentialProvider({self.reference: self.secret})

    def test_credential_contract_resolves_only_references_and_rejects_missing_values(self):
        self.assertEqual(self.credentials.resolve(self.reference), self.secret)
        with self.assertRaises(TypeError):
            CredentialProvider()
        with self.assertRaises(CredentialNotFoundError):
            self.credentials.resolve(ProviderCredentialRefDTO("mock", "missing"))
        with self.assertRaises(ValueError):
            ProviderCredentialRefDTO("mock", "")

    def test_secret_redactor_removes_configured_values_and_common_sensitive_shapes(self):
        redactor = SecretRedactor((self.secret,))

        self.assertEqual(redactor.redact(f"token={self.secret}"), "token=[REDACTED]")
        self.assertEqual(redactor.redact({"api_key": self.secret, "nested": [self.secret]}), {
            "api_key": "[REDACTED]", "nested": ["[REDACTED]"],
        })

    def test_config_and_request_have_no_secret_field_and_only_expose_a_reference(self):
        request = ProviderRequestDTO("request-1", self.prompt, ProviderConfigDTO(), self.reference)
        config_fields = {item.name for item in fields(ProviderConfigDTO)}
        request_fields = {item.name for item in fields(ProviderRequestDTO)}

        self.assertFalse(config_fields & {"api_key", "token", "secret", "password", "credential"})
        self.assertNotIn("credential", request_fields - {"credential_ref"})
        self.assertNotIn(self.secret, repr(request))
        self.assertEqual(request.credential_ref, self.reference)

    def test_mock_resolves_fake_credential_without_exposing_it_in_results_or_errors(self):
        provider = MockAssistantProvider(credential_provider=self.credentials)
        request = ProviderRequestDTO("request-1", self.prompt, credential_ref=self.reference)

        result = ProviderPolicy().execute(provider, request)

        self.assertIsNotNone(result.response)
        self.assertEqual(provider.credential_resolution_count, 1)
        self.assertNotIn(self.secret, repr(provider.calls[0]))
        missing = ProviderPolicy().execute(
            provider,
            ProviderRequestDTO("request-2", self.prompt, credential_ref=ProviderCredentialRefDTO("mock", "missing")),
        )
        self.assertEqual(missing.error.code, "unavailable")
        self.assertNotIn(self.secret, missing.error.message)

    def test_runtime_passes_credential_reference_but_never_secret(self):
        provider = MockAssistantProvider(credential_provider=self.credentials)
        runtime = AssistantRuntime(provider_registry=ProviderRegistry([provider], default_provider_name="mock"))

        result = runtime.process(RuntimeRequestDTO(
            self.runtime_request.user_query,
            self.runtime_request.assistant_context,
            self.runtime_request.session_id,
            self.runtime_request.timestamp_utc,
            credential_ref=self.reference,
        ))

        self.assertIsNotNone(result.assistant_response)
        self.assertEqual(provider.calls[0].credential_ref, self.reference)
        self.assertNotIn(self.secret, repr(result))
