"""Read-only batch orchestration from LibraryService to local WAV analysis."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
import logging
from threading import Event, Lock, Thread

from .audio_analysis_service import AudioAnalysisError, AudioAnalysisQueryDTO, AudioFileMusicAnalysisService

_LOGGER = logging.getLogger("djplus.analysis")


class MusicAnalysisBatchError(ValueError):
    """Raised for invalid read-only batch analysis contracts."""


@dataclass(frozen=True)
class MusicAnalysisBatchQueryDTO:
    track_ids: tuple[int, ...] = ()
    limit: int = 20
    max_concurrency: int = 1
    cancellation_token: object | None = None

    def __post_init__(self):
        if not isinstance(self.track_ids, tuple) or not all(isinstance(item, int) and item > 0 for item in self.track_ids):
            raise MusicAnalysisBatchError("track_ids debe ser una tupla de ids positivos.")
        if len(set(self.track_ids)) != len(self.track_ids):
            raise MusicAnalysisBatchError("track_ids no puede contener duplicados.")
        if not isinstance(self.limit, int) or not 1 <= self.limit <= 100:
            raise MusicAnalysisBatchError("limit debe estar entre 1 y 100.")
        if not isinstance(self.max_concurrency, int) or not 1 <= self.max_concurrency <= 4:
            raise MusicAnalysisBatchError("max_concurrency debe estar entre 1 y 4.")
        if self.cancellation_token is not None and not callable(getattr(self.cancellation_token, "is_cancelled", None)):
            raise MusicAnalysisBatchError("El token de cancelacion debe exponer is_cancelled().")


@dataclass(frozen=True)
class MusicAnalysisItemResultDTO:
    track_id: int
    filepath: str | None
    status: str
    duration_seconds: float | None = None
    peak: float | None = None
    rms: float | None = None
    energy: float | None = None
    bpm: float | None = None
    key: str | None = None
    tempo_confidence: float | None = None
    key_confidence: float | None = None
    error: str | None = None

    def __post_init__(self):
        if not isinstance(self.track_id, int) or self.track_id < 1:
            raise MusicAnalysisBatchError("Cada resultado requiere track_id positivo.")
        if self.filepath is not None and (not isinstance(self.filepath, str) or not self.filepath.strip()):
            raise MusicAnalysisBatchError("filepath debe ser texto no vacio o nulo.")
        if self.status not in {"completed", "error", "cancelled"}:
            raise MusicAnalysisBatchError("El estado por archivo no es valido.")
        if self.status == "completed" and self.error is not None:
            raise MusicAnalysisBatchError("Un analisis completado no contiene error.")
        if self.status == "error" and not self.error:
            raise MusicAnalysisBatchError("Un error por archivo requiere explicacion.")


@dataclass(frozen=True)
class MusicAnalysisBatchResultDTO:
    query: MusicAnalysisBatchQueryDTO
    items: tuple[MusicAnalysisItemResultDTO, ...]
    cancelled: bool
    explanation: str

    def __post_init__(self):
        if not isinstance(self.query, MusicAnalysisBatchQueryDTO):
            raise MusicAnalysisBatchError("El resultado requiere la consulta original.")
        if not isinstance(self.items, tuple) or not all(isinstance(item, MusicAnalysisItemResultDTO) for item in self.items):
            raise MusicAnalysisBatchError("Los resultados del lote no son validos.")
        if not isinstance(self.cancelled, bool) or not isinstance(self.explanation, str) or not self.explanation.strip():
            raise MusicAnalysisBatchError("El resumen de lote no es valido.")

    def export_text(self):
        lines = [self.explanation]
        for item in self.items:
            values = f"duracion={item.duration_seconds}; peak={item.peak}; rms={item.rms}; energia={item.energy}; bpm={item.bpm}; key={item.key}; confianza_tempo={item.tempo_confidence}; confianza_key={item.key_confidence}"
            lines.append(f"pista={item.track_id}; estado={item.status}; {values}" + (f"; error={item.error}" if item.error else ""))
        return "\n".join(lines)


class MusicAnalysisFacade:
    """Read tracks through LibraryService, analyze files locally, and retain nothing."""

    def __init__(self, library_service, music_analysis_service=None):
        if not callable(getattr(library_service, "query", None)):
            raise TypeError("MusicAnalysisFacade requiere LibraryService.")
        self._library_service = library_service
        self._music_analysis_service = music_analysis_service or AudioFileMusicAnalysisService()
        if not isinstance(self._music_analysis_service, AudioFileMusicAnalysisService):
            raise TypeError("MusicAnalysisFacade requiere AudioFileMusicAnalysisService.")

    def analyze(self, query, on_progress=None):
        if not isinstance(query, MusicAnalysisBatchQueryDTO):
            raise TypeError("MusicAnalysisFacade.analyze requiere MusicAnalysisBatchQueryDTO.")
        if on_progress is not None and not callable(on_progress):
            raise TypeError("on_progress debe ser invocable o nulo.")
        rows, _has_more = self._library_service.query(text="")
        if not isinstance(rows, (tuple, list)):
            raise MusicAnalysisBatchError("LibraryService devolvio pistas invalidas.")
        selected = tuple(track for track in rows if not query.track_ids or getattr(track, "id", None) in query.track_ids)[:query.limit]
        results = []
        if query.max_concurrency == 1:
            for track in selected:
                results.append(self._analyze_track(track, query))
                self._progress(on_progress, len(results), len(selected), results[-1])
                if self._cancelled(query):
                    break
        else:
            with ThreadPoolExecutor(max_workers=query.max_concurrency) as executor:
                futures = [executor.submit(self._analyze_track, track, query) for track in selected]
                for future in as_completed(futures):
                    results.append(future.result())
                    self._progress(on_progress, len(results), len(selected), results[-1])
                    if self._cancelled(query):
                        break
        results.sort(key=lambda item: item.track_id)
        cancelled = self._cancelled(query)
        return MusicAnalysisBatchResultDTO(query, tuple(results), cancelled, f"Analisis local read-only: {len(results)} de {len(selected)} archivos procesados; errores: {sum(item.status == 'error' for item in results)}.")

    def _analyze_track(self, track, query):
        track_id, filepath = getattr(track, "id", None), getattr(track, "filepath", None)
        if not isinstance(track_id, int) or track_id < 1:
            raise MusicAnalysisBatchError("LibraryService devolvio una pista sin id positivo.")
        if self._cancelled(query):
            return MusicAnalysisItemResultDTO(track_id, filepath, "cancelled")
        if not isinstance(filepath, str) or not filepath.strip():
            return MusicAnalysisItemResultDTO(track_id, None, "error", error="La pista no tiene una ruta de archivo valida.")
        try:
            result = self._music_analysis_service.analyze(AudioAnalysisQueryDTO(filepath, query.cancellation_token))
        except (AudioAnalysisError, OSError, ValueError) as error:
            return MusicAnalysisItemResultDTO(track_id, filepath, "error", error=str(error))
        if result.status == "cancelled":
            return MusicAnalysisItemResultDTO(track_id, filepath, "cancelled")
        features = result.features
        return MusicAnalysisItemResultDTO(track_id, filepath, "completed", features.duration_seconds, features.peak, result.energy_analysis.rms, features.energy, features.bpm, features.key, result.tempo_analysis.confidence, result.key_analysis.confidence)

    @staticmethod
    def _cancelled(query):
        return query.cancellation_token is not None and query.cancellation_token.is_cancelled()

    @staticmethod
    def _progress(callback, completed, total, item):
        if callback is not None:
            callback(completed, total, item)


class MusicAnalysisWorker:
    """UI-independent cooperative batch worker with bounded facade concurrency."""

    def __init__(self, facade, max_concurrency=1):
        if not isinstance(facade, MusicAnalysisFacade):
            raise TypeError("MusicAnalysisWorker requiere MusicAnalysisFacade.")
        if not isinstance(max_concurrency, int) or not 1 <= max_concurrency <= 4:
            raise ValueError("max_concurrency debe estar entre 1 y 4.")
        self._facade, self._max_concurrency = facade, max_concurrency
        self._cancel, self._finished, self._lock = Event(), Event(), Lock()
        self._callbacks, self._thread, self.result, self.error = [], None, None, None

    def subscribe(self, callback):
        if not callable(callback):
            raise TypeError("El callback debe ser invocable.")
        self._callbacks.append(callback)

    def start(self, query):
        if not isinstance(query, MusicAnalysisBatchQueryDTO):
            raise TypeError("MusicAnalysisWorker.start requiere MusicAnalysisBatchQueryDTO.")
        with self._lock:
            if self.is_running:
                raise RuntimeError("Ya hay un analisis musical en ejecucion.")
            self._cancel.clear(); self._finished.clear(); self.result = self.error = None
            effective = replace(query, max_concurrency=self._max_concurrency, cancellation_token=self)
            self._thread = Thread(target=self._run, args=(effective,), daemon=True)
            self._thread.start()
            return self._thread

    def is_cancelled(self):
        return self._cancel.is_set()

    def cancel(self):
        self._cancel.set()

    def close(self, timeout=None):
        self.cancel(); self._finished.wait(timeout)
        return not self.is_running

    def wait(self, timeout=None):
        self._finished.wait(timeout)
        return self.result

    @property
    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def _run(self, query):
        try:
            self.result = self._facade.analyze(query, self._emit_progress)
        except Exception as error:
            self.error = error
            _LOGGER.error("Music analysis worker failed", exc_info=True, extra={"event_name": "analysis_worker_error", "component": "analysis", "exception_type": type(error).__name__})
            self._emit("error", str(error))
        finally:
            self._finished.set()
            self._emit("finished", self.result)

    def _emit_progress(self, completed, total, item):
        self._emit("progress", completed, total, item)

    def _emit(self, *event):
        for callback in tuple(self._callbacks):
            callback(*event)
