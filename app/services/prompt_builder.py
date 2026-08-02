"""Deterministic provider-neutral prompt construction for the assistant runtime."""

from dataclasses import dataclass
from datetime import datetime, timezone

from .assistant_context import AssistantContextDTO
from .tool_dispatcher import ToolDefinitionDTO, ToolRegistry


class PromptBuilderError(ValueError):
    """Raised when prompt construction receives an invalid bounded request."""


@dataclass(frozen=True)
class ContextBlockDTO:
    data_sources: tuple[str, ...]
    timestamp: datetime
    context_version: str
    available_data: tuple


@dataclass(frozen=True)
class PromptMetadataDTO:
    runtime_version: str
    generated_at_utc: datetime
    prompt_version: str


@dataclass(frozen=True)
class PromptDTO:
    system_prompt: str
    context_block: ContextBlockDTO
    user_prompt: str
    available_tools: tuple[ToolDefinitionDTO, ...]
    metadata: PromptMetadataDTO


class PromptBuilder:
    """Build only deterministic prompt data from runtime DTOs and registry metadata."""

    ASSISTANT_IDENTITY = "DJPlus Assistant"
    PROMPT_VERSION = "1.0"

    def __init__(self, tool_registry, runtime_version="1.0", prompt_version=PROMPT_VERSION):
        if not isinstance(tool_registry, ToolRegistry):
            raise TypeError("PromptBuilder requiere ToolRegistry.")
        if not isinstance(runtime_version, str) or not runtime_version.strip():
            raise PromptBuilderError("La versión del runtime es obligatoria.")
        if not isinstance(prompt_version, str) or not prompt_version.strip():
            raise PromptBuilderError("La versión del prompt es obligatoria.")
        self._tool_registry = tool_registry
        self._runtime_version = runtime_version
        self._prompt_version = prompt_version

    def build(self, request):
        """Create a provider-neutral PromptDTO without invoking models or tools."""
        self._validate_request(request)
        context = request.assistant_context
        return PromptDTO(
            system_prompt=self._build_system_prompt(),
            context_block=ContextBlockDTO(
                data_sources=tuple(context.data_sources),
                timestamp=context.timestamp,
                context_version=context.context_version,
                available_data=_freeze_value(context.available_data),
            ),
            user_prompt=request.user_query,
            available_tools=self._tool_registry.tool_definitions(),
            metadata=PromptMetadataDTO(
                runtime_version=self._runtime_version,
                generated_at_utc=datetime.now(timezone.utc),
                prompt_version=self._prompt_version,
            ),
        )

    def _build_system_prompt(self):
        return (
            f"Identity: {self.ASSISTANT_IDENTITY}\n"
            "Restrictions: operate only through approved runtime boundaries.\n"
            "Safety limits: do not access persistence, filesystem, or unregistered tools.\n"
            f"Runtime version: {self._runtime_version}"
        )

    def _validate_request(self, request):
        required_fields = ("user_query", "assistant_context", "session_id", "timestamp_utc")
        if not all(hasattr(request, field_name) for field_name in required_fields):
            raise TypeError("PromptBuilder.build requiere RuntimeRequestDTO.")
        if not isinstance(request.assistant_context, AssistantContextDTO):
            raise PromptBuilderError("PromptBuilder requiere AssistantContextDTO.")


def _freeze_value(value):
    if isinstance(value, dict):
        return tuple((key, _freeze_value(item)) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    return value
