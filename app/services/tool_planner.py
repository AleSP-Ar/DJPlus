"""Pure, deterministic planning of allowlisted tool calls without execution."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .tool_dispatcher import ToolCallDTO, ToolRegistry


class ToolPlanningError(ValueError):
    """Raised when a plan violates its ordered, dependency-safe contract."""


@dataclass(frozen=True)
class PlannedToolCallDTO:
    call_id: str
    tool_call: ToolCallDTO
    depends_on: tuple[str, ...] = ()

    def __post_init__(self):
        if not isinstance(self.call_id, str) or not self.call_id.strip():
            raise ToolPlanningError("El identificador del paso planificado es obligatorio.")
        if not isinstance(self.tool_call, ToolCallDTO):
            raise ToolPlanningError("El paso planificado requiere ToolCallDTO.")
        if not isinstance(self.depends_on, tuple) or not all(isinstance(value, str) and value.strip() for value in self.depends_on):
            raise ToolPlanningError("Las dependencias deben ser una tupla de identificadores.")
        if self.call_id in self.depends_on or len(set(self.depends_on)) != len(self.depends_on):
            raise ToolPlanningError("Las dependencias no pueden repetirse ni depender de si mismas.")


@dataclass(frozen=True)
class ToolPlanDTO:
    user_query: str
    planned_calls: tuple[PlannedToolCallDTO, ...]

    def __post_init__(self):
        if not isinstance(self.user_query, str) or not self.user_query.strip():
            raise ToolPlanningError("La consulta para planificar es obligatoria.")
        if not isinstance(self.planned_calls, tuple) or not all(isinstance(call, PlannedToolCallDTO) for call in self.planned_calls):
            raise ToolPlanningError("El plan debe contener pasos tipados inmutables.")
        seen = set()
        for call in self.planned_calls:
            if call.call_id in seen:
                raise ToolPlanningError("Los identificadores de pasos no pueden repetirse.")
            if set(call.depends_on) - seen:
                raise ToolPlanningError("Cada dependencia debe apuntar a un paso anterior del plan.")
            seen.add(call.call_id)


class ToolPlanner(ABC):
    @abstractmethod
    def plan(self, user_query, tool_registry):
        """Return ToolPlanDTO without dispatching or executing any tool."""


class DeterministicToolPlanner(ToolPlanner):
    """Keyword planner with stable call ordering and registry-only validation."""

    _RULES = (
        ("library_query", ("biblioteca", "pista", "bpm", "genero", "género", "rating", "favorit", "key", "tono", "clave")),
        ("playlist", ("playlist", "lista de reproduccion", "lista de reproducción")),
        ("collection", ("coleccion", "colección")),
    )

    def plan(self, user_query, tool_registry):
        if not isinstance(user_query, str) or not user_query.strip():
            raise ToolPlanningError("La consulta para planificar es obligatoria.")
        if not isinstance(tool_registry, ToolRegistry):
            raise TypeError("DeterministicToolPlanner requiere ToolRegistry.")
        normalized = user_query.casefold()
        calls = []
        for tool_name, keywords in self._RULES:
            if any(keyword in normalized for keyword in keywords):
                tool_registry.resolve(tool_name)
                arguments = {"query": user_query.strip()} if tool_name == "library_query" else {}
                calls.append(PlannedToolCallDTO(f"step-{len(calls) + 1}", ToolCallDTO(tool_name, arguments)))
        return ToolPlanDTO(user_query.strip(), tuple(calls))
