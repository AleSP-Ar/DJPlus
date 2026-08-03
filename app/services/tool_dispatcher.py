"""Allowlisted assistant-tool registry and typed dispatch boundary."""

from dataclasses import dataclass, field
from types import MappingProxyType

from .assistant_facade import AssistantTool, AssistantToolResultDTO


class ToolRegistryError(ValueError):
    """Raised when the registered assistant-tool contract is invalid."""


class UnknownToolError(ToolRegistryError):
    """Raised when a tool call is outside the registry allowlist."""


class ToolSchemaValidationError(ToolRegistryError):
    """Raised when a tool definition or call violates its bounded schema."""


class ToolSchemaValidator:
    """Small deterministic validator for the JSON-like schemas used by tools."""

    _KNOWN_TYPES = {"object", "string", "integer", "number", "boolean", "array", "track"}

    def validate_schema(self, schema):
        if not isinstance(schema, dict) or schema.get("type") != "object":
            raise ToolSchemaValidationError("El schema de herramienta debe describir un objeto.")
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            raise ToolSchemaValidationError("Las propiedades del schema deben ser un diccionario.")
        required = schema.get("required", ())
        if not isinstance(required, (list, tuple)) or not all(isinstance(name, str) for name in required):
            raise ToolSchemaValidationError("Los campos requeridos del schema no son validos.")
        if not set(required).issubset(properties):
            raise ToolSchemaValidationError("Los campos requeridos deben estar declarados en properties.")
        for definition in properties.values():
            if not isinstance(definition, dict):
                raise ToolSchemaValidationError("Cada propiedad del schema debe ser un diccionario.")
            value_type = definition.get("type")
            if value_type is not None and value_type not in self._KNOWN_TYPES:
                raise ToolSchemaValidationError("El tipo de propiedad del schema no esta soportado.")

    def validate_call(self, schema, arguments):
        self.validate_schema(schema)
        if not isinstance(arguments, dict):
            raise ToolSchemaValidationError("Los argumentos de herramienta deben ser un objeto.")
        properties = schema.get("properties", {})
        required = tuple(schema.get("required", ()))
        if schema.get("additionalProperties", True) is False and set(arguments) - set(properties):
            raise ToolSchemaValidationError("La llamada contiene argumentos no permitidos.")
        missing = [name for name in required if name not in arguments]
        if missing:
            raise ToolSchemaValidationError("Faltan argumentos requeridos en la llamada.")
        for name, value in arguments.items():
            if name in properties:
                self._validate_value(value, properties[name])

    def _validate_value(self, value, definition):
        if "enum" in definition and value not in definition["enum"]:
            raise ToolSchemaValidationError("El argumento no pertenece al enum permitido.")
        value_type = definition.get("type")
        valid = {
            "object": isinstance(value, dict),
            "string": isinstance(value, str),
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "number": isinstance(value, (int, float)) and not isinstance(value, bool),
            "boolean": isinstance(value, bool),
            "array": isinstance(value, (list, tuple)),
            "track": value is not None,
        }
        if value_type is not None and not valid[value_type]:
            raise ToolSchemaValidationError("El tipo de argumento no coincide con el schema.")
        if value_type == "array" and "items" in definition:
            for item in value:
                self._validate_value(item, definition["items"])


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
        self._schema_validator = ToolSchemaValidator()
        for tool in tools:
            self.register(tool)

    @classmethod
    def default(
        cls,
        library_service,
        playlist_service,
        collection_service,
        favorite_service=None,
        history_service=None,
        import_manager_facade=None,
        dj_intelligence_service=None,
        music_analysis_service=None,
        recommendation_facade=None,
        diagnostics_service=None,
        set_builder_facade=None,
        music_analysis_facade=None,
        analysis_change_planner=None,
    ):
        """Build the standard library-tool allowlist from existing services only."""
        from .library_tools import (
            CollectionTool,
            FavoriteTool,
            HistoryTool,
            ImportTool,
            DJCompatibilityTool,
            LibraryQueryTool,
            MusicAnalysisTool,
            PlaylistTool,
            RecommendationTool,
            DiagnosticsTool,
            SetBuilderTool,
            MusicAnalysisBatchTool,
        )
        if analysis_change_planner is not None:
            from .analysis_change_tool import AnalysisChangePreviewTool
            tools.append(AnalysisChangePreviewTool(analysis_change_planner))

        tools = [
            LibraryQueryTool(library_service),
            PlaylistTool(playlist_service),
            CollectionTool(collection_service),
        ]
        optional_tools = (
            (favorite_service, FavoriteTool),
            (history_service, HistoryTool),
            (import_manager_facade, ImportTool),
        )
        if any(service is not None for service, _ in optional_tools) and not all(
            service is not None for service, _ in optional_tools
        ):
            raise ToolRegistryError("El registro estandar requiere los tres servicios opcionales juntos.")
        tools.extend(tool_type(service) for service, tool_type in optional_tools if service is not None)
        analysis_tools = (
            (dj_intelligence_service, DJCompatibilityTool),
            (music_analysis_service, MusicAnalysisTool),
        )
        if any(service is not None for service, _ in analysis_tools) and not all(
            service is not None for service, _ in analysis_tools
        ):
            raise ToolRegistryError("El registro estandar requiere ambos servicios de analisis juntos.")
        tools.extend(tool_type(service) for service, tool_type in analysis_tools if service is not None)
        if recommendation_facade is not None:
            tools.append(RecommendationTool(recommendation_facade))
        if diagnostics_service is not None:
            tools.append(DiagnosticsTool(diagnostics_service))
        if set_builder_facade is not None:
            tools.append(SetBuilderTool(set_builder_facade))
        if music_analysis_facade is not None:
            tools.append(MusicAnalysisBatchTool(music_analysis_facade))
        return cls(tuple(tools))

    def register(self, tool):
        if not isinstance(tool, AssistantTool):
            raise ToolRegistryError("ToolRegistry solo acepta AssistantTool.")
        if not isinstance(tool.name, str) or not tool.name.strip():
            raise ToolRegistryError("Cada herramienta debe tener un nombre válido.")
        if tool.name in self._tools:
            raise ToolRegistryError("No se permiten nombres de herramienta duplicados.")
        self._schema_validator.validate_schema(tool.input_schema)
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
            ToolSchemaValidator().validate_call(tool.input_schema, dict(call.arguments))
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
