import unittest
from dataclasses import FrozenInstanceError

from app.services.assistant_provider import ProviderCancellationToken
from app.services.provider_transport import (
    MockProviderTransport,
    ProviderTransport,
    ProviderTransportError,
    TransportErrorDTO,
    TransportRequestDTO,
    TransportResponseDTO,
)


class ProviderTransportTests(unittest.TestCase):
    def request(self, **overrides):
        values = {
            "request_id": "transport-1",
            "method": "POST",
            "url": "https://provider.invalid/v1/complete",
            "timeout_ms": 10,
        }
        values.update(overrides)
        return TransportRequestDTO(**values)

    def test_transport_is_abstract_and_request_redacts_headers_and_payload(self):
        request = self.request(
            headers={"Authorization": "Bearer fake-secret", "X-Trace": "trace-1"},
            json_body={"api_key": "fake-secret", "prompt": "hello"},
        )

        with self.assertRaises(TypeError):
            ProviderTransport()
        self.assertEqual(request.headers[0], ("Authorization", "[REDACTED]"))
        self.assertEqual(request.json_body["api_key"], "[REDACTED]")
        self.assertNotIn("fake-secret", repr(request))
        with self.assertRaises(FrozenInstanceError):
            request.method = "GET"

    def test_request_and_response_validate_timeout_status_and_body_contracts(self):
        response = TransportResponseDTO("transport-1", 201, 4, json_body={"token": "hidden"})

        self.assertEqual(response.json_body["token"], "[REDACTED]")
        with self.assertRaises(ProviderTransportError):
            self.request(timeout_ms=0)
        with self.assertRaises(ProviderTransportError):
            TransportResponseDTO("transport-1", 99, 0)
        with self.assertRaises(ProviderTransportError):
            self.request(json_body={}, text_body="also text")
        with self.assertRaises(ProviderTransportError):
            TransportErrorDTO("error", "token=fake-secret", False, status_code=700)

    def test_mock_transport_returns_deterministic_text_or_json_responses(self):
        text_transport = MockProviderTransport(status_code=202, duration_ms=4, response_headers={"X-Trace": "ok"})
        json_transport = MockProviderTransport(json_body={"answer": "42"})

        text = text_transport.send(self.request())
        payload = json_transport.send(self.request(request_id="transport-2"))

        self.assertEqual((text.status_code, text.duration_ms, text.text_body), (202, 4, "Mock transport response."))
        self.assertEqual(payload.json_body, {"answer": "42"})
        self.assertIsNone(payload.text_body)
        self.assertEqual(len(text_transport.calls), 1)

    def test_mock_transport_models_timeout_unavailability_error_and_cancellation(self):
        token = ProviderCancellationToken()
        token.cancel()
        outcomes = {
            "timeout": MockProviderTransport(scenario="timeout").send(self.request()),
            "unavailable": MockProviderTransport(scenario="unavailable").send(self.request()),
            "transport_error": MockProviderTransport(scenario="error", status_code=503).send(self.request()),
            "cancelled": MockProviderTransport().send(self.request(cancellation_token=token)),
        }

        self.assertEqual({name: result.code for name, result in outcomes.items()}, {
            "timeout": "timeout",
            "unavailable": "unavailable",
            "transport_error": "transport_error",
            "cancelled": "cancelled",
        })
        self.assertTrue(outcomes["timeout"].retryable)
        self.assertEqual(outcomes["transport_error"].status_code, 503)
        self.assertTrue(all(isinstance(result, TransportErrorDTO) for result in outcomes.values()))
