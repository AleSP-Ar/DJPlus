"""Deterministic, in-memory set sequencing through RecommendationService."""

from dataclasses import dataclass
from numbers import Real

from .recommendation_scoring import RecommendationReasonDTO
from .recommendation_service import RecommendationQueryDTO, RecommendationService


class SetPlanningError(ValueError):
    """Raised when a set planning contract is invalid."""


@dataclass(frozen=True)
class SetPlanningPolicyDTO:
    max_bpm_jump: float = 6.0
    max_energy_jump: float = 25.0

    def __post_init__(self):
        for name in ("max_bpm_jump", "max_energy_jump"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, Real) or value < 0:
                raise SetPlanningError(f"{name} debe ser un numero no negativo.")


@dataclass(frozen=True)
class SetPlanQueryDTO:
    initial_track: object
    candidates: tuple[object, ...]
    target_track_count: int

    def __post_init__(self):
        initial_id = getattr(self.initial_track, "id", None)
        candidate_ids = tuple(getattr(track, "id", None) for track in self.candidates)
        if not isinstance(initial_id, int) or initial_id < 1:
            raise SetPlanningError("La pista inicial debe tener id positivo.")
        if not isinstance(self.candidates, tuple) or not all(isinstance(track_id, int) and track_id > 0 for track_id in candidate_ids):
            raise SetPlanningError("Los candidatos deben ser una tupla de pistas con id positivo.")
        if len(set(candidate_ids)) != len(candidate_ids):
            raise SetPlanningError("Los candidatos no pueden repetirse.")
        if not isinstance(self.target_track_count, int) or not 1 <= self.target_track_count <= 100:
            raise SetPlanningError("La cantidad objetivo debe estar entre 1 y 100.")


@dataclass(frozen=True)
class SetPlanTrackDTO:
    position: int
    track_id: int
    score: int | None
    confidence: float | None
    transition_reasons: tuple[RecommendationReasonDTO, ...]

    def __post_init__(self):
        if not isinstance(self.position, int) or self.position < 1 or not isinstance(self.track_id, int) or self.track_id < 1:
            raise SetPlanningError("Cada pista del plan debe tener posicion e id positivos.")
        if self.score is not None and (not isinstance(self.score, int) or not 0 <= self.score <= 100):
            raise SetPlanningError("El score de transicion no es valido.")
        if self.confidence is not None and (not isinstance(self.confidence, Real) or not 0 <= self.confidence <= 1):
            raise SetPlanningError("La confianza de transicion no es valida.")
        if not isinstance(self.transition_reasons, tuple) or not all(isinstance(item, RecommendationReasonDTO) for item in self.transition_reasons):
            raise SetPlanningError("Las razones de transicion deben ser inmutables.")
        if self.position == 1 and (self.score is not None or self.confidence is not None or self.transition_reasons):
            raise SetPlanningError("La pista inicial no tiene transicion previa.")


@dataclass(frozen=True)
class SetPlanDTO:
    tracks: tuple[SetPlanTrackDTO, ...]
    target_track_count: int
    is_partial: bool
    explanation: str

    def __post_init__(self):
        if not isinstance(self.tracks, tuple) or not self.tracks or not all(isinstance(track, SetPlanTrackDTO) for track in self.tracks):
            raise SetPlanningError("El plan debe contener pistas tipadas.")
        if tuple(track.position for track in self.tracks) != tuple(range(1, len(self.tracks) + 1)):
            raise SetPlanningError("Las posiciones del plan deben ser consecutivas.")
        ids = tuple(track.track_id for track in self.tracks)
        if len(set(ids)) != len(ids):
            raise SetPlanningError("El plan no puede contener pistas duplicadas.")
        if not isinstance(self.target_track_count, int) or self.target_track_count < len(self.tracks):
            raise SetPlanningError("La cantidad objetivo debe cubrir el plan.")
        if not isinstance(self.is_partial, bool) or self.is_partial != (len(self.tracks) < self.target_track_count):
            raise SetPlanningError("El estado parcial debe coincidir con la longitud del plan.")
        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise SetPlanningError("El plan requiere una explicacion.")


class SetPlanningEngine:
    """Build a deterministic sequence without persistence or playlist side effects."""

    def __init__(self, recommendation_service, policy=None):
        if not isinstance(recommendation_service, RecommendationService):
            raise TypeError("SetPlanningEngine requiere RecommendationService.")
        if policy is not None and not isinstance(policy, SetPlanningPolicyDTO):
            raise TypeError("policy debe ser SetPlanningPolicyDTO o nulo.")
        self._recommendation_service = recommendation_service
        self._policy = policy or SetPlanningPolicyDTO()

    def plan(self, query, transition_validator=None):
        if not isinstance(query, SetPlanQueryDTO):
            raise TypeError("SetPlanningEngine.plan requiere SetPlanQueryDTO.")
        if transition_validator is not None and not callable(transition_validator):
            raise TypeError("transition_validator debe ser callable o nulo.")
        tracks = [SetPlanTrackDTO(1, query.initial_track.id, None, None, ())]
        current = query.initial_track
        remaining = {track.id: track for track in query.candidates if track.id != current.id}
        while len(tracks) < query.target_track_count and remaining:
            ranked = self._recommendation_service.recommend(
                RecommendationQueryDTO(current, tuple(remaining.values()), min(100, len(remaining)))
            )
            chosen = next((item for item in ranked if self._valid_transition(current, remaining[item.candidate_track_id]) and (
                transition_validator(current, remaining[item.candidate_track_id], len(tracks) + 1) if transition_validator else True
            )), None)
            if chosen is None:
                break
            current = remaining.pop(chosen.candidate_track_id)
            reason_order = {"bpm": 0, "key": 1, "genre": 2, "energy": 3, "history": 4}
            reasons = tuple(sorted(
                (
                    reason for reason in chosen.reasons
                    if reason.criterion != "genre" or "no disponible" not in reason.explanation.casefold()
                ),
                key=lambda reason: reason_order[reason.criterion],
            ))
            tracks.append(SetPlanTrackDTO(len(tracks) + 1, current.id, chosen.score, chosen.confidence, reasons))
        partial = len(tracks) < query.target_track_count
        explanation = (
            f"Plan parcial: {len(tracks)} de {query.target_track_count} pistas; no hay transiciones validas."
            if partial else f"Plan completo de {len(tracks)} pistas."
        )
        return SetPlanDTO(tuple(tracks), query.target_track_count, partial, explanation)

    def _valid_transition(self, current, candidate):
        return self._difference(current, candidate, "bpm") <= self._policy.max_bpm_jump and self._difference(current, candidate, "energy") <= self._policy.max_energy_jump

    @staticmethod
    def _difference(first, second, attribute):
        first_value, second_value = getattr(first, attribute, None), getattr(second, attribute, None)
        if any(isinstance(value, bool) or not isinstance(value, Real) for value in (first_value, second_value)):
            return float("inf")
        return abs(float(first_value) - float(second_value))
