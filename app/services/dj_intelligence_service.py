"""Deterministic, explainable compatibility scoring with no persistence."""

from dataclasses import dataclass
from numbers import Real


class CompatibilityError(ValueError):
    """Raised when a compatibility request has no valid track identity."""


@dataclass(frozen=True)
class CompatibilityResultDTO:
    track_a_id: int
    track_b_id: int
    score: int
    reasons: tuple[str, ...]
    confidence: float

    def __post_init__(self):
        if not isinstance(self.track_a_id, int) or self.track_a_id < 1:
            raise CompatibilityError("La primera pista debe tener un identificador válido.")
        if not isinstance(self.track_b_id, int) or self.track_b_id < 1:
            raise CompatibilityError("La segunda pista debe tener un identificador válido.")
        if not isinstance(self.score, int) or not 0 <= self.score <= 100:
            raise CompatibilityError("El score debe ser un entero entre 0 y 100.")
        if not self.reasons or not all(isinstance(reason, str) and reason for reason in self.reasons):
            raise CompatibilityError("La compatibilidad debe incluir motivos explicables.")
        if not isinstance(self.confidence, (int, float)) or not 0 <= self.confidence <= 1:
            raise CompatibilityError("La confianza debe estar entre 0 y 1.")


class ScoringEngine:
    """Pure scoring rules for BPM, exact key agreement, and normalized energy."""

    WEIGHTS = {"bpm": 50, "key": 30, "energy": 20}

    def score(self, track_a, track_b, history_context=None):
        """Return a deterministic DTO; ``history_context`` is an intentional future hook."""
        track_a_id = self._track_id(track_a, "primera")
        track_b_id = self._track_id(track_b, "segunda")
        weighted_score = 0.0
        available_weight = 0
        reasons = []

        bpm_score, bpm_reasons, bpm_available = self._bpm_component(track_a, track_b)
        weighted_score += self.WEIGHTS["bpm"] * bpm_score
        available_weight += self.WEIGHTS["bpm"] if bpm_available else 0
        reasons.extend(bpm_reasons)

        key_score, key_reasons, key_available = self._key_component(track_a, track_b)
        weighted_score += self.WEIGHTS["key"] * key_score
        available_weight += self.WEIGHTS["key"] if key_available else 0
        reasons.extend(key_reasons)

        energy_score, energy_reasons, energy_available = self._energy_component(track_a, track_b)
        weighted_score += self.WEIGHTS["energy"] * energy_score
        available_weight += self.WEIGHTS["energy"] if energy_available else 0
        reasons.extend(energy_reasons)

        score = round(weighted_score / available_weight * 100) if available_weight else 0
        confidence = round(available_weight / sum(self.WEIGHTS.values()), 2)
        return CompatibilityResultDTO(track_a_id, track_b_id, score, tuple(reasons), confidence)

    def _bpm_component(self, track_a, track_b):
        first, second = self._number(track_a, "bpm"), self._number(track_b, "bpm")
        if first is None or second is None:
            return 0, ("BPM no disponible",), False
        difference = abs(first - second)
        if difference <= 2:
            return 1, (f"BPM compatible (Δ {difference:g})",), True
        if difference <= 6:
            return 0.6, (f"BPM cercano (Δ {difference:g})",), True
        return 0, (f"BPM distante (Δ {difference:g})",), True

    def _key_component(self, track_a, track_b):
        first, second = self._key(track_a), self._key(track_b)
        if first is None or second is None:
            return 0, ("Key no disponible",), False
        if first == second:
            return 1, ("Key compatible",), True
        return 0, ("Key diferente",), True

    def _energy_component(self, track_a, track_b):
        first, second = self._number(track_a, "energy"), self._number(track_b, "energy")
        if first is None or second is None:
            return 0, ("Energía no disponible",), False
        difference = abs(first - second)
        if difference <= 10:
            return 1, (f"Energía similar (Δ {difference:g})",), True
        if difference <= 30:
            return 0.5, (f"Energía con diferencia moderada (Δ {difference:g})",), True
        return 0, (f"Energía distante (Δ {difference:g})",), True

    def _track_id(self, track, label):
        track_id = getattr(track, "id", None)
        if not isinstance(track_id, int) or track_id < 1:
            raise CompatibilityError(f"La {label} pista debe tener un identificador válido.")
        return track_id

    def _number(self, track, attribute):
        value = getattr(track, attribute, None)
        if isinstance(value, bool) or not isinstance(value, Real):
            return None
        return float(value)

    def _key(self, track):
        value = getattr(track, "key", None)
        if not isinstance(value, str) or not value.strip():
            return None
        return value.strip().casefold()


class DJIntelligenceService:
    """Public, read-only boundary for explainable track compatibility."""

    def __init__(self, scoring_engine=None):
        self.scoring_engine = scoring_engine or ScoringEngine()

    def evaluate_compatibility(self, track_a, track_b, history_context=None):
        return self.scoring_engine.score(track_a, track_b, history_context=history_context)
