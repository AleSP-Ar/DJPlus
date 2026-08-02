"""UI-safe read and recovery facade for durable import jobs."""

from dataclasses import dataclass
from datetime import datetime

from app.repository.import_repository import ImportRepository


@dataclass(frozen=True)
class ImportJobSummary:
    id: int
    status: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    total_items: int
    processed_items: int
    error_count: int


@dataclass(frozen=True)
class ImportItemDetail:
    id: int
    filepath: str
    status: str
    error_message: str | None


@dataclass(frozen=True)
class ImportJobDetail:
    job: ImportJobSummary
    items: tuple[ImportItemDetail, ...]


class ImportManagerFacade:
    """Present import history and recovery operations without exposing ORM objects."""

    def __init__(self, repository=None):
        self.repository = repository or ImportRepository()

    def list_jobs(self, limit=100):
        return tuple(self._job_summary(job) for job in self.repository.list_jobs(limit=limit))

    def get_job_detail(self, job_id):
        job = self.repository.get_job(job_id)
        items = self.repository.list_items(job_id)
        return ImportJobDetail(
            job=self._job_summary(job),
            items=tuple(
                ImportItemDetail(
                    id=item.id,
                    filepath=item.filepath,
                    status=item.status,
                    error_message=item.error_message,
                )
                for item in items
            ),
        )

    def recover_incomplete_jobs(self):
        return tuple(self._job_summary(job) for job in self.repository.recover_incomplete_jobs())

    def close(self):
        self.repository.close()

    def _job_summary(self, job):
        return ImportJobSummary(
            id=job.id,
            status=job.status,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            total_items=job.total_items,
            processed_items=job.processed_items,
            error_count=job.error_count,
        )
