"""Provider-neutral foundation for future musical analysis."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class AnalysisFeature(str, Enum):
    BPM = "bpm"
    KEY = "key"
    ENERGY = "energy"
    DURATION = "duration"
    WAVEFORM = "waveform"


class AnalysisError(ValueError):
    """Base error for validated analysis requests and provider contracts."""


class UnsupportedAnalysisFeatureError(AnalysisError):
    """Raised when a requested feature is not offered by the provider."""


class AnalysisProviderError(AnalysisError):
    """Raised when a provider cannot return its declared result."""


class AnalysisContractError(AnalysisError):
    """Raised when a provider returns a result outside the DTO contract."""


@dataclass(frozen=True)
class AnalysisResultDTO:
    track_id: int
    feature_type: AnalysisFeature
    value: object
    provider: str
    provider_version: str
    confidence: float
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not isinstance(self.track_id, int) or self.track_id < 1:
            raise AnalysisContractError("El identificador de pista debe ser un entero positivo.")
        if not isinstance(self.feature_type, AnalysisFeature):
            raise AnalysisContractError("El tipo de análisis no es válido.")
        if not isinstance(self.provider, str) or not self.provider.strip():
            raise AnalysisContractError("El proveedor de análisis es obligatorio.")
        if not isinstance(self.provider_version, str) or not self.provider_version.strip():
            raise AnalysisContractError("La versión del proveedor es obligatoria.")
        if not isinstance(self.confidence, (int, float)) or not 0 <= self.confidence <= 1:
            raise AnalysisContractError("La confianza debe estar entre 0 y 1.")
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None:
            raise AnalysisContractError("La fecha del resultado debe incluir zona horaria.")


class AnalyzerProvider(ABC):
    """Replaceable analysis adapter with no persistence or UI dependency."""

    provider_name: str
    provider_version: str

    @abstractmethod
    def supported_features(self):
        """Return the immutable set of features this provider can produce."""

    @abstractmethod
    def analyze(self, track, features=None):
        """Return one AnalysisResultDTO per requested feature for ``track``."""


class MockAnalyzerProvider(AnalyzerProvider):
    """Deterministic provider for contracts and tests; it performs no DSP work."""

    provider_name = "mock"
    provider_version = "1.0"

    def __init__(self, values=None, confidence=1.0):
        self.values = {
            self._feature(feature): value
            for feature, value in (values or {}).items()
        }
        self.confidence = confidence
        self.calls = []

    def supported_features(self):
        return frozenset(self.values)

    def analyze(self, track, features=None):
        requested = tuple(features or self.supported_features())
        self.calls.append((track, requested))
        track_id = getattr(track, "id", None)
        results = []
        for feature in requested:
            normalized = self._feature(feature)
            if normalized not in self.values:
                raise AnalysisProviderError(f"El proveedor mock no tiene valor para {normalized.value}.")
            results.append(
                AnalysisResultDTO(
                    track_id=track_id,
                    feature_type=normalized,
                    value=self.values[normalized],
                    provider=self.provider_name,
                    provider_version=self.provider_version,
                    confidence=self.confidence,
                )
            )
        return tuple(results)

    def _feature(self, feature):
        try:
            return feature if isinstance(feature, AnalysisFeature) else AnalysisFeature(str(feature).lower())
        except ValueError as error:
            raise UnsupportedAnalysisFeatureError("La feature de análisis no es válida.") from error


class ProviderMusicAnalysisService:
    """Coordinate a provider and validate result ownership without persistence."""

    def __init__(self, provider):
        if not isinstance(provider, AnalyzerProvider):
            raise TypeError("ProviderMusicAnalysisService requiere un AnalyzerProvider.")
        self.provider = provider

    def analyze(self, track, features):
        track_id = getattr(track, "id", None)
        if not isinstance(track_id, int) or track_id < 1:
            raise AnalysisError("La pista debe tener un identificador válido.")
        requested = self._normalize_features(features)
        unsupported = set(requested) - set(self.provider.supported_features())
        if unsupported:
            names = ", ".join(sorted(feature.value for feature in unsupported))
            raise UnsupportedAnalysisFeatureError(f"El proveedor no soporta: {names}.")
        results = tuple(self.provider.analyze(track, requested))
        self._validate_results(track_id, requested, results)
        return results

    def _normalize_features(self, features):
        if not features:
            raise AnalysisError("Debe solicitarse al menos una feature de análisis.")
        try:
            normalized = tuple(
                feature if isinstance(feature, AnalysisFeature) else AnalysisFeature(str(feature).lower())
                for feature in features
            )
        except ValueError as error:
            raise UnsupportedAnalysisFeatureError("La feature de análisis no es válida.") from error
        if len(set(normalized)) != len(normalized):
            raise AnalysisError("Las features de análisis no pueden repetirse.")
        return normalized

    def _validate_results(self, track_id, requested, results):
        if len(results) != len(requested):
            raise AnalysisContractError("El proveedor no devolvió todos los resultados solicitados.")
        result_features = set()
        for result in results:
            if not isinstance(result, AnalysisResultDTO):
                raise AnalysisContractError("El proveedor debe devolver AnalysisResultDTO.")
            if result.track_id != track_id:
                raise AnalysisContractError("El resultado no pertenece a la pista solicitada.")
            if result.feature_type not in requested:
                raise AnalysisContractError("El proveedor devolvió una feature no solicitada.")
            if result.provider != self.provider.provider_name or result.provider_version != self.provider.provider_version:
                raise AnalysisContractError("La procedencia del resultado no coincide con el proveedor.")
            result_features.add(result.feature_type)
        if result_features != set(requested):
            raise AnalysisContractError("El proveedor devolvió features repetidas o incompletas.")


# Compatibility alias. New public imports must use ProviderMusicAnalysisService;
# local PCM/WAV callers use AudioFileMusicAnalysisService from app.services.
MusicAnalysisService = ProviderMusicAnalysisService
