"""Deterministic, explainable scoring for one recommendation candidate at a time."""

from dataclasses import dataclass
from numbers import Real

from .dj_intelligence_service import DJIntelligenceService


class RecommendationScoringError(ValueError):
    """Raised when recommendation inputs or service contracts are invalid."""


@dataclass(frozen=True)
class RecommendationReasonDTO:
    criterion: str
    contribution: int
    explanation: str

    def __post_init__(self):
        if self.criterion not in {"bpm", "key", "energy", "history"}:
            raise RecommendationScoringError("El criterio de recomendacion no es valido.")
        if not isinstance(self.contribution, int) or not 0 <= self.contribution <= 100:
            raise RecommendationScoringError("La contribucion debe estar entre 0 y 100.")
        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise RecommendationScoringError("La razon de recomendacion es obligatoria.")


@dataclass(frozen=True)
class RecommendationScoreDTO:
    reference_track_id: int
    candidate_track_id: int
    score: int
    reasons: tuple[RecommendationReasonDTO, ...]
    confidence: float = 1.0

    def __post_init__(self):
        for name in ("reference_track_id", "candidate_track_id"):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 1:
                raise RecommendationScoringError(f"{name} debe ser un entero positivo.")
        if not isinstance(self.score, int) or not 0 <= self.score <= 100:
            raise RecommendationScoringError("El score de recomendacion debe estar entre 0 y 100.")
        if not isinstance(self.reasons, tuple) or tuple(reason.criterion for reason in self.reasons) != ("bpm", "key", "energy", "history"):
            raise RecommendationScoringError("El score debe incluir razones BPM, key, energia e historial en orden.")
        if not isinstance(self.confidence, (int, float)) or not 0 <= self.confidence <= 1:
            raise RecommendationScoringError("La confianza debe estar entre 0 y 1.")


class RecommendationScoringEngine:
    """Score one candidate using services only; it never ranks or persists candidates."""

    WEIGHTS = {"bpm": 35, "key": 25, "energy": 25, "history": 15}

    def __init__(self, dj_intelligence_service, history_service):
        if not isinstance(dj_intelligence_service, DJIntelligenceService):
            raise TypeError("RecommendationScoringEngine requiere DJIntelligenceService.")
        if not callable(getattr(history_service, "count_history", None)):
            raise TypeError("RecommendationScoringEngine requiere HistoryService.")
        self._dj_intelligence_service = dj_intelligence_service
        self._history_service = history_service

    def score(self, reference_track, candidate_track):
        reference_id = self._track_id(reference_track, "referencia")
        candidate_id = self._track_id(candidate_track, "candidata")
        self._dj_intelligence_service.evaluate_compatibility(reference_track, candidate_track)
        reasons = (
            self._bpm_reason(reference_track, candidate_track),
            self._key_reason(reference_track, candidate_track),
            self._energy_reason(reference_track, candidate_track),
            self._history_reason(candidate_id),
        )
        confidence = round(sum("no disponible" not in reason.explanation.casefold() for reason in reasons) / len(reasons), 2)
        return RecommendationScoreDTO(reference_id, candidate_id, sum(reason.contribution for reason in reasons), reasons, confidence)

    def _bpm_reason(self, reference, candidate):
        first, second = self._number(reference, "bpm"), self._number(candidate, "bpm")
        if first is None or second is None:
            return self._reason("bpm", 0, "BPM no disponible para la recomendacion.")
        difference = abs(first - second)
        if difference <= 2:
            return self._reason("bpm", 1, f"BPM muy compatible (diferencia {difference:g}).")
        if difference <= 6:
            return self._reason("bpm", 0.6, f"BPM cercano (diferencia {difference:g}).")
        return self._reason("bpm", 0, f"BPM distante (diferencia {difference:g}).")

    def _key_reason(self, reference, candidate):
        first, second = self._key(reference), self._key(candidate)
        if first is None or second is None:
            return self._reason("key", 0, "Key no disponible para la recomendacion.")
        if first == second:
            return self._reason("key", 1, "Key compatible.")
        return self._reason("key", 0, "Key diferente.")

    def _energy_reason(self, reference, candidate):
        first, second = self._number(reference, "energy"), self._number(candidate, "energy")
        if first is None or second is None:
            return self._reason("energy", 0, "Energia no disponible para la recomendacion.")
        difference = abs(first - second)
        if difference <= 10:
            return self._reason("energy", 1, f"Energia similar (diferencia {difference:g}).")
        if difference <= 30:
            return self._reason("energy", 0.5, f"Energia moderadamente cercana (diferencia {difference:g}).")
        return self._reason("energy", 0, f"Energia distante (diferencia {difference:g}).")

    def _history_reason(self, candidate_id):
        count = self._history_service.count_history(candidate_id, "played")
        if not isinstance(count, int) or count < 0:
            raise RecommendationScoringError("HistoryService devolvio un conteo invalido.")
        if count >= 5:
            return self._reason("history", 1, f"Historial fuerte: reproducida {count} veces.")
        if count >= 1:
            return self._reason("history", 0.5, f"Historial disponible: reproducida {count} veces.")
        return self._reason("history", 0, "Sin reproducciones previas registradas.")

    def _reason(self, criterion, ratio, explanation):
        return RecommendationReasonDTO(criterion, round(self.WEIGHTS[criterion] * ratio), explanation)

    def _track_id(self, track, label):
        value = getattr(track, "id", None)
        if not isinstance(value, int) or value < 1:
            raise RecommendationScoringError(f"La pista {label} debe tener id positivo.")
        return value

    def _number(self, track, attribute):
        value = getattr(track, attribute, None)
        return float(value) if isinstance(value, Real) and not isinstance(value, bool) else None

    def _key(self, track):
        value = getattr(track, "key", None)
        return value.strip().casefold() if isinstance(value, str) and value.strip() else None
