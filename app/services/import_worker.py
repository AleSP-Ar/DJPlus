"""Thread-based, UI-independent execution wrapper for ImportService."""

from threading import Event, Lock, Thread
import time

from app.services.import_events import ImportEvent
from app.services.import_service import ImportService
from app.services.execution_hardening import ExecutionConcurrencyLimiter, ExecutionEventMetricsDTO, ExecutionHardeningConfigDTO


class ImportWorker:
    """Run one import job in a background thread and forward progress callbacks."""

    def __init__(self, import_service=None, hardening_config=None):
        if hardening_config is not None and not isinstance(hardening_config, ExecutionHardeningConfigDTO):
            raise TypeError("hardening_config debe ser ExecutionHardeningConfigDTO o nulo.")
        self.import_service = import_service or ImportService()
        self._hardening_config = hardening_config or ExecutionHardeningConfigDTO()
        self._limiter = ExecutionConcurrencyLimiter(self._hardening_config.max_concurrency)
        self._cancel_requested = Event()
        self._finished = Event()
        self._lock = Lock()
        self._callbacks = []
        self._thread = None
        self.result = None
        self.error = None
        self.job_id = None
        self._started_at = None
        self._hardening_metrics = ExecutionEventMetricsDTO("import_worker")

    def subscribe(self, callback):
        self._callbacks.append(callback)

    def start(self, root_path):
        with self._lock:
            if self.is_running:
                raise RuntimeError("Ya hay una importación en ejecución.")
            self._cancel_requested.clear()
            self._finished.clear()
            self.result = None
            self.error = None
            self.job_id = None
            self._started_at = time.perf_counter()
            self._hardening_metrics = ExecutionEventMetricsDTO("import_worker")
            if not self._limiter.try_acquire():
                self._hardening_metrics = ExecutionEventMetricsDTO("import_worker", concurrency_rejected=1)
                raise RuntimeError("Se alcanzo el limite de concurrencia de importacion.")
            self._thread = Thread(target=self._run, args=(root_path,), daemon=True)
            self._thread.start()
            return self._thread

    def cancel(self):
        self._cancel_requested.set()

    def wait(self, timeout=None):
        self._finished.wait(timeout)
        return self.result

    def close(self, timeout=None):
        """Request cooperative cancellation and wait only for the configured bound."""
        self.cancel()
        self._finished.wait(timeout)
        return not self.is_running

    @property
    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def recover_incomplete_jobs(self):
        return self.import_service.recover_incomplete_jobs()

    def resume(self, job_id):
        with self._lock:
            if self.is_running:
                raise RuntimeError("Ya hay una importación en ejecución.")
            self._cancel_requested.clear()
            self._finished.clear()
            self.result = None
            self.error = None
            self.job_id = job_id
            self._started_at = time.perf_counter()
            self._hardening_metrics = ExecutionEventMetricsDTO("import_worker")
            if not self._limiter.try_acquire():
                self._hardening_metrics = ExecutionEventMetricsDTO("import_worker", concurrency_rejected=1)
                raise RuntimeError("Se alcanzo el limite de concurrencia de importacion.")
            self._thread = Thread(target=self._resume, args=(job_id,), daemon=True)
            self._thread.start()
            return self._thread

    def _run(self, root_path):
        try:
            self.result = self.import_service.run(
                root_path,
                cancel_requested=self._cancel_requested.is_set,
                on_event=self._forward_event,
            )
        except Exception as error:
            self.error = error
            self._hardening_metrics = ExecutionEventMetricsDTO("import_worker", failed=1)
            self._emit(ImportEvent("failed", job_id=self.job_id, error_message=str(error)))
        finally:
            self._finished.set()
            self._limiter.release()

    def _resume(self, job_id):
        try:
            self.result = self.import_service.resume(
                job_id,
                cancel_requested=self._cancel_requested.is_set,
                on_event=self._forward_event,
            )
        except Exception as error:
            self.error = error
            self._hardening_metrics = ExecutionEventMetricsDTO("import_worker", failed=1)
            self._emit(ImportEvent("failed", job_id=job_id, error_message=str(error)))
        finally:
            self._finished.set()
            self._limiter.release()

    def _forward_event(self, event):
        if self._deadline_expired():
            self._cancel_requested.set()
            self._hardening_metrics = ExecutionEventMetricsDTO("import_worker", timed_out=1)
        elif event.event_type == "cancelled":
            self._hardening_metrics = ExecutionEventMetricsDTO("import_worker", cancelled=1)
        if event.job_id is not None:
            self.job_id = event.job_id
        self._emit(event)

    def _emit(self, event):
        for callback in tuple(self._callbacks):
            callback(event)

    def _deadline_expired(self):
        return self._hardening_config.timeout_ms is not None and self._started_at is not None and (
            (time.perf_counter() - self._started_at) * 1000 >= self._hardening_config.timeout_ms
        )
