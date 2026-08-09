"""Worker-ready orchestration of discovery and metadata extraction."""

from app.repository.import_repository import ImportRepository
from app.services.import_events import ImportEvent
from app.services.import_queue import ImportQueue
from app.services.metadata_service import MetadataReadError, MetadataService
from app.services.scanner_service import ScannerService
from app.services.track_import_service import TrackImportService


class ImportService:
    """Run the import pipeline without writing to the library track table."""

    def __init__(self, scanner_service=None, metadata_service=None, queue=None, track_import_service=None):
        self.scanner_service = scanner_service or ScannerService()
        self.metadata_service = metadata_service or MetadataService()
        self.queue = queue or ImportQueue(ImportRepository())
        self.track_import_service = track_import_service or TrackImportService()

    def run(self, root_path, cancel_requested=None, on_progress=None, on_event=None):
        """Execute one job synchronously; callers may schedule it in a worker thread."""
        job = self.queue.create_job()
        self.queue.begin_discovery(job.id)
        self._notify(job.id, on_progress)
        self._emit("started", job.id, on_event)

        discovered = []
        for event in self.scanner_service.discover(
            root_path,
            cancel_requested=lambda: self._should_cancel(job.id, cancel_requested),
        ):
            if event.event_type == "cancelled":
                self.queue.request_cancellation(job.id)
                self._notify(job.id, on_progress)
                self._emit("cancelled", job.id, on_event)
                break
            if event.event_type == "error":
                item = self.queue.record_discovery_error(job.id, event.filepath, event.error_message)
                self._notify(job.id, on_progress)
                self._emit("failed", job.id, on_event, item=item, filepath=event.filepath, error_message=event.error_message)
                continue

            self._emit("file_found", job.id, on_event, filepath=event.filepath)
            discovered.append(event.filepath)

        for filepath in discovered:
            if self._should_cancel(job.id, cancel_requested):
                self.queue.request_cancellation(job.id)
                self._notify(job.id, on_progress)
                self._emit("cancelled", job.id, on_event)
                break
            item = self.queue.enqueue_for_processing(job.id, filepath)
            if item is None:
                self.queue.request_cancellation(job.id)
                self._notify(job.id, on_progress)
                self._emit("cancelled", job.id, on_event)
                break
        if not self.queue.is_cancelled(job.id):
            self._notify(job.id, on_progress)
            for item in self.queue.repository.list_items(job.id):
                if self._should_cancel(job.id, cancel_requested):
                    self.queue.request_cancellation(job.id)
                    self._notify(job.id, on_progress)
                    self._emit("cancelled", job.id, on_event)
                    break
                self._process_item(job.id, item, on_event)
                self._notify(job.id, on_progress)

        if not self.queue.is_cancelled(job.id):
            self.queue.complete(job.id)
            self._notify(job.id, on_progress)
            self._emit("completed", job.id, on_event)
        return self.queue.repository.get_job(job.id)

    def recover_incomplete_jobs(self):
        return self.queue.recover_incomplete_jobs()

    def resume(self, job_id, cancel_requested=None, on_progress=None, on_event=None):
        self.queue.recover_incomplete_jobs()
        job = self.queue.repository.get_job(job_id)
        if job.status not in self.queue.repository.INCOMPLETE_STATUSES:
            raise ValueError("El trabajo de importación no está disponible para reanudarse.")
        self.queue.begin_discovery(job_id)
        self._notify(job_id, on_progress)
        self._emit("started", job_id, on_event)
        for item in self.queue.repository.list_items(job_id):
            if self._should_cancel(job_id, cancel_requested):
                self.queue.request_cancellation(job_id)
                self._notify(job_id, on_progress)
                self._emit("cancelled", job_id, on_event)
                break
            if item.status != "pending":
                continue
            self._emit("file_found", job_id, on_event, item=item, filepath=item.filepath)
            self._process_item(job_id, item, on_event)
            self._notify(job_id, on_progress)
        if not self.queue.is_cancelled(job_id):
            self.queue.complete(job_id)
            self._notify(job_id, on_progress)
            self._emit("completed", job_id, on_event)
        return self.queue.repository.get_job(job_id)

    def _process_item(self, job_id, item, on_event):
        try:
            self._emit("processing_started", job_id, on_event, item=item, filepath=item.filepath)
            metadata = self.metadata_service.read(item.filepath)
            self._emit("metadata_processed", job_id, on_event, item=item, filepath=item.filepath)
            result = self.track_import_service.process(item.id, metadata)
            self.queue.repository.session.expire_all()
        except MetadataReadError as error:
            self.queue.mark_failed(item.id, str(error))
            self._emit("failed", job_id, on_event, item=item, filepath=item.filepath, error_message=str(error))
        except Exception as error:  # Defensive boundary for metadata and transactional import errors.
            self.queue.mark_failed(item.id, str(error))
            self._emit("failed", job_id, on_event, item=item, filepath=item.filepath, error_message=str(error))
        else:
            event_type = "skipped" if result.action == "skipped" else "track_imported"
            self._emit(event_type, job_id, on_event, item=item, filepath=item.filepath)

    def _should_cancel(self, job_id, cancel_requested):
        if self.queue.is_cancelled(job_id):
            return True
        return bool(cancel_requested and cancel_requested())

    def _notify(self, job_id, on_progress):
        if on_progress is not None:
            on_progress(self.queue.progress(job_id))

    def _emit(self, event_type, job_id, callback, item=None, filepath=None, error_message=None):
        if callback is not None:
            callback(
                ImportEvent(
                    event_type=event_type,
                    job_id=job_id,
                    item_id=item.id if item is not None else None,
                    filepath=filepath,
                    progress=self.queue.progress(job_id),
                    error_message=error_message,
                )
            )
