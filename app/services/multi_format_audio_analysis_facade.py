"""Read-only batch analysis with optional FFmpeg-backed MP3/FLAC decoding."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import logging

from .audio_analysis_service import AudioAnalysisError, AudioAnalysisQueryDTO, MusicAnalysisService
from .audio_decoder import AudioDecoderError, AudioDecoderRegistry, OFFICIAL_AUDIO_FORMAT_ORDER
from .ffmpeg_audio_decoder import FFmpegAudioDecoder, FFmpegAvailabilityDTO, FFmpegDecoderConfigDTO
from .music_analysis_facade import MusicAnalysisBatchError, MusicAnalysisBatchQueryDTO, MusicAnalysisFacade

_LOGGER = logging.getLogger("djplus.analysis")


@dataclass(frozen=True)
class MultiFormatAudioDiagnosticsDTO:
    format_order: tuple[str, ...]
    decoder_names: tuple[str, ...]
    supported_extensions: tuple[str, ...]
    ffmpeg_availability: FFmpegAvailabilityDTO | None
    analyzer_version: str

    def __post_init__(self):
        if self.format_order != OFFICIAL_AUDIO_FORMAT_ORDER:
            raise MusicAnalysisBatchError("El orden oficial de formatos no es valido.")
        if not isinstance(self.decoder_names, tuple) or not all(isinstance(item, str) for item in self.decoder_names):
            raise MusicAnalysisBatchError("Los decodificadores diagnosticados no son validos.")
        if not isinstance(self.supported_extensions, tuple) or not all(isinstance(item, str) for item in self.supported_extensions):
            raise MusicAnalysisBatchError("Las extensiones diagnosticadas no son validas.")
        if self.ffmpeg_availability is not None and not isinstance(self.ffmpeg_availability, FFmpegAvailabilityDTO):
            raise MusicAnalysisBatchError("La disponibilidad de FFmpeg no es valida.")
        if not isinstance(self.analyzer_version, str) or not self.analyzer_version.strip():
            raise MusicAnalysisBatchError("La version del analizador es obligatoria.")


@dataclass(frozen=True)
class MultiFormatAudioAnalysisItemDTO:
    track_id: int
    filepath: str | None
    status: str
    audio_format: str | None
    decoder: str | None
    analyzer_version: str
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
            raise MusicAnalysisBatchError("Cada resultado multiformato requiere track_id positivo.")
        if self.filepath is not None and (not isinstance(self.filepath, str) or not self.filepath.strip()):
            raise MusicAnalysisBatchError("filepath debe ser texto no vacio o nulo.")
        if self.status not in {"completed", "error", "cancelled"}:
            raise MusicAnalysisBatchError("El estado multiformato no es valido.")
        if self.audio_format is not None and not isinstance(self.audio_format, str):
            raise MusicAnalysisBatchError("El formato debe ser texto o nulo.")
        if self.decoder is not None and not isinstance(self.decoder, str):
            raise MusicAnalysisBatchError("El decoder debe ser texto o nulo.")
        if not isinstance(self.analyzer_version, str) or not self.analyzer_version.strip():
            raise MusicAnalysisBatchError("La version del analizador es obligatoria.")
        if self.status == "completed" and (self.audio_format is None or self.decoder is None or self.error is not None):
            raise MusicAnalysisBatchError("Un resultado completo requiere formato, decoder y ningun error.")
        if self.status == "error" and not self.error:
            raise MusicAnalysisBatchError("Un resultado con error requiere una explicacion segura.")


@dataclass(frozen=True)
class MultiFormatAudioAnalysisResultDTO:
    query: MusicAnalysisBatchQueryDTO
    items: tuple[MultiFormatAudioAnalysisItemDTO, ...]
    cancelled: bool
    diagnostics: MultiFormatAudioDiagnosticsDTO
    explanation: str

    def __post_init__(self):
        if not isinstance(self.query, MusicAnalysisBatchQueryDTO):
            raise MusicAnalysisBatchError("El resultado multiformato requiere la consulta original.")
        if not isinstance(self.items, tuple) or not all(isinstance(item, MultiFormatAudioAnalysisItemDTO) for item in self.items):
            raise MusicAnalysisBatchError("Los items multiformato no son validos.")
        if not isinstance(self.cancelled, bool) or not isinstance(self.diagnostics, MultiFormatAudioDiagnosticsDTO):
            raise MusicAnalysisBatchError("El estado multiformato no es valido.")
        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise MusicAnalysisBatchError("El resumen multiformato es obligatorio.")

    def export_text(self):
        ffmpeg = self.diagnostics.ffmpeg_availability
        lines = [
            self.explanation,
            f"format_order={self.diagnostics.format_order}; analyzer_version={self.diagnostics.analyzer_version}; decoders={self.diagnostics.decoder_names}; extensions={self.diagnostics.supported_extensions}; ffmpeg_available={ffmpeg.available if ffmpeg else False}; ffmpeg_origin={ffmpeg.origin if ffmpeg else 'unavailable'}; ffmpeg_checksum_verified={ffmpeg.checksum_verified if ffmpeg else None}; ffmpeg_version={ffmpeg.version if ffmpeg else None}; ffmpeg_mp3={ffmpeg.supports_mp3 if ffmpeg else False}; ffmpeg_flac={ffmpeg.supports_flac if ffmpeg else False}",
        ]
        for item in self.items:
            values = f"format={item.audio_format}; decoder={item.decoder}; analyzer_version={item.analyzer_version}; duracion={item.duration_seconds}; peak={item.peak}; rms={item.rms}; energia={item.energy}; bpm={item.bpm}; key={item.key}; confianza_tempo={item.tempo_confidence}; confianza_key={item.key_confidence}"
            lines.append(f"pista={item.track_id}; estado={item.status}; {values}" + (f"; error={item.error}" if item.error else ""))
        return "\n".join(lines)


class MultiFormatAudioAnalysisFacade(MusicAnalysisFacade):
    """LibraryService batch boundary with WAV/AIFF and optional FFmpeg formats."""

    DEFAULT_ANALYZER_VERSION = "multiformat-pcm-1"

    def __init__(self, library_service, decoder_registry=None, ffmpeg_config=None, analyzer_version=DEFAULT_ANALYZER_VERSION):
        if decoder_registry is not None and ffmpeg_config is not None:
            raise TypeError("No se puede inyectar registry y configuracion FFmpeg a la vez.")
        if not isinstance(analyzer_version, str) or not analyzer_version.strip():
            raise ValueError("analyzer_version es obligatoria.")
        if decoder_registry is None:
            config = ffmpeg_config or FFmpegDecoderConfigDTO()
            if not isinstance(config, FFmpegDecoderConfigDTO):
                raise TypeError("ffmpeg_config requiere FFmpegDecoderConfigDTO.")
            self._ffmpeg_decoder = FFmpegAudioDecoder(config)
            decoder_registry = AudioDecoderRegistry.default(ffmpeg_decoder=self._ffmpeg_decoder)
        else:
            if not isinstance(decoder_registry, AudioDecoderRegistry):
                raise TypeError("decoder_registry requiere AudioDecoderRegistry.")
            candidate = decoder_registry.optional_decoder("ffmpeg")
            self._ffmpeg_decoder = candidate if isinstance(candidate, FFmpegAudioDecoder) else None
        self._decoder_registry = decoder_registry
        self._analyzer_version = analyzer_version
        super().__init__(library_service, MusicAnalysisService(decoder_registry=decoder_registry))

    def diagnostics(self):
        return MultiFormatAudioDiagnosticsDTO(
            OFFICIAL_AUDIO_FORMAT_ORDER,
            self._decoder_registry.registered_decoder_names(),
            self._decoder_registry.supported_extensions(),
            self._ffmpeg_decoder.availability() if self._ffmpeg_decoder is not None else None,
            self._analyzer_version,
        )

    def analyze(self, query, on_progress=None):
        if not isinstance(query, MusicAnalysisBatchQueryDTO):
            raise TypeError("MultiFormatAudioAnalysisFacade.analyze requiere MusicAnalysisBatchQueryDTO.")
        if on_progress is not None and not callable(on_progress):
            raise TypeError("on_progress debe ser invocable o nulo.")
        rows, _has_more = self._library_service.query(text="")
        if not isinstance(rows, (tuple, list)):
            raise MusicAnalysisBatchError("LibraryService devolvio pistas invalidas.")
        selected = tuple(track for track in rows if not query.track_ids or getattr(track, "id", None) in query.track_ids)[:query.limit]
        results = []
        if query.max_concurrency == 1:
            for track in selected:
                results.append(self._analyze_multi_format_track(track, query))
                self._progress(on_progress, len(results), len(selected), results[-1])
                if self._cancelled(query):
                    break
        else:
            with ThreadPoolExecutor(max_workers=query.max_concurrency) as executor:
                futures = [executor.submit(self._analyze_multi_format_track, track, query) for track in selected]
                for future in as_completed(futures):
                    results.append(future.result())
                    self._progress(on_progress, len(results), len(selected), results[-1])
                    if self._cancelled(query):
                        break
        results.sort(key=lambda item: item.track_id)
        cancelled = self._cancelled(query)
        return MultiFormatAudioAnalysisResultDTO(
            query, tuple(results), cancelled, self.diagnostics(),
            f"Analisis multiformato read-only: {len(results)} de {len(selected)} archivos procesados; errores: {sum(item.status == 'error' for item in results)}.",
        )

    def _analyze_multi_format_track(self, track, query):
        track_id, filepath = getattr(track, "id", None), getattr(track, "filepath", None)
        if not isinstance(track_id, int) or track_id < 1:
            raise MusicAnalysisBatchError("LibraryService devolvio una pista sin id positivo.")
        if self._cancelled(query):
            return MultiFormatAudioAnalysisItemDTO(track_id, filepath, "cancelled", None, None, self._analyzer_version)
        if not isinstance(filepath, str) or not filepath.strip():
            return MultiFormatAudioAnalysisItemDTO(track_id, None, "error", None, None, self._analyzer_version, error="La pista no tiene una ruta de archivo valida.")
        audio_format = decoder_name = None
        try:
            decoder = self._decoder_registry.detect(filepath)
            decoder_name = decoder.audio_format.name
            info = decoder.probe(filepath)
            audio_format = info.audio_format.name
            result = self._music_analysis_service.analyze(AudioAnalysisQueryDTO(filepath, query.cancellation_token))
        except (AudioAnalysisError, AudioDecoderError, OSError, ValueError) as error:
            _LOGGER.warning("Multiformat analysis failed", extra={"event_name": "analysis_error", "component": "analysis", "context": {"track_id": track_id, "decoder": decoder_name, "exception_type": type(error).__name__}})
            return MultiFormatAudioAnalysisItemDTO(track_id, filepath, "error", audio_format, decoder_name, self._analyzer_version, error=str(error))
        if result.status == "cancelled":
            return MultiFormatAudioAnalysisItemDTO(track_id, filepath, "cancelled", audio_format, decoder_name, self._analyzer_version)
        features = result.features
        return MultiFormatAudioAnalysisItemDTO(
            track_id, filepath, "completed", audio_format, decoder_name, self._analyzer_version,
            features.duration_seconds, features.peak, result.energy_analysis.rms, features.energy,
            features.bpm, features.key, result.tempo_analysis.confidence, result.key_analysis.confidence,
        )
