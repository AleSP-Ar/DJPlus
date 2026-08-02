import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base
from app.repository.import_repository import ImportRepository
from app.services.import_manager_facade import ImportManagerFacade


class ImportManagerFacadeTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session = sessionmaker(bind=engine)()
        self.repository = ImportRepository(session=self.session)
        self.facade = ImportManagerFacade(repository=self.repository)

    def tearDown(self):
        self.session.close()

    def test_lists_history_and_returns_orm_free_job_detail(self):
        failed_job = self.repository.create_job()
        failed_item = self.repository.add_item(failed_job.id, "broken.mp3")
        self.repository.update_item_status(failed_item.id, "failed", "invalid audio")
        self.repository.update_job_status(failed_job.id, "failed")
        imported_job = self.repository.create_job()
        self.repository.update_job_status(imported_job.id, "skipped")

        history = self.facade.list_jobs()
        detail = self.facade.get_job_detail(failed_job.id)

        self.assertEqual([job.id for job in history], [imported_job.id, failed_job.id])
        self.assertEqual(detail.job.error_count, 1)
        self.assertEqual(detail.items[0].error_message, "invalid audio")
        self.assertFalse(hasattr(detail.job, "_sa_instance_state"))

    def test_recovers_incomplete_jobs_and_returns_updated_summaries(self):
        interrupted = self.repository.create_job()
        item = self.repository.add_item(interrupted.id, "interrupted.wav")
        self.repository.update_job_status(interrupted.id, "reading_metadata")
        self.repository.update_item_status(item.id, "reading_metadata")

        recovered = self.facade.recover_incomplete_jobs()

        self.assertEqual([job.id for job in recovered], [interrupted.id])
        self.assertEqual(recovered[0].status, "pending")
        self.assertEqual(self.facade.get_job_detail(interrupted.id).items[0].status, "pending")
