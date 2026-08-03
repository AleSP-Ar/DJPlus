"""Allowlisted, DTO-only foundation for a future AI assistant."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from types import MappingProxyType


class AssistantError(ValueError):
    """Base error for controlled assistant tool requests."""


class UnknownAssistantToolError(AssistantError):
    """Raised when a caller asks for a tool outside the allowlist."""


@dataclass(frozen=True)
class AssistantActionProposalDTO:
    action_type: str
    label: str
    payload: dict

    def __post_init__(self):
        if not isinstance(self.payload, dict):
            raise AssistantError("La propuesta debe usar un payload de datos.")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


@dataclass(frozen=True)
class AssistantToolResultDTO:
    response: str
    data_used: dict
    proposed_actions: tuple[AssistantActionProposalDTO, ...] = ()

    def __post_init__(self):
        if not isinstance(self.data_used, dict):
            raise AssistantError("La herramienta debe devolver datos tipados.")
        if not isinstance(self.proposed_actions, tuple) or not all(
            isinstance(action, AssistantActionProposalDTO) for action in self.proposed_actions
        ):
            raise AssistantError("Las propuestas deben ser AssistantActionProposalDTO.")
        object.__setattr__(self, "data_used", MappingProxyType(dict(self.data_used)))


@dataclass(frozen=True)
class AssistantResponseDTO:
    response: str
    data_used: dict
    proposed_actions: tuple[AssistantActionProposalDTO, ...]
    requires_confirmation: bool


class AssistantTool(ABC):
    """A typed, narrow capability exposed to AssistantFacade."""

    name: str
    description: str
    input_schema: dict

    @abstractmethod
    def execute(self, input_data):
        """Return AssistantToolResultDTO without performing autonomous writes."""


class LibraryQueryTool(AssistantTool):
    name = "library_query"
    description = "Consulta estadísticas generales y cantidad de pistas."
    input_schema = {"type": "object", "properties": {}, "additionalProperties": False}

    def __init__(self, library_service):
        self.library_service = library_service

    def execute(self, input_data):
        self._validate_empty_input(input_data)
        count = self.library_service.count_tracks()
        return AssistantToolResultDTO(
            response=f"La biblioteca contiene {count} pistas.",
            data_used={"track_count": count},
        )

    def _validate_empty_input(self, input_data):
        if input_data not in ({}, None):
            raise AssistantError("Esta consulta no acepta parámetros.")


class PlaylistInsightTool(AssistantTool):
    name = "playlist_insight"
    description = "Resume playlists y puede proponer una nueva playlist sin crearla."
    input_schema = {
        "type": "object",
        "properties": {"proposal_name": {"type": "string"}},
        "additionalProperties": False,
    }

    def __init__(self, playlist_service):
        self.playlist_service = playlist_service

    def execute(self, input_data):
        payload = dict(input_data or {})
        if set(payload) - {"proposal_name"}:
            raise AssistantError("La consulta de playlists recibió parámetros no permitidos.")
        playlists = self.playlist_service.list_playlists()
        playlist_count = len(playlists)
        track_count = sum(self.playlist_service.count_tracks(playlist.id) for playlist in playlists)
        actions = ()
        proposal_name = payload.get("proposal_name")
        if proposal_name is not None:
            if not isinstance(proposal_name, str) or not proposal_name.strip():
                raise AssistantError("El nombre de la playlist propuesta es obligatorio.")
            actions = (
                AssistantActionProposalDTO(
                    action_type="create_playlist",
                    label=f"Crear playlist {proposal_name.strip()}",
                    payload={"name": proposal_name.strip()},
                ),
            )
        return AssistantToolResultDTO(
            response=f"Hay {playlist_count} playlists con {track_count} pistas asociadas.",
            data_used={"playlist_count": playlist_count, "playlist_track_count": track_count},
            proposed_actions=actions,
        )


class DJCompatibilityTool(AssistantTool):
    name = "dj_compatibility"
    description = "Consulta compatibilidad determinista entre dos pistas proporcionadas por el llamador."
    input_schema = {
        "type": "object",
        "required": ["track_a", "track_b"],
        "properties": {"track_a": {"type": "track"}, "track_b": {"type": "track"}},
        "additionalProperties": False,
    }

    def __init__(self, dj_intelligence_service):
        self.dj_intelligence_service = dj_intelligence_service

    def execute(self, input_data):
        payload = dict(input_data or {})
        if set(payload) != {"track_a", "track_b"}:
            raise AssistantError("La compatibilidad requiere únicamente track_a y track_b.")
        result = self.dj_intelligence_service.evaluate_compatibility(payload["track_a"], payload["track_b"])
        return AssistantToolResultDTO(
            response=f"Compatibilidad: {result.score}/100.",
            data_used={
                "track_a_id": result.track_a_id,
                "track_b_id": result.track_b_id,
                "score": result.score,
                "reasons": result.reasons,
                "confidence": result.confidence,
            },
        )


class AssistantFacade:
    """Execute only registered tools and return non-executable response DTOs."""

    def __init__(self, tools):
        registry = {}
        for tool in tools:
            if not isinstance(tool, AssistantTool):
                raise TypeError("AssistantFacade requiere herramientas AssistantTool.")
            if not isinstance(tool.name, str) or not tool.name or tool.name in registry:
                raise AssistantError("Cada herramienta permitida debe tener un nombre único.")
            registry[tool.name] = tool
        self._tools = registry

    def available_tools(self):
        return tuple(
            {"name": tool.name, "description": tool.description, "input_schema": dict(tool.input_schema)}
            for tool in self._tools.values()
        )

    def execute(self, tool_name, input_data=None):
        try:
            tool = self._tools[tool_name]
        except KeyError as error:
            raise UnknownAssistantToolError("La herramienta solicitada no está permitida.") from error
        result = tool.execute(input_data)
        if not isinstance(result, AssistantToolResultDTO):
            raise AssistantError("La herramienta debe devolver AssistantToolResultDTO.")
        actions = tuple(result.proposed_actions)
        return AssistantResponseDTO(
            response=result.response,
            data_used=dict(result.data_used),
            proposed_actions=actions,
            requires_confirmation=bool(actions),
        )
