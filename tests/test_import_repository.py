import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base
from app.repository.import_repository import ImportRepository


class ImportRepositoryTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session = sessionmaker(bind=engine)()
        self.repository = ImportRepository(session=self.session)

    def tearDown(self):
        self.session.close()

    def test_creates_job_registers_items_and_reports_progress(self):
        job = self.repository.create_job()
        first = self.repository.add_item(job.id, " first.mp3 ")
        second = self.repository.add_item(job.id, "second.mp3")
        self.repository.update_job_status(job.id, "scanning")
        self.repository.update_item_status(first.id, "imported")
        self.repository.update_item_status(second.id, "failed", "Unreadable metadata")

        progress = self.repository.get_progress(job.id)
        self.assertTrue(Path(first.filepath).is_absolute())
        self.assertEqual(progress["status"], "scanning")
        self.assertEqual(progress["total_items"], 2)
        self.assertEqual(progress["processed_items"], 2)
        self.assertEqual(progress["error_count"], 1)
        self.assertIsNotNone(self.repository.get_job(job.id).started_at)

    def test_rejects_invalid_states_and_duplicate_items(self):
        job = self.repository.create_job()
        item = self.repository.add_item(job.id, "duplicate.mp3")

        with self.assertRaises(ValueError):
            self.repository.update_job_status(job.id, "complete")
        with self.assertRaises(ValueError):
            self.repository.update_item_status(item.id, "unknown")
        with self.assertRaises(ValueError):
            self.repository.add_item(job.id, "duplicate.mp3")

    def test_normalizes_filepaths_and_truncates_stored_error_messages(self):
        job = self.repository.create_job()
        item = self.repository.add_item(job.id, "relative.mp3")

        failed = self.repository.update_item_status(item.id, "failed", "x" * 600 + "\nunsafe formatting")

        self.assertTrue(Path(failed.filepath).is_absolute())
        self.assertEqual(len(failed.error_message), self.repository.MAX_ERROR_MESSAGE_LENGTH)
        self.assertNotIn("\n", failed.error_message)
        with self.assertRaises(ValueError):
            self.repository.add_item(job.id, "./relative.mp3")

    def test_recovers_incomplete_jobs_and_in_progress_items(self):
        interrupted = self.repository.create_job()
        active_item = self.repository.add_item(interrupted.id, "active.mp3")
        pending_item = self.repository.add_item(interrupted.id, "pending.mp3")
        completed = self.repository.create_job()
        self.repository.update_job_status(interrupted.id, "reading_metadata")
        self.repository.update_item_status(active_item.id, "reading_metadata")
        self.repository.update_job_status(completed.id, "imported")

        recovered = self.repository.recover_incomplete_jobs()

        self.assertEqual([job.id for job in recovered], [interrupted.id])
        self.assertEqual(self.repository.get_job(interrupted.id).status, "pending")
        items = self.repository.list_items(interrupted.id)
        self.assertEqual([item.status for item in items], ["pending", "pending"])
        self.assertEqual([job.id for job in self.repository.list_incomplete_jobs()], [interrupted.id])
        self.assertEqual(self.repository.get_job(completed.id).status, "imported")
