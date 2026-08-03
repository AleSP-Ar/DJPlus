"""Pure, read-only planning for adopting local music-analysis metadata."""

from dataclasses import dataclass
from numbers import Real


class AnalysisChangePlanningError(ValueError):
    """Raised when a metadata comparison contract is invalid."""


@dataclass(frozen=True)
class AnalysisMetadataDTO:
    """Current or analyzed BPM, key and energy for exactly one track."""

    track_id: int
    bpm: float | None = None
    key: str | None = None
    energy: float | None = None
    bpm_confidence: float | None = None
    key_confidence: float | None = None
    energy_confidence: float | None = None

    def __post_init__(self):
        if not isinstance(self.track_id, int) or self.track_id < 1:
            raise AnalysisChangePlanningError("track_id debe ser positivo.")
        if self.bpm is not None and (not isinstance(self.bpm, Real) or isinstance(self.bpm, bool) or self.bpm <= 0):
            raise AnalysisChangePlanningError("BPM debe ser positivo o nulo.")
        if self.key is not None and (not isinstance(self.key, str) or not self.key.strip()):
            raise AnalysisChangePlanningError("key debe ser texto no vacio o nulo.")
        if self.energy is not None and (not isinstance(self.energy, Real) or isinstance(self.energy, bool) or not 0 <= self.energy <= 100):
            raise AnalysisChangePlanningError("energy debe estar entre 0 y 100 o ser nula.")
        for field in ("bpm", "key", "energy"):
            confidence = getattr(self, f"{field}_confidence")
            if confidence is not None and (not isinstance(confidence, Real) or isinstance(confidence, bool) or not 0 <= confidence <= 1):
                raise AnalysisChangePlanningError("Las confianzas deben estar entre 0 y 1 o ser nulas.")
            if getattr(self, field) is None and confidence is not None:
                raise AnalysisChangePlanningError("No puede haber confianza para un valor ausente.")
        if self.key is not None:
            object.__setattr__(self, "key", self.key.strip())


@dataclass(frozen=True)
class AnalysisWritePolicyDTO:
    mode: str = "never_overwrite"

    def __post_init__(self):
        if self.mode not in {"never_overwrite", "overwrite_lower_confidence", "force"}:
            raise AnalysisChangePlanningError("La politica de escritura no es valida.")


@dataclass(frozen=True)
class AnalysisChangeDTO:
    field: str
    classification: str
    previous_value: object | None
    proposed_value: object | None
    previous_confidence: float | None
    proposed_confidence: float | None
    explanation: str

    def __post_init__(self):
        if self.field not in {"bpm", "key", "energy"}:
            raise AnalysisChangePlanningError("El campo de cambio no es valido.")
        if self.classification not in {"new", "unchanged", "conflict", "skipped"}:
            raise AnalysisChangePlanningError("La clasificacion de cambio no es valida.")
        for value in (self.previous_confidence, self.proposed_confidence):
            if value is not None and (not isinstance(value, Real) or isinstance(value, bool) or not 0 <= value <= 1):
                raise AnalysisChangePlanningError("La confianza de cambio no es valida.")
        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise AnalysisChangePlanningError("Cada cambio requiere explicacion.")


@dataclass(frozen=True)
class AnalysisChangeSetDTO:
    track_id: int
    policy: AnalysisWritePolicyDTO
    changes: tuple[AnalysisChangeDTO, ...]
    preview: str

    def __post_init__(self):
        if not isinstance(self.track_id, int) or self.track_id < 1:
            raise AnalysisChangePlanningError("El plan requiere track_id positivo.")
        if not isinstance(self.policy, AnalysisWritePolicyDTO):
            raise AnalysisChangePlanningError("El plan requiere una politica valida.")
        if not isinstance(self.changes, tuple) or tuple(change.field for change in self.changes) != ("bpm", "key", "energy"):
            raise AnalysisChangePlanningError("El plan requiere cambios BPM, key y energy ordenados.")
        if not isinstance(self.preview, str) or not self.preview.strip():
            raise AnalysisChangePlanningError("El plan requiere una vista previa.")

    @property
    def has_applicable_changes(self):
        return any(change.classification == "new" for change in self.changes)


class AnalysisChangePlanner:
    """Compare supplied DTOs only; this class never receives a persistence object."""

    def plan(self, existing, analyzed, policy=None):
        if not isinstance(existing, AnalysisMetadataDTO) or not isinstance(analyzed, AnalysisMetadataDTO):
            raise TypeError("AnalysisChangePlanner.plan requiere AnalysisMetadataDTO.")
        if existing.track_id != analyzed.track_id:
            raise AnalysisChangePlanningError("La metadata existente y analizada deben pertenecer a la misma pista.")
        policy = policy or AnalysisWritePolicyDTO()
        if not isinstance(policy, AnalysisWritePolicyDTO):
            raise TypeError("policy debe ser AnalysisWritePolicyDTO o nula.")
        changes = tuple(self._plan_field(field, existing, analyzed, policy) for field in ("bpm", "key", "energy"))
        preview = " | ".join(f"{change.field}: {change.classification} ({change.explanation})" for change in changes)
        return AnalysisChangeSetDTO(existing.track_id, policy, changes, preview)

    def _plan_field(self, field, existing, analyzed, policy):
        previous, proposed = getattr(existing, field), getattr(analyzed, field)
        previous_confidence = getattr(existing, f"{field}_confidence")
        proposed_confidence = getattr(analyzed, f"{field}_confidence")
        if proposed is None:
            return AnalysisChangeDTO(field, "skipped", previous, None, previous_confidence, None, "El analisis no aporto un valor con confianza suficiente.")
        if previous is None:
            return AnalysisChangeDTO(field, "new", None, proposed, None, proposed_confidence, "No existe metadata previa; el valor analizado se propone como nuevo.")
        if self._equal(field, previous, proposed):
            return AnalysisChangeDTO(field, "unchanged", previous, proposed, previous_confidence, proposed_confidence, "El valor analizado coincide con la metadata existente.")
        if policy.mode == "force":
            return AnalysisChangeDTO(field, "new", previous, proposed, previous_confidence, proposed_confidence, "La politica force propone reemplazar el valor existente.")
        if policy.mode == "overwrite_lower_confidence" and previous_confidence is not None and proposed_confidence is not None and proposed_confidence > previous_confidence:
            return AnalysisChangeDTO(field, "new", previous, proposed, previous_confidence, proposed_confidence, "La confianza analizada supera la confianza existente; se propone reemplazo.")
        reason = "La politica never_overwrite conserva la metadata existente." if policy.mode == "never_overwrite" else "No hay confianza existente menor verificable para autorizar el reemplazo."
        return AnalysisChangeDTO(field, "conflict", previous, proposed, previous_confidence, proposed_confidence, reason)

    @staticmethod
    def _equal(field, previous, proposed):
        if field == "key":
            return previous.strip().casefold() == proposed.strip().casefold()
        return abs(float(previous) - float(proposed)) < 0.01
