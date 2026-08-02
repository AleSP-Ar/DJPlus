from datetime import datetime

from app.database import SessionLocal
from app.database.models import IMPORT_STATUSES, ImportItem, ImportJob
from app.services.filepath_normalization import normalize_filepath


class ImportRepository:
    """Persistence boundary for durable import job and item state."""

    TERMINAL_STATUSES = {"imported", "skipped", "failed", "cancelled"}
    INCOMPLETE_STATUSES = {"pending", "scanning", "reading_metadata"}
    MAX_ERROR_MESSAGE_LENGTH = 500

    def __init__(self, session=None):
        self.session = session or SessionLocal()

    def create_job(self, commit=True):
        job = ImportJob(status="pending")
        self.session.add(job)
        self._finish(commit)
        return job

    def add_item(self, job_id, filepath, commit=True):
        job = self._require_job(job_id)
        cleaned_path = self._validate_filepath(filepath)
        if self._item_for_filepath(job_id, cleaned_path) is not None:
            raise ValueError("El archivo ya está registrado en este trabajo de importación.")
        item = ImportItem(job_id=job.id, filepath=cleaned_path, status="pending")
        self.session.add(item)
        job.total_items += 1
        self._finish(commit)
        return item

    def update_job_status(self, job_id, status, commit=True):
        job = self._require_job(job_id)
        self._validate_status(status)
        job.status = status
        now = datetime.now()
        if status in {"scanning", "reading_metadata"} and job.started_at is None:
            job.started_at = now
        if status in self.TERMINAL_STATUSES:
            job.finished_at = now
        else:
            job.finished_at = None
        self._finish(commit)
        return job

    def update_item_status(self, item_id, status, error_message=None, commit=True):
        item = self._require_item(item_id)
        self._validate_status(status)
        was_terminal = item.status in self.TERMINAL_STATUSES
        is_terminal = status in self.TERMINAL_STATUSES
        was_failed = item.status == "failed"

        item.status = status
        item.error_message = self._validate_error_message(error_message) if error_message else None
        job = item.job
        if not was_terminal and is_terminal:
            job.processed_items += 1
        elif was_terminal and not is_terminal:
            job.processed_items -= 1
        if not was_failed and status == "failed":
            job.error_count += 1
        elif was_failed and status != "failed":
            job.error_count -= 1
        self._finish(commit)
        return item

    def get_job(self, job_id):
        return self._require_job(job_id)

    def get_item(self, item_id):
        return self._require_item(item_id)

    def get_progress(self, job_id):
        job = self._require_job(job_id)
        return {
            "job_id": job.id,
            "status": job.status,
            "total_items": job.total_items,
            "processed_items": job.processed_items,
            "error_count": job.error_count,
        }

    def list_incomplete_jobs(self):
        return (
            self.session.query(ImportJob)
            .filter(ImportJob.status.in_(self.INCOMPLETE_STATUSES))
            .order_by(ImportJob.created_at.asc(), ImportJob.id.asc())
            .all()
        )

    def recover_incomplete_jobs(self, commit=True):
        jobs = self.list_incomplete_jobs()
        for job in jobs:
            job.status = "pending"
            job.finished_at = None
            for item in job.items:
                if item.status in {"scanning", "reading_metadata"}:
                    item.status = "pending"
                    item.error_message = None
        self._finish(commit)
        return jobs

    def list_items(self, job_id):
        self._require_job(job_id)
        return (
            self.session.query(ImportItem)
            .filter(ImportItem.job_id == job_id)
            .order_by(ImportItem.id.asc())
            .all()
        )

    def close(self):
        self.session.close()

    def commit(self):
        """Commit a caller-composed short repository transaction."""
        self.session.commit()

    def _finish(self, commit):
        if commit:
            self.session.commit()
        else:
            self.session.flush()

    def _require_job(self, job_id):
        job = self.session.get(ImportJob, job_id)
        if job is None:
            raise ValueError("El trabajo de importación no existe.")
        return job

    def _require_item(self, item_id):
        item = self.session.get(ImportItem, item_id)
        if item is None:
            raise ValueError("El ítem de importación no existe.")
        return item

    def _item_for_filepath(self, job_id, filepath):
        return (
            self.session.query(ImportItem)
            .filter(ImportItem.job_id == job_id, ImportItem.filepath == filepath)
            .one_or_none()
        )

    def _validate_status(self, status):
        if status not in IMPORT_STATUSES:
            raise ValueError("El estado de importación no es válido.")

    def _validate_filepath(self, filepath):
        return normalize_filepath(filepath)

    def _validate_error_message(self, error_message):
        if not isinstance(error_message, str):
            raise ValueError("El mensaje de error debe ser texto.")
        return " ".join(error_message.split())[: self.MAX_ERROR_MESSAGE_LENGTH]
