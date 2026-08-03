"""Qt worker for non-blocking, cancellable local assistant queries."""

import time
from threading import Lock

from PySide6.QtCore import QObject, Signal, Slot

from app.services.assistant_provider import ProviderCancellationToken
from app.services.local_assistant_mvp import LocalAssistantMVP
from app.services.execution_hardening import ExecutionConcurrencyLimiter, ExecutionEventMetricsDTO, ExecutionHardeningConfigDTO


class AssistantWorker(QObject):
    """Execute one local read-only query outside the Qt GUI thread."""

    started = Signal()
    result = Signal(object)
    error = Signal(str)
    cancelled = Signal()
    finished = Signal()
    _limiters = {}
    _limiters_lock = Lock()

    def __init__(self, assistant_mvp, query, hardening_config=None):
        super().__init__()
        if not isinstance(assistant_mvp, LocalAssistantMVP):
            raise TypeError("AssistantWorker requiere LocalAssistantMVP.")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("La consulta del asistente es obligatoria.")
        if hardening_config is not None and not isinstance(hardening_config, ExecutionHardeningConfigDTO):
            raise TypeError("hardening_config debe ser ExecutionHardeningConfigDTO o nulo.")
        self._assistant_mvp = assistant_mvp
        self._query = query.strip()
        self._cancellation_token = ProviderCancellationToken()
        self._hardening_config = hardening_config or ExecutionHardeningConfigDTO()
        self._limiter = self._shared_limiter(self._hardening_config.max_concurrency)
        self._hardening_metrics = ExecutionEventMetricsDTO("assistant_worker")

    def cancel(self):
        """Request cooperative cancellation; no work or library state is changed."""
        self._cancellation_token.cancel()

    def close(self):
        """Safe worker shutdown is cooperative: it never terminates a Qt thread."""
        self.cancel()

    @classmethod
    def _shared_limiter(cls, max_concurrency):
        with cls._limiters_lock:
            limiter = cls._limiters.get(max_concurrency)
            if limiter is None:
                limiter = ExecutionConcurrencyLimiter(max_concurrency)
                cls._limiters[max_concurrency] = limiter
            return limiter

    @Slot()
    def run(self):
        self.started.emit()
        if not self._limiter.try_acquire():
            self._hardening_metrics = ExecutionEventMetricsDTO("assistant_worker", concurrency_rejected=1)
            self.error.emit("Se alcanzo el limite de concurrencia del asistente local.")
            self.finished.emit()
            return
        started = time.perf_counter()
        try:
            if self._cancellation_token.is_cancelled():
                self._hardening_metrics = ExecutionEventMetricsDTO("assistant_worker", cancelled=1)
                self.cancelled.emit()
                return
            outcome = self._assistant_mvp.ask(self._query, self._cancellation_token)
            execution = outcome.provider_execution
            if execution is not None and execution.error is not None:
                if execution.error.code == "cancelled":
                    self._hardening_metrics = ExecutionEventMetricsDTO("assistant_worker", cancelled=1)
                    self.cancelled.emit()
                else:
                    timed_out = 1 if execution.error.code == "timeout" else 0
                    self._hardening_metrics = ExecutionEventMetricsDTO("assistant_worker", timed_out=timed_out, failed=1 - timed_out)
                    self.error.emit(execution.error.message)
                return
            if self._cancellation_token.is_cancelled():
                self._hardening_metrics = ExecutionEventMetricsDTO("assistant_worker", cancelled=1)
                self.cancelled.emit()
                return
            if self._hardening_config.timeout_ms is not None and (time.perf_counter() - started) * 1000 >= self._hardening_config.timeout_ms:
                self._hardening_metrics = ExecutionEventMetricsDTO("assistant_worker", timed_out=1)
                self.error.emit("La consulta local supero el timeout configurado.")
                return
            self.result.emit(outcome)
        except Exception:
            self._hardening_metrics = ExecutionEventMetricsDTO("assistant_worker", failed=1)
            self.error.emit("La consulta local no pudo completarse.")
        finally:
            self._limiter.release()
            self.finished.emit()
