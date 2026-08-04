"""Bounded, deterministic ranking over batched lightweight library candidates."""

from __future__ import annotations

from dataclasses import dataclass
import heapq
import logging
from pathlib import Path
import time
from typing import Protocol, runtime_checkable

from .recommendation_service import RankedRecommendationDTO, RecommendationService


class GlobalRankingError(ValueError): pass
class InvalidRankingRequestError(GlobalRankingError): pass
class CandidateSourceError(GlobalRankingError): pass


@dataclass(frozen=True)
class RankingTrackDTO:
    track_id: int
    bpm: float | None = None
    key: str | None = None
    energy: float | None = None
    rating: int = 0
    genre: str | None = None
    favorite: bool = False
    duration: float | None = None
    filepath: str | None = None
    def __post_init__(self):
        if not isinstance(self.track_id, int) or self.track_id < 1: raise InvalidRankingRequestError("track_id invalido.")
    @property
    def id(self): return self.track_id


@dataclass(frozen=True)
class GlobalRankingRequestDTO:
    current_track: object
    limit: int = 10
    batch_size: int = 250
    bpm_min: float | None = None
    bpm_max: float | None = None
    key: str | None = None
    genre: str | None = None
    favorite: bool | None = None
    excluded_track_ids: tuple[int, ...] = ()
    cancellation: object | None = None
    require_existing_file: bool = False
    def __post_init__(self):
        if not isinstance(getattr(self.current_track, "id", None), int) or self.current_track.id < 1: raise InvalidRankingRequestError("Pista origen invalida.")
        if not isinstance(self.limit, int) or not 1 <= self.limit <= 100: raise InvalidRankingRequestError("K debe estar entre 1 y 100.")
        if not isinstance(self.batch_size, int) or not 1 <= self.batch_size <= 5000: raise InvalidRankingRequestError("batch_size debe estar entre 1 y 5000.")
        if self.bpm_min is not None and self.bpm_max is not None and self.bpm_min > self.bpm_max: raise InvalidRankingRequestError("Rango BPM invalido.")
        if not isinstance(self.excluded_track_ids, tuple) or not all(isinstance(item, int) and item > 0 for item in self.excluded_track_ids): raise InvalidRankingRequestError("Exclusiones invalidas.")
        if not isinstance(self.require_existing_file, bool): raise InvalidRankingRequestError("require_existing_file debe ser booleano.")
    def filters(self): return {name: value for name, value in {"bpm_min": self.bpm_min, "bpm_max": self.bpm_max, "key": self.key, "genre": self.genre, "favorite": self.favorite}.items() if value is not None}


@dataclass(frozen=True)
class GlobalRankingStatsDTO:
    processed: int
    discarded: int
    incomplete_metadata: int
    batches: int
    duration_ms: float
    algorithm_version: str = "global-ranking-v1"


@dataclass(frozen=True)
class GlobalRankingResultDTO:
    status: str
    recommendations: tuple[RankedRecommendationDTO, ...]
    stats: GlobalRankingStatsDTO
    errors: tuple[str, ...] = ()
    candidates: tuple[RankingTrackDTO, ...] = ()
    @property
    def cancelled(self): return self.status == "cancelled"


@runtime_checkable
class TrackCandidateSourceProtocol(Protocol):
    def iter_ranking_candidates(self, *, batch_size: int, filters: dict, excluded_track_ids: tuple[int, ...], cancellation=None): ...


class GlobalRankingService:
    """Top-K service. Memory is O(K + batch), never a whole candidate list."""
    def __init__(self, candidate_source, recommendation_service, logger=None):
        if not isinstance(candidate_source, TrackCandidateSourceProtocol): raise TypeError("GlobalRankingService requiere TrackCandidateSourceProtocol.")
        if not isinstance(recommendation_service, RecommendationService): raise TypeError("GlobalRankingService requiere RecommendationService.")
        self._source, self._recommendation_service = candidate_source, recommendation_service
        self._logger = logger or logging.getLogger("djplus.global_ranking")

    def rank(self, request, progress=None):
        if not isinstance(request, GlobalRankingRequestDTO): raise TypeError("rank requiere GlobalRankingRequestDTO.")
        started = time.perf_counter(); heap = []; processed = discarded = incomplete = batches = 0
        excluded = set(request.excluded_track_ids) | {request.current_track.id}
        self._event("global_ranking_started", limit=request.limit, batch_size=request.batch_size)
        iterator = iter(self._source.iter_ranking_candidates(
            batch_size=request.batch_size, filters=request.filters(),
            excluded_track_ids=tuple(sorted(excluded)), cancellation=request.cancellation,
        ))
        try:
            for batch in iterator:
                if self._cancelled(request.cancellation):
                    self._event("global_ranking_cancelled", processed=processed, batches=batches)
                    return self._result("cancelled", heap, processed, discarded, incomplete, batches, started)
                batches += 1
                for candidate in batch:
                    if self._cancelled(request.cancellation):
                        self._event("global_ranking_cancelled", processed=processed, batches=batches)
                        return self._result("cancelled", heap, processed, discarded, incomplete, batches, started)
                    if candidate.id in excluded: discarded += 1; continue
                    if request.require_existing_file and candidate.filepath and not Path(candidate.filepath).is_file():
                        discarded += 1; continue
                    processed += 1
                    if candidate.bpm is None or candidate.key is None or candidate.energy is None: incomplete += 1
                    score = self._recommendation_service._scoring_engine.score(request.current_track, candidate)
                    key = (score.score, score.confidence, -candidate.id)
                    item = (key, score, candidate)
                    if len(heap) < request.limit: heapq.heappush(heap, item)
                    elif key > heap[0][0]: heapq.heapreplace(heap, item)
                if callable(progress): progress(processed, batches, tuple(item[1].candidate_track_id for item in sorted(heap, reverse=True)))
        except Exception as error:
            if isinstance(error, GlobalRankingError): raise
            self._event("global_ranking_failed", exception_type=type(error).__name__, processed=processed, batches=batches)
            raise CandidateSourceError(type(error).__name__) from error
        finally:
            close = getattr(iterator, "close", None)
            if callable(close):
                close()
        result = self._result("completed", heap, processed, discarded, incomplete, batches, started)
        self._event("global_ranking_completed", processed=processed, batches=batches, returned=len(result.recommendations))
        return result

    @staticmethod
    def _cancelled(token): return bool(token is not None and callable(getattr(token, "is_cancelled", None)) and token.is_cancelled())
    def _result(self, status, heap, processed, discarded, incomplete, batches, started):
        ordered_items = sorted(heap, key=lambda item: (-item[1].score, -item[1].confidence, item[1].candidate_track_id))
        ordered = tuple(item[1] for item in ordered_items)
        candidates = tuple(item[2] for item in ordered_items)
        recommendations = tuple(RankedRecommendationDTO(index, item.candidate_track_id, item.score, item.confidence, item.reasons) for index, item in enumerate(ordered, 1)) if status == "completed" else ()
        return GlobalRankingResultDTO(status, recommendations, GlobalRankingStatsDTO(processed, discarded, incomplete, batches, (time.perf_counter() - started) * 1000), candidates=candidates if status == "completed" else ())

    def _event(self, name, **context):
        """Emit identifiers/counts only; titles, paths and ORM objects never reach logs."""
        self._logger.info(name, extra={"event_name": name, "component": "global_ranking", "context": context})
