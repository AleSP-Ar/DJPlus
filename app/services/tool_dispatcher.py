"""Allowlisted assistant-tool registry and typed dispatch boundary."""

from dataclasses import dataclass, field
from types import MappingProxyType

from .assistant_facade import AssistantTool, AssistantToolResultDTO


class ToolRegistryError(ValueError):
    """Raised when the registered assistant-tool contract is invalid."""


class UnknownToolError(ToolRegistryError):
    """Raised when a tool call is outside the registry allowlist."""


@dataclass(frozen=True)
class ToolCallDTO:
    tool_name: str
    arguments: dict = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.tool_name, str) or not self.tool_name.strip():
            raise ToolRegistryError("El nombre de la herramienta es obligatorio.")
        if not isinstance(self.arguments, dict):
            raise ToolRegistryError("Los argumentos de la herramienta deben ser un diccionario.")
        object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))


@dataclass(frozen=True)
class ToolResultDTO:
    tool_name: str
    success: bool
    result: AssistantToolResultDTO | None = None
    error: str | None = None

    def __post_init__(self):
        if not isinstance(self.tool_name, str) or not self.tool_name.strip():
            raise ToolRegistryError("El resultado debe identificar una herramienta.")
        if not isinstance(self.success, bool):
            raise ToolRegistryError("El estado del resultado debe ser booleano.")
        if self.success and (not isinstance(self.result, AssistantToolResultDTO) or self.error is not None):
            raise ToolRegistryError("Un resultado correcto requiere AssistantToolResultDTO sin error.")
        if not self.success and (self.result is not None or not isinstance(self.error, str) or not self.error):
            raise ToolRegistryError("Un resultado fallido requiere un error seguro.")


@dataclass(frozen=True)
class ToolDefinitionDTO:
    """Immutable public metadata for a registered assistant tool."""

    name: str
    description: str
    input_schema: tuple


class ToolRegistry:
    """Own the allowlist and uniqueness rules for AssistantTool instances."""

    def __init__(self, tools=()):
        self._tools = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool):
        if not isinstance(tool, AssistantTool):
            raise ToolRegistryError("ToolRegistry solo acepta AssistantTool.")
        if not isinstance(tool.name, str) or not tool.name.strip():
            raise ToolRegistryError("Cada herramienta debe tener un nombre válido.")
        if tool.name in self._tools:
            raise ToolRegistryError("No se permiten nombres de herramienta duplicados.")
        self._tools[tool.name] = tool

    def resolve(self, tool_name):
        if not isinstance(tool_name, str) or not tool_name.strip():
            raise UnknownToolError("La herramienta solicitada no está registrada.")
        try:
            return self._tools[tool_name]
        except KeyError as error:
            raise UnknownToolError("La herramienta solicitada no está registrada.") from error

    def registered_tool_names(self):
        """Return only names so callers cannot bypass the dispatcher boundary."""
        return tuple(self._tools)

    def tool_definitions(self):
        """Return immutable metadata without exposing tool implementations."""
        return tuple(
            ToolDefinitionDTO(
                name=tool.name,
                description=tool.description,
                input_schema=_freeze_value(tool.input_schema),
            )
            for tool in self._tools.values()
        )


class ToolDispatcher:
    """Resolve allowlisted tools and return typed, non-throwing execution outcomes."""

    def __init__(self, registry):
        if not isinstance(registry, ToolRegistry):
            raise TypeError("ToolDispatcher requiere ToolRegistry.")
        self._registry = registry

    @property
    def registry(self):
        """Expose registry metadata ownership for composed runtime collaborators."""
        return self._registry

    def dispatch(self, call):
        if not isinstance(call, ToolCallDTO):
            raise TypeError("ToolDispatcher.dispatch requiere ToolCallDTO.")
        tool = self._registry.resolve(call.tool_name)
        try:
            result = tool.execute(dict(call.arguments))
            if not isinstance(result, AssistantToolResultDTO):
                raise ToolRegistryError("La herramienta debe devolver AssistantToolResultDTO.")
        except Exception as error:
            return ToolResultDTO(
                tool_name=call.tool_name,
                success=False,
                error=str(error) or error.__class__.__name__,
            )
        return ToolResultDTO(tool_name=call.tool_name, success=True, result=result)


def _freeze_value(value):
    if isinstance(value, dict):
        return tuple((key, _freeze_value(item)) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    return value
