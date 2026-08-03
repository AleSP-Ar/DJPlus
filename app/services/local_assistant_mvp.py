"""Small read-only vertical slice for a locally hosted Ollama assistant."""

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from uuid import uuid4

from .assistant_context import AssistantContextDTO, LibraryContextProvider
from .assistant_provider import ProviderCancellationToken, ProviderConfigDTO
from .assistant_runtime import AssistantRuntime, RuntimeRequestDTO
from .library_tools import LibraryQueryTool
from .provider_adapters import OllamaLocalConfigDTO, OllamaProvider
from .provider_registry import ProviderRegistry
from .provider_transport import LocalhostHTTPProviderTransport, ProviderTransport
from .tool_dispatcher import ToolRegistry


_LOGGER = logging.getLogger("djplus.assistant")


@dataclass(frozen=True)
class LocalAssistantConfigDTO:
    """User-visible local settings; no credentials or non-local endpoint are allowed."""

    ollama_url: str = "http://localhost:11434"
    model: str = "llama3.2"
    timeout_ms: int = 30000

    def __post_init__(self):
        OllamaLocalConfigDTO(self.ollama_url, self.model)
        if not isinstance(self.timeout_ms, int) or not 1 <= self.timeout_ms <= 120000:
            raise ValueError("El timeout local debe estar entre 1 y 120000 ms.")


class LocalAssistantMVP:
    """Read-only query -> runtime -> Ollama -> LibraryQueryTool vertical slice."""

    def __init__(self, library_service, config=None, transport=None):
        self.config = config or LocalAssistantConfigDTO()
        if not isinstance(self.config, LocalAssistantConfigDTO):
            raise TypeError("LocalAssistantMVP requiere LocalAssistantConfigDTO.")
        if transport is not None and not isinstance(transport, ProviderTransport):
            raise TypeError("LocalAssistantMVP requiere ProviderTransport.")
        self._library_service = library_service
        self._transport = transport or LocalhostHTTPProviderTransport()
        tools = ToolRegistry((LibraryQueryTool(library_service),))
        provider = OllamaProvider(
            self._transport,
            local_config=OllamaLocalConfigDTO(self.config.ollama_url, self.config.model),
        )
        providers = ProviderRegistry((provider,), default_provider_name="ollama")
        self.runtime = AssistantRuntime(provider_registry=providers, tool_registry=tools)

    def ask(self, user_query, cancellation_token=None):
        if not isinstance(user_query, str) or not user_query.strip():
            raise ValueError("La consulta local es obligatoria.")
        if cancellation_token is not None and not isinstance(cancellation_token, ProviderCancellationToken):
            raise TypeError("cancellation_token debe ser ProviderCancellationToken o nulo.")
        _LOGGER.info(
            "Local assistant query started",
            extra={
                "event_name": "assistant_query_started",
                "component": "assistant",
                "context": {"provider": "ollama", "model": self.config.model},
            },
        )
        context = LibraryContextProvider(self._library_service).get_context()
        return self.runtime.process(
            RuntimeRequestDTO(
                user_query=user_query,
                assistant_context=AssistantContextDTO(
                    available_data=context.available_data,
                    data_sources=context.data_sources,
                ),
                session_id="local-ollama-mvp",
                timestamp_utc=datetime.now(timezone.utc),
                provider_config=ProviderConfigDTO(model=self.config.model, timeout_ms=self.config.timeout_ms),
                request_id=str(uuid4()),
                cancellation_token=cancellation_token,
            )
        )
