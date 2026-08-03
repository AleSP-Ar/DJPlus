"""Deterministic energy-curve planning layered over SetPlanningEngine."""

from dataclasses import dataclass
from numbers import Real

from .set_planning import SetPlanDTO, SetPlanQueryDTO, SetPlanningEngine


class EnergyJourneyError(ValueError):
    """Raised when an energy journey contract is invalid."""


@dataclass(frozen=True)
class EnergyPhaseDTO:
    name: str
    start_position: int
    end_position: int
    target_energy_start: float
    target_energy_end: float

    def __post_init__(self):
        if self.name not in {"warm-up", "build", "peak", "cooldown"}:
            raise EnergyJourneyError("La fase energetica no es valida.")
        if not isinstance(self.start_position, int) or not isinstance(self.end_position, int) or not 1 <= self.start_position <= self.end_position:
            raise EnergyJourneyError("Las posiciones de fase deben ser consecutivas y positivas.")
        for value in (self.target_energy_start, self.target_energy_end):
            if isinstance(value, bool) or not isinstance(value, Real) or not 0 <= value <= 100:
                raise EnergyJourneyError("La energia objetivo debe estar entre 0 y 100.")


@dataclass(frozen=True)
class SetJourneyPolicyDTO:
    curve: str = "arc"
    energy_tolerance: float = 15.0

    def __post_init__(self):
        if self.curve not in {"ascending", "descending", "arc"}:
            raise EnergyJourneyError("La curva debe ser ascending, descending o arc.")
        if isinstance(self.energy_tolerance, bool) or not isinstance(self.energy_tolerance, Real) or not 0 <= self.energy_tolerance <= 100:
            raise EnergyJourneyError("La tolerancia energetica debe estar entre 0 y 100.")


@dataclass(frozen=True)
class EnergyJourneyDTO:
    set_plan: SetPlanDTO
    phases: tuple[EnergyPhaseDTO, ...]
    target_energy_by_position: tuple[float, ...]
    deviations: tuple[str, ...]
    explanation: str

    def __post_init__(self):
        if not isinstance(self.set_plan, SetPlanDTO):
            raise EnergyJourneyError("El recorrido requiere SetPlanDTO.")
        if not isinstance(self.phases, tuple) or tuple(phase.name for phase in self.phases) != ("warm-up", "build", "peak", "cooldown"):
            raise EnergyJourneyError("El recorrido debe incluir las cuatro fases ordenadas.")
        if not isinstance(self.target_energy_by_position, tuple) or len(self.target_energy_by_position) != self.set_plan.target_track_count:
            raise EnergyJourneyError("Debe haber un objetivo por posicion planificada.")
        if not all(isinstance(value, Real) and 0 <= value <= 100 for value in self.target_energy_by_position):
            raise EnergyJourneyError("Los objetivos deben ser energia valida.")
        if not isinstance(self.deviations, tuple) or not all(isinstance(item, str) and item for item in self.deviations):
            raise EnergyJourneyError("Las desviaciones deben ser texto no vacio.")
        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise EnergyJourneyError("La explicacion del recorrido es obligatoria.")


class EnergyJourneyPlanner:
    """Plan warm-up, build, peak and cooldown with no storage or UI dependencies."""

    def __init__(self, set_planning_engine, policy=None):
        if not isinstance(set_planning_engine, SetPlanningEngine):
            raise TypeError("EnergyJourneyPlanner requiere SetPlanningEngine.")
        if policy is not None and not isinstance(policy, SetJourneyPolicyDTO):
            raise TypeError("policy debe ser SetJourneyPolicyDTO o nulo.")
        self._set_planning_engine = set_planning_engine
        self._policy = policy or SetJourneyPolicyDTO()

    def plan(self, query, policy=None):
        if not isinstance(query, SetPlanQueryDTO):
            raise TypeError("EnergyJourneyPlanner.plan requiere SetPlanQueryDTO.")
        if policy is not None and not isinstance(policy, SetJourneyPolicyDTO):
            raise TypeError("policy debe ser SetJourneyPolicyDTO o nulo.")
        if query.target_track_count < 4:
            raise EnergyJourneyError("Un recorrido energetico requiere al menos cuatro pistas.")
        active_policy = policy or self._policy
        phases, targets = self._journey(query.target_track_count, active_policy)
        plan = self._set_planning_engine.plan(query, lambda _current, candidate, position: self._matches_target(candidate, targets[position - 1], active_policy))
        deviations = self._deviations(query, plan, targets)
        explanation = (
            f"Recorrido {active_policy.curve} completo con {len(plan.tracks)} pistas."
            if not plan.is_partial else f"Recorrido {active_policy.curve} parcial: {len(plan.tracks)} de {query.target_track_count} pistas; no hubo candidatas adecuadas."
        )
        return EnergyJourneyDTO(plan, phases, targets, deviations, explanation)

    def _journey(self, count, policy):
        endpoints = {
            "ascending": ((35, 48), (48, 65), (65, 82), (82, 92)),
            "descending": ((92, 82), (82, 65), (65, 48), (48, 35)),
            "arc": ((35, 50), (50, 72), (72, 92), (92, 50)),
        }[policy.curve]
        names = ("warm-up", "build", "peak", "cooldown")
        base, remainder = divmod(count, 4)
        sizes = tuple(base + (1 if index < remainder else 0) for index in range(4))
        phases, targets, start = [], [], 1
        for name, size, (first, last) in zip(names, sizes, endpoints):
            end = start + size - 1
            phases.append(EnergyPhaseDTO(name, start, end, first, last))
            targets.extend(last if size == 1 else round(first + (last - first) * index / (size - 1), 2) for index in range(size))
            start = end + 1
        return tuple(phases), tuple(targets)

    def _matches_target(self, candidate, target, policy):
        energy = getattr(candidate, "energy", None)
        return isinstance(energy, Real) and not isinstance(energy, bool) and abs(float(energy) - target) <= policy.energy_tolerance

    def _deviations(self, query, plan, targets):
        deviations = []
        track_by_id = {query.initial_track.id: query.initial_track, **{track.id: track for track in query.candidates}}
        for track in plan.tracks:
            energy = getattr(track_by_id[track.track_id], "energy", None)
            if not isinstance(energy, Real) or abs(float(energy) - targets[track.position - 1]) > self._policy.energy_tolerance:
                deviations.append(f"Posicion {track.position}: energia fuera del objetivo {targets[track.position - 1]:g}.")
        if plan.is_partial:
            deviations.append(f"Posicion {len(plan.tracks) + 1}: no hay candidata dentro de la energia objetivo.")
        return tuple(deviations)
