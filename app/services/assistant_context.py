"""Bounded, auditable context assembly for future assistant integrations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone


class AssistantContextError(ValueError):
    """Raised when context providers or their contracts are invalid."""


@dataclass(frozen=True)
class AssistantContextDTO:
    available_data: dict
    data_sources: tuple[str, ...]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    context_version: str = "1.0"

    def __post_init__(self):
        if not isinstance(self.available_data, dict):
            raise AssistantContextError("Los datos de contexto deben ser un diccionario.")
        if not self.data_sources or not all(isinstance(source, str) and source for source in self.data_sources):
            raise AssistantContextError("El contexto debe declarar al menos un origen válido.")
        if not isinstance(self.timestamp, datetime) or self.timestamp.tzinfo is None:
            raise AssistantContextError("El timestamp del contexto debe incluir zona horaria.")
        if not isinstance(self.context_version, str) or not self.context_version.strip():
            raise AssistantContextError("La versión de contexto es obligatoria.")


class ContextProvider(ABC):
    """Allowlisted source that exposes a bounded AssistantContextDTO."""

    @abstractmethod
    def get_context(self):
        """Return a context DTO without exposing persistence or filesystem objects."""


class LibraryContextProvider(ContextProvider):
    """Expose only aggregate library metrics through an injected service."""

    SOURCE = "library"

    def __init__(self, library_service):
        self.library_service = library_service

    def get_context(self):
        return AssistantContextDTO(
            available_data={"track_count": self.library_service.count_tracks()},
            data_sources=(self.SOURCE,),
        )


class DJContextProvider(ContextProvider):
    """Expose deterministic compatibility capabilities, not track-level data."""

    SOURCE = "dj_intelligence"

    def __init__(self, dj_intelligence_service):
        self.dj_intelligence_service = dj_intelligence_service

    def get_context(self):
        weights = self.dj_intelligence_service.scoring_engine.WEIGHTS
        return AssistantContextDTO(
            available_data={
                "compatibility_available": True,
                "scoring_metrics": tuple(sorted(weights)),
                "score_range": (0, 100),
            },
            data_sources=(self.SOURCE,),
        )


class AssistantContextBuilder:
    """Combine only permitted providers into a filtered, namespaced context DTO."""

    SENSITIVE_KEY_FRAGMENTS = frozenset(
        {"path", "file", "sql", "sqlite", "session", "orm", "repository"}
    )

    def __init__(self, providers, context_version="1.0"):
        if not isinstance(context_version, str) or not context_version.strip():
            raise AssistantContextError("La versión de contexto es obligatoria.")
        self.providers = tuple(providers)
        if not all(isinstance(provider, ContextProvider) for provider in self.providers):
            raise TypeError("AssistantContextBuilder requiere ContextProvider permitidos.")
        self.context_version = context_version

    def build(self):
        available_data = {}
        sources = []
        for provider in self.providers:
            context = provider.get_context()
            if not isinstance(context, AssistantContextDTO):
                raise AssistantContextError("El provider debe devolver AssistantContextDTO.")
            for source in context.data_sources:
                if source in available_data:
                    raise AssistantContextError("Los orígenes de contexto no pueden repetirse.")
                available_data[source] = self._filter_mapping(context.available_data)
                sources.append(source)
        return AssistantContextDTO(
            available_data=available_data,
            data_sources=tuple(sources),
            context_version=self.context_version,
        )

    def _filter_mapping(self, data):
        if not isinstance(data, dict):
            raise AssistantContextError("Los datos del provider deben ser un diccionario.")
        filtered = {}
        for key, value in data.items():
            if not isinstance(key, str) or self._is_sensitive_key(key):
                continue
            safe_value = self._safe_value(value)
            if safe_value is not None:
                filtered[key] = safe_value
        return filtered

    def _is_sensitive_key(self, key):
        normalized_key = key.casefold().replace("_", "").replace("-", "")
        return any(fragment in normalized_key for fragment in self.SENSITIVE_KEY_FRAGMENTS)

    def _safe_value(self, value):
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (tuple, list)):
            values = [self._safe_value(item) for item in value]
            return tuple(item for item in values if item is not None)
        if isinstance(value, dict):
            return self._filter_mapping(value)
        return None
