"""Deterministic local PCM/WAV inspection with no persistence dependency."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable
from statistics import median, fmean, pstdev
import math
import wave


class AudioAnalysisError(ValueError):
    """Raised when an audio file cannot be safely analyzed."""


@dataclass(frozen=True)
class AudioAnalysisQueryDTO:
    filepath: str
    cancellation_token: object | None = None

    def __post_init__(self):
        if not isinstance(self.filepath, str) or not self.filepath.strip():
            raise AudioAnalysisError("La ruta de audio es obligatoria.")
        if Path(self.filepath).suffix.casefold() != ".wav":
            raise AudioAnalysisError("Solo se admite WAV PCM en el analisis local actual.")
        if self.cancellation_token is not None and not callable(getattr(self.cancellation_token, "is_cancelled", None)):
            raise AudioAnalysisError("El token de cancelacion debe exponer is_cancelled().")


@dataclass(frozen=True)
class AudioFeaturesDTO:
    duration_seconds: float | None
    sample_rate: int | None
    channels: int | None
    peak: float | None
    bpm: float | None = None
    key: str | None = None
    energy: float | None = None

    def __post_init__(self):
        if self.duration_seconds is not None and (not isinstance(self.duration_seconds, (int, float)) or self.duration_seconds < 0):
            raise AudioAnalysisError("La duracion debe ser no negativa o nula.")
        if self.sample_rate is not None and (not isinstance(self.sample_rate, int) or self.sample_rate < 1):
            raise AudioAnalysisError("El sample rate debe ser positivo o nulo.")
        if self.channels is not None and (not isinstance(self.channels, int) or self.channels < 1):
            raise AudioAnalysisError("Los canales deben ser positivos o nulos.")
        if self.peak is not None and (not isinstance(self.peak, (int, float)) or not 0 <= self.peak <= 1):
            raise AudioAnalysisError("El peak debe estar entre 0 y 1 o ser nulo.")
        if self.bpm is not None and (not isinstance(self.bpm, (int, float)) or self.bpm <= 0):
            raise AudioAnalysisError("El BPM debe ser positivo o nulo.")
        if self.key is not None and (not isinstance(self.key, str) or not self.key.strip()):
            raise AudioAnalysisError("La key debe ser texto no vacio o nula.")
        if self.energy is not None and (not isinstance(self.energy, (int, float)) or not 0 <= self.energy <= 100):
            raise AudioAnalysisError("La energia debe estar entre 0 y 100 o ser nula.")


@dataclass(frozen=True)
class EnergyAnalysisDTO:
    rms: float
    normalized_energy: float
    confidence: float
    explanation: str

    def __post_init__(self):
        for value in (self.rms, self.confidence):
            if not isinstance(value, (int, float)) or not 0 <= value <= 1:
                raise AudioAnalysisError("RMS y confianza deben estar entre 0 y 1.")
        if not isinstance(self.normalized_energy, (int, float)) or not 0 <= self.normalized_energy <= 100:
            raise AudioAnalysisError("La energia normalizada debe estar entre 0 y 100.")
        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise AudioAnalysisError("La explicacion de energia es obligatoria.")


@dataclass(frozen=True)
class TempoAnalysisDTO:
    bpm: float | None
    confidence: float
    explanation: str

    def __post_init__(self):
        if self.bpm is not None and (not isinstance(self.bpm, (int, float)) or not 40 <= self.bpm <= 240):
            raise AudioAnalysisError("El BPM debe estar entre 40 y 240 o ser nulo.")
        if not isinstance(self.confidence, (int, float)) or not 0 <= self.confidence <= 1:
            raise AudioAnalysisError("La confianza de tempo debe estar entre 0 y 1.")
        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise AudioAnalysisError("La explicacion de tempo es obligatoria.")


@dataclass(frozen=True)
class ChromaAnalysisDTO:
    """Normalized 12 pitch-class profile in chromatic C-to-B order."""

    profile: tuple[float, ...]
    confidence: float
    explanation: str

    def __post_init__(self):
        if not isinstance(self.profile, tuple) or len(self.profile) != 12:
            raise AudioAnalysisError("El perfil cromatico debe contener 12 notas.")
        if any(not isinstance(value, (int, float)) or value < 0 or value > 1 for value in self.profile):
            raise AudioAnalysisError("El perfil cromatico debe estar normalizado entre 0 y 1.")
        if not isinstance(self.confidence, (int, float)) or not 0 <= self.confidence <= 1:
            raise AudioAnalysisError("La confianza cromatica debe estar entre 0 y 1.")
        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise AudioAnalysisError("La explicacion cromatica es obligatoria.")


@dataclass(frozen=True)
class KeyAnalysisDTO:
    key: str | None
    root: str | None
    mode: str | None
    confidence: float
    explanation: str

    def __post_init__(self):
        valid_roots = {"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"}
        if self.root is not None and self.root not in valid_roots:
            raise AudioAnalysisError("La raiz musical no esta normalizada.")
        if self.mode is not None and self.mode not in {"major", "minor"}:
            raise AudioAnalysisError("El modo debe ser major, minor o nulo.")
        expected = f"{self.root} {self.mode}" if self.root and self.mode else None
        if self.key != expected:
            raise AudioAnalysisError("La tonalidad debe coincidir con raiz y modo normalizados.")
        if not isinstance(self.confidence, (int, float)) or not 0 <= self.confidence <= 1:
            raise AudioAnalysisError("La confianza tonal debe estar entre 0 y 1.")
        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise AudioAnalysisError("La explicacion tonal es obligatoria.")


@dataclass(frozen=True)
class AudioAnalysisResultDTO:
    query: AudioAnalysisQueryDTO
    status: str
    features: AudioFeaturesDTO | None
    explanation: str
    energy_analysis: EnergyAnalysisDTO | None = None
    tempo_analysis: TempoAnalysisDTO | None = None
    chroma_analysis: ChromaAnalysisDTO | None = None
    key_analysis: KeyAnalysisDTO | None = None

    def __post_init__(self):
        if not isinstance(self.query, AudioAnalysisQueryDTO):
            raise AudioAnalysisError("El resultado requiere la consulta original.")
        if self.status not in {"completed", "cancelled"}:
            raise AudioAnalysisError("El estado de analisis no es valido.")
        if self.status == "completed" and not isinstance(self.features, AudioFeaturesDTO):
            raise AudioAnalysisError("Un analisis completado requiere features.")
        if self.status == "cancelled" and self.features is not None:
            raise AudioAnalysisError("Un analisis cancelado no entrega features parciales.")
        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise AudioAnalysisError("La explicacion de analisis es obligatoria.")
        if self.energy_analysis is not None and not isinstance(self.energy_analysis, EnergyAnalysisDTO):
            raise AudioAnalysisError("El resultado de energia no es valido.")
        if self.tempo_analysis is not None and not isinstance(self.tempo_analysis, TempoAnalysisDTO):
            raise AudioAnalysisError("El resultado de tempo no es valido.")
        if self.chroma_analysis is not None and not isinstance(self.chroma_analysis, ChromaAnalysisDTO):
            raise AudioAnalysisError("El resultado cromatico no es valido.")
        if self.key_analysis is not None and not isinstance(self.key_analysis, KeyAnalysisDTO):
            raise AudioAnalysisError("El resultado tonal no es valido.")


@runtime_checkable
class AudioAnalyzerProtocol(Protocol):
    """Replaceable local analyzer boundary for future BPM/key/energy support."""

    def analyze(self, query: AudioAnalysisQueryDTO) -> AudioAnalysisResultDTO:
        ...


@runtime_checkable
class AudioFeatureExtractorProtocol(Protocol):
    """Extract optional PCM features while WaveAudioAnalyzer owns file access."""

    def extract(self, source, query: AudioAnalysisQueryDTO):
        ...


class PCMFeatureExtractor:
    """Block-based RMS and envelope peak estimator for mono or stereo PCM."""

    block_frames = 1024

    def extract(self, source, query):
        sample_width, channels, sample_rate = source.getsampwidth(), source.getnchannels(), source.getframerate()
        if sample_width not in {1, 2, 3, 4}:
            raise AudioAnalysisError("El ancho de muestra WAV no es compatible.")
        envelope, square_sum, sample_count, peak = [], 0.0, 0, 0.0
        while True:
            if query.cancellation_token is not None and query.cancellation_token.is_cancelled():
                return None
            raw = source.readframes(self.block_frames)
            if not raw:
                break
            values = self._mono_values(raw, sample_width, channels)
            if not values:
                continue
            block_square_sum = sum(value * value for value in values)
            envelope.append(math.sqrt(block_square_sum / len(values)))
            square_sum += block_square_sum
            sample_count += len(values)
            peak = max(peak, self._peak(raw, sample_width))
        rms = math.sqrt(square_sum / sample_count) if sample_count else 0.0
        energy = EnergyAnalysisDTO(round(rms, 6), round(rms * 100, 3), 1.0 if sample_count else 0.0, "Energia normalizada calculada mediante RMS PCM por bloques.")
        tempo = self._tempo(envelope, sample_rate)
        return peak, energy, tempo

    @staticmethod
    def _mono_values(raw, sample_width, channels):
        if sample_width == 1:
            samples = [(value - 128) / 128 for value in raw]
        else:
            maximum = float((1 << (sample_width * 8 - 1)) - 1)
            samples = [int.from_bytes(raw[index:index + sample_width], "little", signed=True) / maximum for index in range(0, len(raw), sample_width)]
        return tuple(sum(samples[index:index + channels]) / channels for index in range(0, len(samples), channels) if len(samples[index:index + channels]) == channels)

    @staticmethod
    def _peak(raw, sample_width):
        if sample_width == 1:
            return max((abs(value - 128) / 128 for value in raw), default=0.0)
        maximum = float((1 << (sample_width * 8 - 1)) - 1)
        values = (int.from_bytes(raw[index:index + sample_width], "little", signed=True) for index in range(0, len(raw), sample_width))
        return max((min(1.0, abs(value) / maximum) for value in values), default=0.0)

    def _tempo(self, envelope, sample_rate):
        duration = len(envelope) * self.block_frames / sample_rate
        if duration < 3 or not envelope:
            return TempoAnalysisDTO(None, 0.0, "Audio demasiado corto para estimar BPM con confianza.")
        highest = max(envelope)
        if highest < 0.01:
            return TempoAnalysisDTO(None, 0.0, "Audio silencioso: no hay envolvente suficiente para BPM.")
        threshold = fmean(envelope) + max(0.002, pstdev(envelope) * 0.5)
        gap = max(1, int(0.25 * sample_rate / self.block_frames))
        peaks = []
        for index in range(1, len(envelope) - 1):
            if envelope[index] >= threshold and envelope[index] >= envelope[index - 1] and envelope[index] >= envelope[index + 1] and (not peaks or index - peaks[-1] >= gap):
                peaks.append(index)
        intervals = [(second - first) * self.block_frames / sample_rate for first, second in zip(peaks, peaks[1:])]
        intervals = [value for value in intervals if 60 / 240 <= value <= 60 / 40]
        if len(intervals) < 2:
            return TempoAnalysisDTO(None, 0.0, "No hubo suficientes picos de envolvente para estimar BPM.")
        period = median(intervals)
        bpm = 60 / period
        variation = median(abs(value - period) for value in intervals) / period if period else 1.0
        confidence = round(min(1.0, len(intervals) / 4) * max(0.0, 1 - variation * 4), 2)
        if confidence < 0.55:
            return TempoAnalysisDTO(None, confidence, "La envolvente produce una confianza insuficiente para publicar BPM.")
        return TempoAnalysisDTO(round(bpm, 2), confidence, f"BPM estimado por picos de envolvente ({len(intervals)} intervalos).")


class PCMKeyAnalyzer:
    """Deterministic block PCM chroma extractor and major/minor template matcher."""

    block_frames = 1024
    _NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
    _MAJOR = (6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88)
    _MINOR = (6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17)

    def analyze(self, source, query):
        width, channels, rate, frame_count = source.getsampwidth(), source.getnchannels(), source.getframerate(), source.getnframes()
        if width not in {1, 2, 3, 4}:
            raise AudioAnalysisError("El ancho de muestra WAV no es compatible.")
        if frame_count / rate < 2:
            return self._empty("Audio demasiado corto para estimar tonalidad con confianza.")
        chroma = [0.0] * 12
        blocks = 0
        while True:
            if query.cancellation_token is not None and query.cancellation_token.is_cancelled():
                return None
            raw = source.readframes(self.block_frames)
            if not raw:
                break
            values = PCMFeatureExtractor._mono_values(raw, width, channels)
            if len(values) < 32:
                continue
            blocks += 1
            for midi in range(36, 97):
                frequency = 440.0 * (2 ** ((midi - 69) / 12))
                if frequency >= rate / 2:
                    continue
                chroma[midi % 12] += self._power(values, frequency, rate)
        if not blocks or max(chroma, default=0.0) < 1e-7:
            return self._empty("Audio silencioso: no hay perfil cromatico suficiente.")
        total = sum(chroma)
        profile = tuple(round(value / total, 6) for value in chroma)
        chroma_dto = ChromaAnalysisDTO(profile, self._concentration(profile), "Perfil cromatico PCM calculado en orden C a B.")
        ranked = sorted(((self._score(profile, root, template), root, mode) for mode, template in (("major", self._MAJOR), ("minor", self._MINOR)) for root in range(12)), reverse=True)
        best, root, mode = ranked[0]
        runner_up = ranked[1][0]
        confidence = round(max(0.0, min(1.0, (best - runner_up) / max(best, 1e-12) * 6 + chroma_dto.confidence * 0.35)), 2)
        if confidence < 0.30:
            return chroma_dto, KeyAnalysisDTO(None, None, None, confidence, "El perfil cromatico no distingue una tonalidad con confianza suficiente.")
        name = self._NAMES[root]
        return chroma_dto, KeyAnalysisDTO(f"{name} {mode}", name, mode, confidence, f"Tonalidad {name} {mode} estimada mediante coincidencia determinista de perfil cromatico.")

    @classmethod
    def _empty(cls, explanation):
        return ChromaAnalysisDTO((0.0,) * 12, 0.0, explanation), KeyAnalysisDTO(None, None, None, 0.0, explanation)

    @staticmethod
    def _power(values, frequency, rate):
        step = 2 * math.pi * frequency / rate
        real = sum(value * math.cos(step * index) for index, value in enumerate(values))
        imaginary = sum(value * math.sin(step * index) for index, value in enumerate(values))
        return (real * real + imaginary * imaginary) / (len(values) * len(values))

    @staticmethod
    def _score(profile, root, template):
        rotated = tuple(template[(index - root) % 12] for index in range(12))
        return sum(value * weight for value, weight in zip(profile, rotated))

    @staticmethod
    def _concentration(profile):
        return round(min(1.0, max(profile) * 4), 2)


class WaveAudioAnalyzer:
    """Inspect WAV PCM headers and peak with cooperative cancellation checks."""

    _CHUNK_FRAMES = 4096

    def __init__(self, feature_extractor=None, key_analyzer=None):
        self._feature_extractor = feature_extractor or PCMFeatureExtractor()
        self._key_analyzer = key_analyzer or PCMKeyAnalyzer()
        if not isinstance(self._feature_extractor, AudioFeatureExtractorProtocol):
            raise TypeError("WaveAudioAnalyzer requiere AudioFeatureExtractorProtocol.")
        if not callable(getattr(self._key_analyzer, "analyze", None)):
            raise TypeError("WaveAudioAnalyzer requiere un analizador tonal con analyze().")

    def analyze(self, query):
        path = Path(query.filepath)
        if not path.is_file():
            raise AudioAnalysisError("El archivo de audio no existe o no es accesible.")
        if self._cancelled(query):
            return AudioAnalysisResultDTO(query, "cancelled", None, "Analisis cancelado antes de leer el archivo.")
        try:
            with wave.open(str(path), "rb") as source:
                channels, sample_rate, frame_count = source.getnchannels(), source.getframerate(), source.getnframes()
                extracted = self._feature_extractor.extract(source, query)
                if extracted is None:
                    return AudioAnalysisResultDTO(query, "cancelled", None, "Analisis cancelado cooperativamente.")
                peak, energy, tempo = extracted
                source.rewind()
                tonal = self._key_analyzer.analyze(source, query)
                if tonal is None:
                    return AudioAnalysisResultDTO(query, "cancelled", None, "Analisis cancelado cooperativamente.")
                chroma, key = tonal
        except AudioAnalysisError:
            raise
        except (wave.Error, OSError, EOFError) as error:
            raise AudioAnalysisError("El archivo WAV esta corrupto o no puede leerse.") from error
        features = AudioFeaturesDTO(round(frame_count / sample_rate, 6), sample_rate, channels, round(peak, 6), tempo.bpm, key.key, energy.normalized_energy)
        return AudioAnalysisResultDTO(query, "completed", features, f"Duracion, sample rate, canales y peak analizados. {energy.explanation} {tempo.explanation} {key.explanation}", energy, tempo, chroma, key)

    @staticmethod
    def _cancelled(query):
        return query.cancellation_token is not None and query.cancellation_token.is_cancelled()



class MusicAnalysisService:
    """Coordinate one injected file analyzer without storing any result."""

    def __init__(self, analyzer=None):
        self._analyzer = analyzer or WaveAudioAnalyzer()
        if not isinstance(self._analyzer, AudioAnalyzerProtocol):
            raise TypeError("MusicAnalysisService requiere AudioAnalyzerProtocol.")

    def analyze(self, query):
        if not isinstance(query, AudioAnalysisQueryDTO):
            raise TypeError("MusicAnalysisService.analyze requiere AudioAnalysisQueryDTO.")
        result = self._analyzer.analyze(query)
        if not isinstance(result, AudioAnalysisResultDTO) or result.query != query:
            raise AudioAnalysisError("El analizador devolvio un resultado invalido.")
        return result
