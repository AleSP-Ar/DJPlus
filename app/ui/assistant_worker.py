"""Qt worker for non-blocking, cancellable local assistant queries."""

from PySide6.QtCore import QObject, Signal, Slot

from app.services.assistant_provider import ProviderCancellationToken
from app.services.local_assistant_mvp import LocalAssistantMVP


class AssistantWorker(QObject):
    """Execute one local read-only query outside the Qt GUI thread."""

    started = Signal()
    result = Signal(object)
    error = Signal(str)
    cancelled = Signal()
    finished = Signal()

    def __init__(self, assistant_mvp, query):
        super().__init__()
        if not isinstance(assistant_mvp, LocalAssistantMVP):
            raise TypeError("AssistantWorker requiere LocalAssistantMVP.")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("La consulta del asistente es obligatoria.")
        self._assistant_mvp = assistant_mvp
        self._query = query.strip()
        self._cancellation_token = ProviderCancellationToken()

    def cancel(self):
        """Request cooperative cancellation; no work or library state is changed."""
        self._cancellation_token.cancel()

    @Slot()
    def run(self):
        self.started.emit()
        try:
            if self._cancellation_token.is_cancelled():
                self.cancelled.emit()
                return
            outcome = self._assistant_mvp.ask(self._query, self._cancellation_token)
            execution = outcome.provider_execution
            if execution is not None and execution.error is not None:
                if execution.error.code == "cancelled":
                    self.cancelled.emit()
                else:
                    self.error.emit(execution.error.message)
                return
            if self._cancellation_token.is_cancelled():
                self.cancelled.emit()
                return
            self.result.emit(outcome)
        except Exception:
            self.error.emit("La consulta local no pudo completarse.")
        finally:
            self.finished.emit()
