"""Persistent import-job coordination with no track persistence."""


class ImportQueue:
    """Coordinates import item state through ``ImportRepository``."""

    def __init__(self, repository):
        self.repository = repository
        self._cancelled_job_ids = set()

    def create_job(self):
        return self.repository.create_job()

    def begin_discovery(self, job_id):
        return self.repository.update_job_status(job_id, "scanning")

    def enqueue(self, job_id, filepath):
        if self.is_cancelled(job_id):
            return None
        return self.repository.add_item(job_id, filepath)

    def enqueue_for_processing(self, job_id, filepath):
        """Persist discovery and job progress with one commit before metadata work."""
        if self.is_cancelled(job_id):
            return None
        item = self.repository.add_item(job_id, filepath, commit=False)
        if self.repository.get_job(job_id).status != "reading_metadata":
            self.repository.update_job_status(job_id, "reading_metadata", commit=False)
        self.repository.commit()
        return item

    def begin_metadata_read(self, item_id):
        item = self.repository.update_item_status(item_id, "reading_metadata")
        self.repository.update_job_status(item.job_id, "reading_metadata")
        return item

    def mark_imported(self, item_id):
        return self.repository.update_item_status(item_id, "imported")

    def mark_failed(self, item_id, error_message):
        return self.repository.update_item_status(item_id, "failed", error_message)

    def record_discovery_error(self, job_id, filepath, error_message):
        item = self.enqueue(job_id, filepath)
        if item is None:
            return None
        return self.mark_failed(item.id, error_message)

    def request_cancellation(self, job_id):
        self._cancelled_job_ids.add(job_id)
        for item in self.repository.list_items(job_id):
            if item.status in self.repository.INCOMPLETE_STATUSES:
                self.repository.update_item_status(item.id, "cancelled")
        return self.repository.update_job_status(job_id, "cancelled")

    def is_cancelled(self, job_id):
        return job_id in self._cancelled_job_ids

    def complete(self, job_id):
        if self.is_cancelled(job_id):
            return self.repository.get_job(job_id)
        items = self.repository.list_items(job_id)
        statuses = [item.status for item in items]
        if not items or all(status == "skipped" for status in statuses):
            status = "skipped"
        elif any(status == "imported" for status in statuses):
            status = "imported"
        else:
            status = "failed"
        return self.repository.update_job_status(job_id, status)

    def progress(self, job_id):
        return self.repository.get_progress(job_id)

    def recover_incomplete_jobs(self):
        return self.repository.recover_incomplete_jobs()
