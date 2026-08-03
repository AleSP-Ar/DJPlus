"""Concrete provider adapters backed only by the transport contract."""

from abc import ABC
from collections.abc import Mapping
from dataclasses import dataclass

from .assistant_provider import (
    AssistantProvider,
    AssistantProviderError,
    ProviderCapabilitiesDTO,
    ProviderInvalidResponseError,
    ProviderRateLimitError,
    ProviderRequestDTO,
    ProviderResponseDTO,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from .provider_transport import ProviderTransport, TransportErrorDTO, TransportRequestDTO, TransportResponseDTO, is_localhost_http_url
from .tool_dispatcher import ToolCallDTO


class ProviderCapabilityError(AssistantProviderError):
    """Raised when a request exceeds an adapter's declared capabilities."""


@dataclass(frozen=True)
class OllamaLocalConfigDTO:
    """Explicit local-only Ollama endpoint and model configuration."""

    base_url: str = "http://localhost:11434"
    model: str = "llama3.2"

    def __post_init__(self):
        if not is_localhost_http_url(self.base_url) or self.base_url.rstrip("/").count("/") != 2:
            raise ProviderCapabilityError("Ollama solo admite una URL HTTP de localhost con puerto.")
        if not isinstance(self.model, str) or not self.model.strip():
            raise ProviderCapabilityError("El modelo local de Ollama es obligatorio.")

    @property
    def endpoint(self):
        return f"{self.base_url.rstrip('/')}/api/chat"


class ProviderCapabilityResolver:
    """Validate immutable capability declarations before an adapter sends a request."""

    def resolve(self, provider):
        if not isinstance(provider, AssistantProvider):
            raise TypeError("ProviderCapabilityResolver requiere AssistantProvider.")
        capabilities = provider.capabilities()
        if not isinstance(capabilities, ProviderCapabilitiesDTO):
            raise ProviderCapabilityError("El proveedor debe declarar ProviderCapabilitiesDTO.")
        return capabilities

    def validate(self, provider, request):
        if not isinstance(request, ProviderRequestDTO):
            raise TypeError("ProviderCapabilityResolver.validate requiere ProviderRequestDTO.")
        capabilities = self.resolve(provider)
        if capabilities.max_context_tokens is not None and request.config.max_tokens > capabilities.max_context_tokens:
            raise ProviderCapabilityError("max_tokens excede la capacidad declarada por el proveedor.")
        if request.prompt.available_tools and not capabilities.supports_tool_calls:
            raise ProviderCapabilityError("El proveedor no soporta herramientas registradas.")
        return capabilities


class _TransportAssistantProvider(AssistantProvider, ABC):
    """Shared local adapter behavior; subclasses only declare identity and endpoint."""

    provider_name = ""
    provider_version = "1.0"
    endpoint = ""
    supports_tool_calls = False
    max_context_tokens = 4096

    def __init__(self, transport, capability_resolver=None):
        if not isinstance(transport, ProviderTransport):
            raise TypeError("El adaptador requiere ProviderTransport.")
        if capability_resolver is not None and not isinstance(capability_resolver, ProviderCapabilityResolver):
            raise TypeError("El adaptador requiere ProviderCapabilityResolver.")
        self._transport = transport
        self._capability_resolver = capability_resolver or ProviderCapabilityResolver()

    def capabilities(self):
        return ProviderCapabilitiesDTO(
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            supports_tool_calls=self.supports_tool_calls,
            supports_streaming=False,
            max_context_tokens=self.max_context_tokens,
        )

    def complete(self, request):
        self._capability_resolver.validate(self, request)
        transport_result = self._transport.send(self._transport_request(request))
        if isinstance(transport_result, TransportErrorDTO):
            self._raise_transport_error(transport_result)
        if not isinstance(transport_result, TransportResponseDTO):
            raise ProviderInvalidResponseError("El transporte devolvio un resultado invalido.")
        if not 200 <= transport_result.status_code < 300:
            raise ProviderUnavailableError("El transporte devolvio un status no exitoso.", transport_result.duration_ms)
        content, tool_calls = self._content_and_tool_calls(transport_result)
        return ProviderResponseDTO(
            request_id=request.request_id,
            content=content,
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            tool_calls=tool_calls,
            duration_ms=transport_result.duration_ms,
        )

    def _content_and_tool_calls(self, response):
        return self._content_from(response), ()

    def _transport_request(self, request):
        return TransportRequestDTO(
            request_id=request.request_id,
            method="POST",
            url=self.endpoint,
            timeout_ms=request.config.timeout_ms,
            headers={"X-DJPlus-Provider": self.provider_name},
            json_body={
                "model": request.config.model,
                "temperature": request.config.temperature,
                "max_tokens": request.config.max_tokens,
                "system": request.prompt.system_prompt,
                "prompt": request.prompt.user_prompt,
            },
        )

    def _content_from(self, response):
        if isinstance(response.text_body, str) and response.text_body.strip():
            return response.text_body
        body = response.json_body
        if isinstance(body, Mapping):
            if isinstance(body.get("content"), str) and body["content"].strip():
                return body["content"]
            choices = body.get("choices")
            if isinstance(choices, list) and choices:
                message = choices[0].get("message", {}) if isinstance(choices[0], Mapping) else {}
                if isinstance(message.get("content"), str) and message["content"].strip():
                    return message["content"]
        raise ProviderInvalidResponseError("La respuesta del transporte no contiene texto valido.", response.duration_ms)

    def _raise_transport_error(self, error):
        error_map = {
            "timeout": ProviderTimeoutError,
            "rate_limit": ProviderRateLimitError,
            "unavailable": ProviderUnavailableError,
        }
        error_type = error_map.get(error.code, ProviderUnavailableError)
        raise error_type("El transporte del proveedor no pudo completar la solicitud.", error.duration_ms)


class OpenAIProvider(_TransportAssistantProvider):
    """OpenAI-compatible contract adapter using only an injected transport."""

    provider_name = "openai"
    endpoint = "mock://openai/v1/chat/completions"
    supports_tool_calls = True
    max_context_tokens = 16384


class OllamaProvider(_TransportAssistantProvider):
    """Ollama local adapter; its endpoint is constrained by OllamaLocalConfigDTO."""

    provider_name = "ollama"
    endpoint = "http://localhost:11434/api/chat"
    supports_tool_calls = True
    max_context_tokens = 8192

    def __init__(self, transport, capability_resolver=None, local_config=None):
        super().__init__(transport, capability_resolver)
        if local_config is not None and not isinstance(local_config, OllamaLocalConfigDTO):
            raise TypeError("OllamaProvider requiere OllamaLocalConfigDTO.")
        self.local_config = local_config or OllamaLocalConfigDTO()
        self.endpoint = self.local_config.endpoint

    def _transport_request(self, request):
        return TransportRequestDTO(
            request_id=request.request_id,
            method="POST",
            url=self.endpoint,
            timeout_ms=request.config.timeout_ms,
            json_body={
                "model": request.config.model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": request.prompt.system_prompt},
                    {"role": "user", "content": request.prompt.user_prompt},
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": _thaw(tool.input_schema),
                        },
                    }
                    for tool in request.prompt.available_tools
                ],
                "options": {"temperature": request.config.temperature, "num_predict": request.config.max_tokens},
            },
        )

    def _content_and_tool_calls(self, response):
        body = response.json_body
        if not isinstance(body, Mapping):
            return super()._content_and_tool_calls(response)
        message = body.get("message")
        if not isinstance(message, Mapping):
            return super()._content_and_tool_calls(response)
        content = message.get("content")
        raw_calls = message.get("tool_calls", ())
        tool_calls = []
        if isinstance(raw_calls, list):
            for raw_call in raw_calls:
                function = raw_call.get("function", raw_call) if isinstance(raw_call, Mapping) else None
                if not isinstance(function, Mapping):
                    raise ProviderInvalidResponseError("Ollama devolvio una llamada de herramienta invalida.", response.duration_ms)
                name = function.get("name")
                arguments = function.get("arguments", {})
                if isinstance(arguments, str):
                    try:
                        import json
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError as error:
                        raise ProviderInvalidResponseError("Ollama devolvio argumentos de herramienta invalidos.", response.duration_ms) from error
                try:
                    tool_calls.append(ToolCallDTO(name, arguments))
                except Exception as error:
                    raise ProviderInvalidResponseError("Ollama devolvio una llamada de herramienta invalida.", response.duration_ms) from error
        if not isinstance(content, str) or not content.strip():
            content = "Consulta de herramienta preparada." if tool_calls else None
        if not isinstance(content, str) or not content.strip():
            raise ProviderInvalidResponseError("Ollama no devolvio contenido valido.", response.duration_ms)
        return content, tuple(tool_calls)


class LMStudioProvider(_TransportAssistantProvider):
    """LM Studio-compatible contract adapter using only an injected transport."""

    provider_name = "lmstudio"
    endpoint = "mock://lmstudio/v1/chat/completions"
    supports_tool_calls = False
    max_context_tokens = 8192


class ProviderFactory:
    """Create declared adapters by normalized provider name with an injected transport."""

    _PROVIDERS = {
        "openai": OpenAIProvider,
        "ollama": OllamaProvider,
        "lmstudio": LMStudioProvider,
    }

    @classmethod
    def create(cls, provider_name, transport, capability_resolver=None, ollama_local_config=None):
        if not isinstance(provider_name, str) or not provider_name.strip():
            raise ProviderCapabilityError("El nombre de proveedor es obligatorio.")
        try:
            provider_type = cls._PROVIDERS[provider_name.strip().casefold()]
        except KeyError as error:
            raise ProviderCapabilityError(f"El proveedor '{provider_name}' no esta soportado.") from error
        if provider_type is OllamaProvider:
            return provider_type(transport, capability_resolver, ollama_local_config)
        if ollama_local_config is not None:
            raise ProviderCapabilityError("La configuracion local solo aplica a Ollama.")
        return provider_type(transport, capability_resolver)


def _thaw(value):
    if isinstance(value, tuple):
        return {key: _thaw(item) for key, item in value} if all(
            isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str) for item in value
        ) else [_thaw(item) for item in value]
    return value
