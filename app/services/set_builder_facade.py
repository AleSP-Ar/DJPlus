"""Read-only orchestration from LibraryService candidates to an energy-aware set."""

from dataclasses import dataclass
from types import MappingProxyType

from .energy_journey import EnergyJourneyPlanner, EnergyJourneyDTO, SetJourneyPolicyDTO
from .set_planning import SetPlanQueryDTO


class SetBuilderError(ValueError):
    """Raised when set builder input or injected service output is invalid."""


@dataclass(frozen=True)
class SetBuilderQueryDTO:
    initial_track: object
    target_track_count: int = 8
    energy_curve: str = "arc"
    bpm_min: float | None = None
    bpm_max: float | None = None
    key: str | None = None
    genre: str | None = None
    favorite: bool | None = None
    recent_history_limit: int = 20

    def __post_init__(self):
        if not isinstance(getattr(self.initial_track, "id", None), int) or self.initial_track.id < 1:
            raise SetBuilderError("La pista inicial debe tener id positivo.")
        if not isinstance(self.target_track_count, int) or not 4 <= self.target_track_count <= 100:
            raise SetBuilderError("La cantidad debe estar entre 4 y 100.")
        if self.energy_curve not in {"ascending", "descending", "arc"}:
            raise SetBuilderError("La curva energetica no es valida.")
        for name in ("bpm_min", "bpm_max"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0):
                raise SetBuilderError(f"{name} debe ser BPM positivo o nulo.")
        if self.bpm_min is not None and self.bpm_max is not None and self.bpm_min > self.bpm_max:
            raise SetBuilderError("bpm_min no puede superar bpm_max.")
        if self.key is not None and (not isinstance(self.key, str) or not self.key.strip()):
            raise SetBuilderError("key debe ser texto no vacio o nulo.")
        if self.genre is not None and (not isinstance(self.genre, str) or not self.genre.strip()):
            raise SetBuilderError("genre debe ser texto no vacio o nulo.")
        if self.favorite is not None and not isinstance(self.favorite, bool):
            raise SetBuilderError("favorite debe ser booleano o nulo.")
        if not isinstance(self.recent_history_limit, int) or not 0 <= self.recent_history_limit <= 100:
            raise SetBuilderError("recent_history_limit debe estar entre 0 y 100.")

    def filters(self):
        return MappingProxyType({name: value for name, value in {
            "bpm_min": self.bpm_min, "bpm_max": self.bpm_max, "key": self.key, "genre": self.genre, "favorite": self.favorite,
        }.items() if value is not None})


@dataclass(frozen=True)
class SetBuilderResultDTO:
    journey: EnergyJourneyDTO
    candidate_total: int
    excluded_recent_track_ids: tuple[int, ...]
    explanation: str

    def __post_init__(self):
        if not isinstance(self.journey, EnergyJourneyDTO):
            raise SetBuilderError("El resultado requiere EnergyJourneyDTO.")
        if not isinstance(self.candidate_total, int) or self.candidate_total < 0:
            raise SetBuilderError("El total de candidatas no es valido.")
        if not isinstance(self.excluded_recent_track_ids, tuple) or not all(isinstance(item, int) and item > 0 for item in self.excluded_recent_track_ids):
            raise SetBuilderError("Las exclusiones deben ser ids positivos.")
        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise SetBuilderError("La explicacion es obligatoria.")

    @property
    def sequence(self):
        return self.journey.set_plan.tracks

    @property
    def phases(self):
        return self.journey.phases

    def export_text(self):
        lines = [self.explanation, self.journey.explanation]
        lines.extend(f"{item.position}. pista={item.track_id}; score={item.score}; confidence={item.confidence}; reasons=" + ", ".join(reason.explanation for reason in item.transition_reasons) for item in self.sequence)
        lines.extend("desviacion=" + item for item in self.journey.deviations)
        return "\n".join(lines)


class SetBuilderFacade:
    """Use application services only; never stores or executes a resulting set."""

    def __init__(self, library_service, history_service, energy_journey_planner):
        if not callable(getattr(library_service, "query", None)) or not callable(getattr(library_service, "count_results", None)):
            raise TypeError("SetBuilderFacade requiere LibraryService.")
        if not callable(getattr(history_service, "list_history", None)):
            raise TypeError("SetBuilderFacade requiere HistoryService.")
        if not isinstance(energy_journey_planner, EnergyJourneyPlanner):
            raise TypeError("SetBuilderFacade requiere EnergyJourneyPlanner.")
        self._library_service = library_service
        self._history_service = history_service
        self._energy_journey_planner = energy_journey_planner

    def build(self, query):
        if not isinstance(query, SetBuilderQueryDTO):
            raise TypeError("SetBuilderFacade.build requiere SetBuilderQueryDTO.")
        rows, _has_more = self._library_service.query(text="", **dict(query.filters()))
        total = self._library_service.count_results()
        if not isinstance(rows, (tuple, list)) or not isinstance(total, int) or total < 0:
            raise SetBuilderError("LibraryService devolvio candidatas invalidas.")
        excluded = self._recent_track_ids(query.recent_history_limit)
        candidates = tuple(track for track in rows if getattr(track, "id", None) != query.initial_track.id and getattr(track, "id", None) not in excluded)
        journey = self._energy_journey_planner.plan(
            SetPlanQueryDTO(query.initial_track, candidates, query.target_track_count),
            SetJourneyPolicyDTO(query.energy_curve),
        )
        explanation = f"Candidatas: {total}; excluidas por historial: {len(excluded)}; {journey.explanation}"
        return SetBuilderResultDTO(journey, total, tuple(sorted(excluded)), explanation)

    def _recent_track_ids(self, limit):
        if limit == 0:
            return set()
        events = self._history_service.list_history(event_type="played", limit=limit)
        if not isinstance(events, (tuple, list)):
            raise SetBuilderError("HistoryService devolvio historial invalido.")
        return {track_id for event in events for track_id in ((event.get("track_id") if isinstance(event, dict) else getattr(event, "track_id", None)),) if isinstance(track_id, int) and track_id > 0}
