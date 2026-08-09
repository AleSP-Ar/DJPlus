"""Read-only paged recommendation orchestration through application services."""

from dataclasses import dataclass
import time

from .recommendation_service import RecommendationQueryDTO, RecommendationService, RankedRecommendationDTO
from .optimization_metrics import OperationMetricsDTO, StageTimingDTO


class RecommendationFacadeError(ValueError):
    """Raised when a read-only recommendation query is invalid."""


@dataclass(frozen=True)
class RecommendationFacadeQueryDTO:
    current_track: object
    bpm_min: float | None = None
    bpm_max: float | None = None
    key: str | None = None
    genre: str | None = None
    favorite: bool | None = None
    limit: int = 10
    recent_history_limit: int = 20
    load_more: bool = False
    min_score: int = 45

    def __post_init__(self):
        track_id = getattr(self.current_track, "id", None)
        if not isinstance(track_id, int) or track_id < 1:
            raise RecommendationFacadeError("La pista actual debe tener id positivo.")
        for name in ("bpm_min", "bpm_max"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0):
                raise RecommendationFacadeError(f"{name} debe ser BPM positivo o nulo.")
        if self.bpm_min is not None and self.bpm_max is not None and self.bpm_min > self.bpm_max:
            raise RecommendationFacadeError("bpm_min no puede superar bpm_max.")
        if self.key is not None and (not isinstance(self.key, str) or not self.key.strip()):
            raise RecommendationFacadeError("key debe ser texto no vacio o nulo.")
        if self.genre is not None and (not isinstance(self.genre, str) or not self.genre.strip()):
            raise RecommendationFacadeError("genre debe ser texto no vacio o nulo.")
        if self.favorite is not None and not isinstance(self.favorite, bool):
            raise RecommendationFacadeError("favorite debe ser booleano o nulo.")
        if not isinstance(self.limit, int) or not 1 <= self.limit <= 100:
            raise RecommendationFacadeError("limit debe estar entre 1 y 100.")
        if not isinstance(self.recent_history_limit, int) or not 0 <= self.recent_history_limit <= 100:
            raise RecommendationFacadeError("recent_history_limit debe estar entre 0 y 100.")
        if not isinstance(self.load_more, bool):
            raise RecommendationFacadeError("load_more debe ser booleano.")
        if not isinstance(self.min_score, int) or not 1 <= self.min_score <= 100:
            raise RecommendationFacadeError("min_score debe estar entre 1 y 100.")

    def filters(self):
        return {name: value for name, value in {
            "bpm_min": self.bpm_min,
            "bpm_max": self.bpm_max,
            "key": self.key,
            "genre": self.genre,
            "favorite": self.favorite,
        }.items() if value is not None}


@dataclass(frozen=True)
class RecommendationPageDTO:
    recommendations: tuple[RankedRecommendationDTO, ...]
    candidate_total: int
    excluded_recent_track_ids: tuple[int, ...]
    has_more: bool
    page_number: int
    explanation: str

    def __post_init__(self):
        if not isinstance(self.recommendations, tuple) or not all(isinstance(item, RankedRecommendationDTO) for item in self.recommendations):
            raise RecommendationFacadeError("Las recomendaciones deben ser DTOs inmutables.")
        if not isinstance(self.candidate_total, int) or self.candidate_total < 0:
            raise RecommendationFacadeError("El total de candidatas debe ser entero no negativo.")
        if not isinstance(self.excluded_recent_track_ids, tuple) or not all(isinstance(value, int) and value > 0 for value in self.excluded_recent_track_ids):
            raise RecommendationFacadeError("Las exclusiones recientes deben ser ids positivos.")
        if not isinstance(self.has_more, bool) or not isinstance(self.page_number, int) or self.page_number < 1:
            raise RecommendationFacadeError("El estado de pagina no es valido.")
        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise RecommendationFacadeError("La explicacion de pagina es obligatoria.")


class RecommendationFacade:
    """Compose LibraryService, HistoryService and RecommendationService without writes."""

    def __init__(self, library_service, history_service, recommendation_service, global_ranking_service=None):
        if not callable(getattr(library_service, "query", None)) or not callable(getattr(library_service, "load_more", None)):
            raise TypeError("RecommendationFacade requiere LibraryService.")
        if not callable(getattr(library_service, "count_results", None)):
            raise TypeError("RecommendationFacade requiere conteo de LibraryService.")
        if not callable(getattr(history_service, "list_history", None)):
            raise TypeError("RecommendationFacade requiere HistoryService.")
        if not isinstance(recommendation_service, RecommendationService):
            raise TypeError("RecommendationFacade requiere RecommendationService.")
        self._library_service = library_service
        self._history_service = history_service
        self._recommendation_service = recommendation_service
        self._global_ranking_service = global_ranking_service
        self._last_query = None
        self._page_number = 0
        self._last_metrics = OperationMetricsDTO("recommendation_facade", ())
        self._last_stage_ms = {"library": 0.0, "history": 0.0, "ranking": 0.0}

    def recommend(self, query):
        started = time.perf_counter()
        self._last_stage_ms = {"library": 0.0, "history": 0.0, "ranking": 0.0}
        page = self._recommend(query)
        total_ms = (time.perf_counter() - started) * 1000
        self._last_metrics = OperationMetricsDTO("recommendation_facade", (
            StageTimingDTO("library", self._last_stage_ms["library"]),
            StageTimingDTO("history", self._last_stage_ms["history"]),
            StageTimingDTO("ranking", self._last_stage_ms["ranking"]),
            StageTimingDTO("total", total_ms),
        ))
        return page

    def _recommend(self, query):
        if not isinstance(query, RecommendationFacadeQueryDTO):
            raise TypeError("RecommendationFacade.recommend requiere RecommendationFacadeQueryDTO.")
        if self._global_ranking_service is not None and not query.load_more:
            return self._recommend_global(query)
        library_started = time.perf_counter()
        if query.load_more:
            if self._last_query is None:
                raise RecommendationFacadeError("No hay una consulta previa para cargar mas recomendaciones.")
            rows, has_more = self._library_service.load_more()
            active_query = self._last_query
            self._page_number += 1
        else:
            rows, has_more = self._library_service.query(text="", **query.filters())
            active_query = query
            self._last_query = query
            self._page_number = 1
        self._last_stage_ms["library"] = (time.perf_counter() - library_started) * 1000
        if not isinstance(rows, (tuple, list)) or not isinstance(has_more, bool):
            raise RecommendationFacadeError("LibraryService devolvio una pagina invalida.")
        total = self._library_service.count_results()
        if not isinstance(total, int) or total < 0:
            raise RecommendationFacadeError("LibraryService devolvio un total invalido.")
        history_started = time.perf_counter()
        recent_ids = self._recent_track_ids(active_query.recent_history_limit)
        self._last_stage_ms["history"] = (time.perf_counter() - history_started) * 1000
        current_id = active_query.current_track.id
        candidates = tuple(track for track in rows if getattr(track, "id", None) != current_id and getattr(track, "id", None) not in recent_ids)
        ranking_started = time.perf_counter()
        ranked = tuple(item for item in self._recommendation_service.recommend(RecommendationQueryDTO(active_query.current_track, candidates, active_query.limit)) if item.score >= active_query.min_score)
        self._last_stage_ms["ranking"] = (time.perf_counter() - ranking_started) * 1000
        explanation = self._explanation(active_query, total, len(recent_ids), len(ranked))
        return RecommendationPageDTO(ranked, total, tuple(sorted(recent_ids)), has_more, self._page_number, explanation)

    def _recommend_global(self, query):
        from .global_ranking_service import GlobalRankingRequestDTO
        history_started = time.perf_counter()
        recent_ids = self._recent_track_ids(query.recent_history_limit)
        self._last_stage_ms["history"] = (time.perf_counter() - history_started) * 1000
        ranking_started = time.perf_counter()
        result = self._global_ranking_service.rank(GlobalRankingRequestDTO(query.current_track, query.limit, min_score=query.min_score, excluded_track_ids=tuple(sorted(recent_ids)), **query.filters()))
        self._last_stage_ms["ranking"] = (time.perf_counter() - ranking_started) * 1000
        self._last_stage_ms["library"] = result.stats.duration_ms
        self._page_number = 1; self._last_query = query
        explanation = f"Alcance global; candidatas evaluadas: {result.stats.processed}; lotes: {result.stats.batches}; filtros: {', '.join(sorted(query.filters())) or 'sin filtros'}; recomendaciones: {len(result.recommendations)}."
        return RecommendationPageDTO(result.recommendations, result.stats.processed + result.stats.discarded, tuple(sorted(recent_ids)), False, 1, explanation)

    def _recent_track_ids(self, limit):
        if limit == 0:
            return set()
        events = self._history_service.list_history(event_type="played", limit=limit)
        if not isinstance(events, (tuple, list)):
            raise RecommendationFacadeError("HistoryService devolvio historial invalido.")
        ids = set()
        for event in events:
            track_id = event.get("track_id") if isinstance(event, dict) else getattr(event, "track_id", None)
            if isinstance(track_id, int) and track_id > 0:
                ids.add(track_id)
        return ids

    def _explanation(self, query, total, excluded, returned):
        filters = query.filters()
        criteria = ", ".join(f"{name}={value}" for name, value in sorted(filters.items())) or "sin filtros"
        return f"Candidatas: {total}; filtros: {criteria}; excluidas por historial: {excluded}; recomendaciones en pagina: {returned}."
