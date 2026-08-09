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
            if self._is_recommendable(score):
                scored.append((score, candidate))
        ordered = sorted(scored, key=lambda item: self._priority_key(item[0], item[1], query.current_track))
        return tuple(
            RankedRecommendationDTO(index, item[0].candidate_track_id, item[0].score, item[0].confidence, item[0].reasons)
            for index, item in enumerate(ordered[:query.limit], start=1)
        )

    @staticmethod
    def _is_recommendable(score):
        return score.score > 0 and RecommendationService._has_musical_match(score)

    @staticmethod
    def _has_musical_match(score):
        """Reject candidates with no genre, harmonic, or tempo connection."""
        return any(
            (
                reason.criterion == "genre"
                and reason.contribution >= 21
                and "no disponible" not in reason.explanation.casefold()
            )
            or (reason.criterion == "key" and reason.contribution > 0)
            or (reason.criterion == "bpm" and reason.contribution > 0)
            for reason in score.reasons
        )

    @staticmethod
    def _priority_key(score, candidate, reference):
        reasons = {reason.criterion: reason.contribution for reason in score.reasons}
        label_match = RecommendationService._same_text(getattr(reference, "label", None), getattr(candidate, "label", None))
        artist_match = RecommendationService._same_text(getattr(reference, "artist", None), getattr(candidate, "artist", None))
        return (-reasons.get("genre", 0), -reasons.get("key", 0), -reasons.get("bpm", 0), -int(label_match), -int(artist_match), -score.score, -score.confidence, score.candidate_track_id)

    @staticmethod
    def _same_text(left, right):
        return isinstance(left, str) and isinstance(right, str) and bool(left.strip()) and left.strip().casefold() == right.strip().casefold()
