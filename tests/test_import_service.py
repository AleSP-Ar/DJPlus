import tempfile
import unittest
import wave
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base
from app.database.unit_of_work import UnitOfWork
from app.repository.import_repository import ImportRepository
from app.services.import_queue import ImportQueue
from app.services.import_service import ImportService
from app.services.track_import_service import TrackImportService


class ImportServiceTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        self.session_factory = sessionmaker(bind=engine)
        self.session = self.session_factory()
        Base.metadata.create_all(engine)
        self.repository = ImportRepository(session=self.session)
        self.service = ImportService(
            queue=ImportQueue(self.repository),
            track_import_service=TrackImportService(
                unit_of_work_factory=lambda: UnitOfWork(session_factory=self.session_factory)
            ),
        )

    def tearDown(self):
        self.session.close()

    def test_pipeline_discovers_reads_metadata_and_records_item_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            valid = root / "valid.wav"
            with wave.open(str(valid), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(44100)
                audio.writeframes(b"\x00\x00" * 4410)
            (root / "broken.mp3").write_bytes(b"corrupt")
            progress_events = []

            job = self.service.run(root, on_progress=progress_events.append)

        items = self.repository.list_items(job.id)
        self.assertEqual(job.status, "imported")
        self.assertEqual({item.status for item in items}, {"imported", "failed"})
        self.assertEqual(job.total_items, 2)
        self.assertEqual(job.processed_items, 2)
        self.assertEqual(job.error_count, 1)
        self.assertEqual(progress_events[-1]["status"], "imported")

    def test_pipeline_cancels_and_recovers_incomplete_jobs(self):
        with tempfile.TemporaryDirectory() as directory:
            cancelled = self.service.run(directory, cancel_requested=lambda: True)

        self.assertEqual(cancelled.status, "cancelled")

        interrupted = self.repository.create_job()
        item = self.repository.add_item(interrupted.id, "interrupted.wav")
        self.repository.update_job_status(interrupted.id, "reading_metadata")
        self.repository.update_item_status(item.id, "reading_metadata")

        recovered = self.service.recover_incomplete_jobs()

        self.assertEqual([job.id for job in recovered], [interrupted.id])
        self.assertEqual(self.repository.get_job(interrupted.id).status, "pending")
        self.assertEqual(self.repository.list_items(interrupted.id)[0].status, "pending")
