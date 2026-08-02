import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base
from app.repository.import_repository import ImportRepository
from app.services.import_queue import ImportQueue


class ImportQueueTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        self.session = sessionmaker(bind=engine)()
        Base.metadata.create_all(engine)
        self.repository = ImportRepository(session=self.session)
        self.queue = ImportQueue(self.repository)

    def tearDown(self):
        self.session.close()

    def test_enqueues_metadata_results_and_completes_progress(self):
        job = self.queue.create_job()
        self.queue.begin_discovery(job.id)
        item = self.queue.enqueue(job.id, "track.wav")
        self.queue.begin_metadata_read(item.id)
        self.queue.mark_imported(item.id)
        completed = self.queue.complete(job.id)

        self.assertEqual(completed.status, "imported")
        self.assertEqual(
            self.queue.progress(job.id),
            {"job_id": job.id, "status": "imported", "total_items": 1, "processed_items": 1, "error_count": 0},
        )

    def test_cancellation_marks_pending_items_and_job(self):
        job = self.queue.create_job()
        first = self.queue.enqueue(job.id, "first.wav")
        second = self.queue.enqueue(job.id, "second.wav")

        cancelled = self.queue.request_cancellation(job.id)

        self.assertEqual(cancelled.status, "cancelled")
        self.assertTrue(self.queue.is_cancelled(job.id))
        self.assertEqual([item.status for item in self.repository.list_items(job.id)], ["cancelled", "cancelled"])
        self.assertIsNone(self.queue.enqueue(job.id, "third.wav"))

    def test_enqueues_processing_item_with_one_persisted_queue_transition(self):
        job = self.queue.create_job()

        item = self.queue.enqueue_for_processing(job.id, "processing.mp3")

        self.assertEqual(item.status, "pending")
        self.assertEqual(self.repository.get_job(job.id).status, "reading_metadata")
        self.assertEqual(self.queue.progress(job.id)["total_items"], 1)
