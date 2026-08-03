"""Small dependency-free primitives for cooperative execution hardening."""

from dataclasses import dataclass
from threading import BoundedSemaphore, Lock


class ExecutionHardeningError(ValueError):
    """Raised when a hardening contract is invalid."""


@dataclass(frozen=True)
class ExecutionHardeningConfigDTO:
    """Optional limits. ``None`` timeout preserves the existing behaviour."""

    timeout_ms: int | None = None
    max_concurrency: int = 1

    def __post_init__(self):
        if self.timeout_ms is not None and (
            not isinstance(self.timeout_ms, int) or isinstance(self.timeout_ms, bool) or not 1 <= self.timeout_ms <= 120000
        ):
            raise ExecutionHardeningError("timeout_ms debe estar entre 1 y 120000, o ser nulo.")
        if not isinstance(self.max_concurrency, int) or isinstance(self.max_concurrency, bool) or not 1 <= self.max_concurrency <= 64:
            raise ExecutionHardeningError("max_concurrency debe estar entre 1 y 64.")


@dataclass(frozen=True)
class ExecutionEventMetricsDTO:
    """Immutable counters for the latest worker or executor lifecycle."""

    operation: str
    cancelled: int = 0
    timed_out: int = 0
    failed: int = 0
    concurrency_rejected: int = 0

    def __post_init__(self):
        if not isinstance(self.operation, str) or not self.operation.strip():
            raise ExecutionHardeningError("La operacion de metricas es obligatoria.")
        for value in (self.cancelled, self.timed_out, self.failed, self.concurrency_rejected):
            if not isinstance(value, int) or value < 0:
                raise ExecutionHardeningError("Las metricas de ejecucion deben ser enteros no negativos.")


class ExecutionConcurrencyLimiter:
    """Non-blocking, process-local limit used only at application boundaries."""

    def __init__(self, max_concurrency=1):
        self._semaphore = BoundedSemaphore(max_concurrency)
        self._lock = Lock()
        self._active = 0

    def try_acquire(self):
        acquired = self._semaphore.acquire(blocking=False)
        if acquired:
            with self._lock:
                self._active += 1
        return acquired

    def release(self):
        with self._lock:
            if self._active < 1:
                raise ExecutionHardeningError("No hay una ejecucion activa para liberar.")
            self._active -= 1
        self._semaphore.release()
