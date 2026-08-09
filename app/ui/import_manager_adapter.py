"""Qt signal adapter for the UI-independent ImportWorker."""

from PySide6.QtCore import QObject, Signal

from app.services.import_worker import ImportWorker
from app.services.import_manager_facade import ImportManagerFacade


class ImportManagerAdapter(QObject):
    """Expose ImportWorker activity as Qt-safe, UI-oriented signals."""

    event_received = Signal(object)
    progress_changed = Signal(dict)
    job_status_changed = Signal(str)
    file_processed = Signal(str, str)
    error_reported = Signal(str, str)
    running_changed = Signal(bool)
    history_loaded = Signal(list)
    job_detail_loaded = Signal(object)
    recovery_completed = Signal(list)
    import_completed = Signal()

    def __init__(self, worker=None, facade=None, parent=None):
        super().__init__(parent)
        self.worker = worker or ImportWorker()
        self.facade = facade or ImportManagerFacade()
        self.worker.subscribe(self._handle_event)

    @property
    def is_running(self):
        return self.worker.is_running

    def start(self, folder_path):
        if not isinstance(folder_path, str) or not folder_path.strip():
            raise ValueError("Selecciona una carpeta para importar.")
        thread = self.worker.start(folder_path)
        self.running_changed.emit(True)
        return thread

    def cancel(self):
        if self.worker.is_running:
            self.worker.cancel()

    def load_history(self):
        jobs = list(self.facade.list_jobs())
        self.history_loaded.emit(jobs)
        return jobs

    def load_job_detail(self, job_id):
        detail = self.facade.get_job_detail(job_id)
        self.job_detail_loaded.emit(detail)
        return detail

    def recover_incomplete_jobs(self):
        jobs = list(self.facade.recover_incomplete_jobs())
        self.recovery_completed.emit(jobs)
        self.load_history()
        return jobs

    def close(self):
        self.facade.close()

    def _handle_event(self, event):
        """Called by the worker thread; Qt queues connected UI slots safely."""
        self.event_received.emit(event)
        if event.progress is not None:
            self.progress_changed.emit(dict(event.progress))
            status = event.progress.get("status")
            if status:
                self.job_status_changed.emit(status)
        if event.event_type in {"track_imported", "skipped", "failed"} and event.filepath:
            self.file_processed.emit(event.filepath, event.event_type)
        if event.event_type == "failed" and event.error_message:
            self.error_reported.emit(event.filepath or "Importación", event.error_message)
        if event.event_type in {"completed", "cancelled"}:
            self.running_changed.emit(False)
        if event.event_type == "completed":
            self.import_completed.emit()
