"""In-memory deterministic ranking built only on RecommendationScoringEngine."""

from dataclasses import dataclass

from .recommendation_scoring import RecommendationReasonDTO, RecommendationScoringEngine


class RecommendationServiceError(ValueError):
    """Raised when a ranking query or ranked DTO violates its contract."""


@dataclass(frozen=True)
class RecommendationQueryDTO:
    current_track: object
    candidates: tuple[object, ...]
    limit: int = 10

    def __post_init__(self):
        current_id = getattr(self.current_track, "id", None)
        if not isinstance(current_id, int) or current_id < 1:
            raise RecommendationServiceError("La pista actual debe tener un id positivo.")
        if not isinstance(self.candidates, tuple):
            raise RecommendationServiceError("Los candidatos deben ser una tupla inmutable.")
        candidate_ids = tuple(getattr(track, "id", None) for track in self.candidates)
        if not all(isinstance(track_id, int) and track_id > 0 for track_id in candidate_ids):
            raise RecommendationServiceError("Cada candidata debe tener un id positivo.")
        if len(set(candidate_ids)) != len(candidate_ids):
            raise RecommendationServiceError("Los candidatos no pueden repetirse.")
        if not isinstance(self.limit, int) or not 1 <= self.limit <= 100:
            raise RecommendationServiceError("El limite debe estar entre 1 y 100.")


@dataclass(frozen=True)
class RankedRecommendationDTO:
    rank: int
    candidate_track_id: int
    score: int
    confidence: float
    reasons: tuple[RecommendationReasonDTO, ...]

    def __post_init__(self):
        if not isinstance(self.rank, int) or self.rank < 1:
            raise RecommendationServiceError("El rango debe ser un entero positivo.")
        if not isinstance(self.candidate_track_id, int) or self.candidate_track_id < 1:
            raise RecommendationServiceError("La candidata debe tener un id positivo.")
        if not isinstance(self.score, int) or not 0 <= self.score <= 100:
            raise RecommendationServiceError("El score debe estar entre 0 y 100.")
        if not isinstance(self.confidence, (int, float)) or not 0 <= self.confidence <= 1:
            raise RecommendationServiceError("La confianza debe estar entre 0 y 1.")
        if not isinstance(self.reasons, tuple) or not all(isinstance(reason, RecommendationReasonDTO) for reason in self.reasons):
            raise RecommendationServiceError("Las razones deben ser RecommendationReasonDTO inmutables.")


class RecommendationService:
    """Rank candidates deterministically without storage or model generation."""

    def __init__(self, scoring_engine):
        if not isinstance(scoring_engine, RecommendationScoringEngine):
            raise TypeError("RecommendationService requiere RecommendationScoringEngine.")
        self._scoring_engine = scoring_engine

    def recommend(self, query):
        if not isinstance(query, RecommendationQueryDTO):
            raise TypeError("RecommendationService.recommend requiere RecommendationQueryDTO.")
        current_id = query.current_track.id
        scored = []
        for candidate in query.candidates:
            if candidate.id == current_id:
                continue
            score = self._scoring_engine.score(query.current_track, candidate)
            scored.append(score)
        ordered = sorted(scored, key=lambda item: (-item.score, -item.confidence, item.candidate_track_id))
        return tuple(
            RankedRecommendationDTO(index, item.candidate_track_id, item.score, item.confidence, item.reasons)
            for index, item in enumerate(ordered[:query.limit], start=1)
        )
