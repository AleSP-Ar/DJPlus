"""Small read-only vertical slice for a locally hosted Ollama assistant."""

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from uuid import uuid4

from .assistant_context import AssistantContextDTO, LibraryContextProvider
from .assistant_provider import ProviderCancellationToken, ProviderConfigDTO
from .assistant_runtime import AssistantRuntime, RuntimeRequestDTO
from .library_tools import LibraryQueryTool, RecommendationTool
from .provider_adapters import OllamaLocalConfigDTO, OllamaProvider
from .provider_registry import ProviderRegistry
from .provider_transport import LocalhostHTTPProviderTransport, ProviderTransport
from .settings_service import DEFAULT_ASSISTANT_MODEL
from .tool_dispatcher import ToolRegistry
from .tool_planner import DeterministicToolPlanner


_LOGGER = logging.getLogger("djplus.assistant")


@dataclass(frozen=True)
class LocalAssistantConfigDTO:
    """User-visible local settings; no credentials or non-local endpoint are allowed."""

    ollama_url: str = "http://localhost:11434"
    model: str = DEFAULT_ASSISTANT_MODEL
    timeout_ms: int = 30000

    def __post_init__(self):
        OllamaLocalConfigDTO(self.ollama_url, self.model)
        if not isinstance(self.timeout_ms, int) or not 1 <= self.timeout_ms <= 120000:
            raise ValueError("El timeout local debe estar entre 1 y 120000 ms.")


class LocalAssistantMVP:
    """Read-only local assistant vertical slice with optional deterministic mode."""

    def __init__(self, library_service, config=None, transport=None, tool_registry=None, recommendation_facade=None, use_provider=True, tool_planner=None):
        self.config = config or LocalAssistantConfigDTO()
        if not isinstance(self.config, LocalAssistantConfigDTO):
            raise TypeError("LocalAssistantMVP requiere LocalAssistantConfigDTO.")
        if transport is not None and not isinstance(transport, ProviderTransport):
            raise TypeError("LocalAssistantMVP requiere ProviderTransport.")
        if tool_registry is not None and not isinstance(tool_registry, ToolRegistry):
            raise TypeError("LocalAssistantMVP requiere ToolRegistry o nulo.")
        if not isinstance(use_provider, bool):
            raise TypeError("use_provider debe ser booleano.")
        if tool_planner is not None and not isinstance(tool_planner, DeterministicToolPlanner):
            raise TypeError("tool_planner debe ser DeterministicToolPlanner o nulo.")
        self._library_service = library_service
        self._tool_planner = tool_planner or DeterministicToolPlanner()
        if tool_registry is None:
            tools = [LibraryQueryTool(library_service)]
            if recommendation_facade is not None:
                tools.append(RecommendationTool(recommendation_facade))
            tool_registry = ToolRegistry(tuple(tools))
        self._tool_registry = tool_registry
        self._use_provider = use_provider
        self._provider_registry = None
        self._transport = transport if transport is not None else (LocalhostHTTPProviderTransport() if self._use_provider else None)
        if self._use_provider:
            provider = OllamaProvider(
                self._transport,
                local_config=OllamaLocalConfigDTO(self.config.ollama_url, self.config.model),
            )
            self._provider_registry = ProviderRegistry((provider,), default_provider_name="ollama")
        self.runtime = AssistantRuntime(provider_registry=self._provider_registry, tool_registry=self._tool_registry)

    def ask(self, user_query, cancellation_token=None):
        if not isinstance(user_query, str) or not user_query.strip():
            raise ValueError("La consulta local es obligatoria.")
        if cancellation_token is not None and not isinstance(cancellation_token, ProviderCancellationToken):
            raise TypeError("cancellation_token debe ser ProviderCancellationToken o nulo.")
        provider_name = "ollama" if self._use_provider else "local"
        _LOGGER.info(
            "Local assistant query started",
            extra={
                "event_name": "assistant_query_started",
                "component": "assistant",
                "context": {"provider": provider_name, "model": self.config.model},
            },
        )
        context = LibraryContextProvider(self._library_service).get_context()
        request = RuntimeRequestDTO(
            user_query=user_query,
            assistant_context=AssistantContextDTO(
                available_data=context.available_data,
                data_sources=context.data_sources,
            ),
            session_id="local-assistant-mvp",
            timestamp_utc=datetime.now(timezone.utc),
            provider_config=ProviderConfigDTO(model=self.config.model, timeout_ms=self.config.timeout_ms),
            request_id=str(uuid4()),
            cancellation_token=cancellation_token,
        )
        if not self._use_provider:
            request = RuntimeRequestDTO(
                user_query=user_query,
                assistant_context=request.assistant_context,
                session_id=request.session_id,
                timestamp_utc=request.timestamp_utc,
                provider_config=request.provider_config,
                request_id=request.request_id,
                cancellation_token=request.cancellation_token,
                tool_plan=self._tool_planner.plan(user_query, self._tool_registry),
            )
        return self.runtime.process(request)
