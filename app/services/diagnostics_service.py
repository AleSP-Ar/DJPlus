"""Read-only, in-memory diagnostics for local core health."""

from dataclasses import dataclass

from .execution_hardening import ExecutionEventMetricsDTO
from .optimization_metrics import OperationMetricsDTO


class DiagnosticsError(ValueError):
    pass


@dataclass(frozen=True)
class HealthSnapshotDTO:
    cache_entries: tuple[tuple[str, int], ...]
    timings_ms: tuple[tuple[str, float], ...]
    errors: int
    cancellations: int
    timeouts: int
    concurrency_rejections: int
    workers: tuple[tuple[str, str], ...]

    def __post_init__(self):
        for entries in (self.cache_entries, self.timings_ms, self.workers):
            if not isinstance(entries, tuple) or not all(isinstance(item, tuple) and len(item) == 2 for item in entries):
                raise DiagnosticsError("El snapshot debe usar pares inmutables.")
        if any(not isinstance(name, str) or not name for name, _ in self.cache_entries + self.timings_ms + self.workers):
            raise DiagnosticsError("Cada diagnostico debe tener nombre.")
        if any(not isinstance(value, int) or value < 0 for _, value in self.cache_entries):
            raise DiagnosticsError("Los tamanos de cache deben ser enteros no negativos.")
        if any(not isinstance(value, (int, float)) or value < 0 for _, value in self.timings_ms):
            raise DiagnosticsError("Los tiempos deben ser no negativos.")
        if any(not isinstance(value, str) for _, value in self.workers):
            raise DiagnosticsError("Los estados de worker deben ser texto.")
        if any(not isinstance(value, int) or value < 0 for value in (self.errors, self.cancellations, self.timeouts, self.concurrency_rejections)):
            raise DiagnosticsError("Los contadores deben ser enteros no negativos.")

    def export_text(self):
        """Export only aggregate counts and states, never arguments or secrets."""
        lines = [
            "DJPlus diagnostics",
            f"errors={self.errors}; cancellations={self.cancellations}; timeouts={self.timeouts}; concurrency_rejections={self.concurrency_rejections}",
        ]
        lines.extend(f"cache.{name}={value}" for name, value in self.cache_entries)
        lines.extend(f"time_ms.{name}={value:.3f}" for name, value in self.timings_ms)
        lines.extend(f"worker.{name}={value}" for name, value in self.workers)
        return "\n".join(lines)


class DiagnosticsService:
    """Aggregate explicitly injected runtime components without side effects."""

    def __init__(self, components=()):
        if isinstance(components, dict):
            components = tuple(components.items())
        if not isinstance(components, (tuple, list)) or not all(isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str) for item in components):
            raise TypeError("components debe ser una secuencia de pares nombre/componente.")
        self._components = tuple(components)

    def snapshot(self):
        caches, timings, workers = [], [], []
        errors = cancellations = timeouts = rejections = 0
        for name, component in self._components:
            for attribute in ("_interpretation_cache", "_dependency_cache"):
                cache = getattr(component, attribute, None)
                if isinstance(cache, dict):
                    caches.append((f"{name}.{attribute[1:]}", len(cache)))
            timing = getattr(component, "_last_metrics", None)
            if isinstance(timing, OperationMetricsDTO):
                timings.append((name, timing.total_ms))
            event_metrics = getattr(component, "_hardening_metrics", None)
            if isinstance(event_metrics, ExecutionEventMetricsDTO):
                errors += event_metrics.failed
                cancellations += event_metrics.cancelled
                timeouts += event_metrics.timed_out
                rejections += event_metrics.concurrency_rejected
            if hasattr(component, "is_running"):
                workers.append((name, "running" if bool(component.is_running) else "idle"))
            elif component.__class__.__name__.endswith("Worker"):
                workers.append((name, "idle"))
        return HealthSnapshotDTO(tuple(sorted(caches)), tuple(sorted(timings)), errors, cancellations, timeouts, rejections, tuple(sorted(workers)))
