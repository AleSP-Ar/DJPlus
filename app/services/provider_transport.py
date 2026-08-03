"""Transport contracts plus a tightly scoped localhost HTTP implementation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Mapping
import json
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .assistant_provider import ProviderCancellationToken
from .provider_credentials import SecretRedactor


class ProviderTransportError(ValueError):
    """Raised when a transport DTO violates its safe local contract."""


def _redacted_headers(headers):
    if headers is None:
        return ()
    items = headers.items() if isinstance(headers, Mapping) else headers
    try:
        normalized = tuple((key, value) for key, value in items)
    except (TypeError, ValueError) as error:
        raise ProviderTransportError("Los headers deben ser pares clave-valor.") from error
    if not all(isinstance(key, str) and key.strip() and isinstance(value, str) for key, value in normalized):
        raise ProviderTransportError("Los headers deben contener textos validos.")
    redactor = SecretRedactor()
    return tuple(
        (key, redactor.redact({key: value})[key])
        for key, value in sorted(normalized, key=lambda item: item[0].casefold())
    )


@dataclass(frozen=True)
class TransportRequestDTO:
    """Redacted local transport request with no connection side effect."""

    request_id: str
    method: str
    url: str
    timeout_ms: int
    headers: tuple[tuple[str, str], ...] | Mapping[str, str] = ()
    json_body: object | None = None
    text_body: str | None = None
    cancellation_token: ProviderCancellationToken | None = None

    def __post_init__(self):
        for field_name in ("request_id", "method", "url"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ProviderTransportError(f"{field_name} es obligatorio.")
        if not isinstance(self.timeout_ms, int) or self.timeout_ms < 1:
            raise ProviderTransportError("timeout_ms debe ser un entero positivo.")
        if self.json_body is not None and self.text_body is not None:
            raise ProviderTransportError("El request admite JSON o texto, no ambos.")
        if self.text_body is not None and not isinstance(self.text_body, str):
            raise ProviderTransportError("text_body debe ser texto o nulo.")
        if self.cancellation_token is not None and not isinstance(self.cancellation_token, ProviderCancellationToken):
            raise ProviderTransportError("cancellation_token debe ser ProviderCancellationToken o nulo.")
        object.__setattr__(self, "headers", _redacted_headers(self.headers))
        object.__setattr__(self, "json_body", SecretRedactor().redact(self.json_body))
        if self.text_body is not None:
            object.__setattr__(self, "text_body", SecretRedactor().redact(self.text_body))


@dataclass(frozen=True)
class TransportResponseDTO:
    """Redacted completed transport response, represented without I/O objects."""

    request_id: str
    status_code: int
    duration_ms: int
    headers: tuple[tuple[str, str], ...] | Mapping[str, str] = ()
    json_body: object | None = None
    text_body: str | None = None

    def __post_init__(self):
        if not isinstance(self.request_id, str) or not self.request_id.strip():
            raise ProviderTransportError("request_id es obligatorio.")
        if not isinstance(self.status_code, int) or not 100 <= self.status_code <= 599:
            raise ProviderTransportError("status_code debe estar entre 100 y 599.")
        if not isinstance(self.duration_ms, int) or self.duration_ms < 0:
            raise ProviderTransportError("duration_ms debe ser un entero no negativo.")
        if self.json_body is not None and self.text_body is not None:
            raise ProviderTransportError("La respuesta admite JSON o texto, no ambos.")
        if self.text_body is not None and not isinstance(self.text_body, str):
            raise ProviderTransportError("text_body debe ser texto o nulo.")
        object.__setattr__(self, "headers", _redacted_headers(self.headers))
        object.__setattr__(self, "json_body", SecretRedactor().redact(self.json_body))
        if self.text_body is not None:
            object.__setattr__(self, "text_body", SecretRedactor().redact(self.text_body))


@dataclass(frozen=True)
class TransportErrorDTO:
    """Typed and redacted transport failure without exception internals."""

    code: str
    message: str
    retryable: bool
    duration_ms: int = 0
    status_code: int | None = None

    def __post_init__(self):
        if not isinstance(self.code, str) or not self.code.strip():
            raise ProviderTransportError("El codigo de transporte es obligatorio.")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ProviderTransportError("El mensaje de transporte es obligatorio.")
        if not isinstance(self.retryable, bool):
            raise ProviderTransportError("retryable debe ser booleano.")
        if not isinstance(self.duration_ms, int) or self.duration_ms < 0:
            raise ProviderTransportError("duration_ms debe ser un entero no negativo.")
        if self.status_code is not None and (not isinstance(self.status_code, int) or not 100 <= self.status_code <= 599):
            raise ProviderTransportError("status_code debe estar entre 100 y 599 o ser nulo.")
        object.__setattr__(self, "message", SecretRedactor().redact(self.message))


class ProviderTransport(ABC):
    """Replaceable transport boundary that returns DTOs and never exposes clients."""

    @abstractmethod
    def send(self, request):
        """Return TransportResponseDTO or TransportErrorDTO for one request."""


class LocalhostHTTPProviderTransport(ProviderTransport):
    """Small stdlib HTTP transport that accepts only http://localhost URLs."""

    def send(self, request):
        if not isinstance(request, TransportRequestDTO):
            raise TypeError("LocalhostHTTPProviderTransport.send requiere TransportRequestDTO.")
        if request.cancellation_token is not None and request.cancellation_token.is_cancelled():
            return TransportErrorDTO("cancelled", "El transporte fue cancelado.", False)
        if not is_localhost_http_url(request.url):
            return TransportErrorDTO("invalid_endpoint", "El transporte solo permite HTTP hacia localhost.", False)
        started = time.monotonic()
        body = None
        headers = dict(request.headers)
        if request.json_body is not None:
            body = json.dumps(request.json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif request.text_body is not None:
            body = request.text_body.encode("utf-8")
            headers["Content-Type"] = "text/plain; charset=utf-8"
        try:
            http_request = Request(request.url, data=body, headers=headers, method=request.method.upper())
            with urlopen(http_request, timeout=request.timeout_ms / 1000) as response:
                return self._response(request.request_id, response.status, response.headers, response.read(), started)
        except HTTPError as error:
            return self._response(request.request_id, error.code, error.headers, error.read(), started)
        except (socket.timeout, TimeoutError):
            return TransportErrorDTO("timeout", "El transporte local supero el timeout configurado.", True, self._duration(started))
        except URLError as error:
            if isinstance(error.reason, socket.timeout):
                return TransportErrorDTO("timeout", "El transporte local supero el timeout configurado.", True, self._duration(started))
            return TransportErrorDTO("unavailable", "Ollama local no esta disponible.", True, self._duration(started))
        except OSError:
            return TransportErrorDTO("unavailable", "Ollama local no esta disponible.", True, self._duration(started))

    def _response(self, request_id, status_code, headers, raw_body, started):
        duration_ms = self._duration(started)
        text = raw_body.decode("utf-8", errors="replace")
        try:
            json_body = json.loads(text) if text.strip() else None
        except json.JSONDecodeError:
            json_body = None
        return TransportResponseDTO(
            request_id=request_id,
            status_code=status_code,
            duration_ms=duration_ms,
            headers=dict(headers.items()),
            json_body=json_body,
            text_body=None if json_body is not None else text,
        )

    @staticmethod
    def _duration(started):
        return int((time.monotonic() - started) * 1000)


def is_localhost_http_url(url):
    """Return whether a URL is an explicit, credential-free localhost HTTP endpoint."""
    if not isinstance(url, str) or not url.strip():
        return False
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme == "http"
            and parsed.hostname == "localhost"
            and parsed.username is None
            and parsed.password is None
            and parsed.port is not None
        )
    except ValueError:
        return False


class MockProviderTransport(ProviderTransport):
    """Deterministic local transport double with no sockets or HTTP libraries."""

    def __init__(
        self,
        scenario="success",
        status_code=200,
        duration_ms=0,
        response_headers=None,
        json_body=None,
        text_body=None,
    ):
        if scenario not in {"success", "timeout", "unavailable", "error"}:
            raise ProviderTransportError("El escenario de transporte no es valido.")
        self.scenario = scenario
        self.status_code = status_code
        self.duration_ms = duration_ms
        self.response_headers = response_headers or {}
        self.json_body = json_body
        self.text_body = text_body
        self.calls = []

    def send(self, request):
        if not isinstance(request, TransportRequestDTO):
            raise TypeError("MockProviderTransport.send requiere TransportRequestDTO.")
        self.calls.append(request)
        if request.cancellation_token is not None and request.cancellation_token.is_cancelled():
            return TransportErrorDTO("cancelled", "El transporte fue cancelado.", False)
        if self.scenario == "timeout" or self.duration_ms > request.timeout_ms:
            return TransportErrorDTO("timeout", "El transporte supero el timeout configurado.", True, request.timeout_ms)
        if self.scenario == "unavailable":
            return TransportErrorDTO("unavailable", "El transporte no esta disponible.", True, self.duration_ms)
        if self.scenario == "error":
            return TransportErrorDTO("transport_error", "Error de transporte simulado.", False, self.duration_ms, self.status_code)
        text_body = self.text_body
        if self.json_body is None and text_body is None:
            text_body = "Mock transport response."
        return TransportResponseDTO(
            request_id=request.request_id,
            status_code=self.status_code,
            duration_ms=self.duration_ms,
            headers=self.response_headers,
            json_body=self.json_body,
            text_body=text_body,
        )
