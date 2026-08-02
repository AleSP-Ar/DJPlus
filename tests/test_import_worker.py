import tempfile
import unittest
import wave
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models import Base
from app.database.unit_of_work import UnitOfWork
from app.repository.import_repository import ImportRepository
from app.services.import_queue import ImportQueue
from app.services.import_service import ImportService
from app.services.import_worker import ImportWorker
from app.services.track_import_service import TrackImportService


class ImportWorkerTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.session = self.session_factory()
        self.repository = ImportRepository(session=self.session)
        service = ImportService(
            queue=ImportQueue(self.repository),
            track_import_service=TrackImportService(
                unit_of_work_factory=lambda: UnitOfWork(session_factory=self.session_factory)
            ),
        )
        self.worker = ImportWorker(import_service=service)

    def tearDown(self):
        self.session.close()

    def test_worker_runs_pipeline_and_emits_progress_events(self):
        events = []
        self.worker.subscribe(events.append)
        with tempfile.TemporaryDirectory() as directory:
            self._write_wav(directory, "valid.wav")
            self.worker.start(directory)
            result = self.worker.wait(timeout=5)

        self.assertEqual(result.status, "imported")
        self.assertFalse(self.worker.is_running)
        self.assertEqual(
            [event.event_type for event in events],
            ["started", "file_found", "metadata_processed", "track_imported", "completed"],
        )
        self.assertEqual(events[-1].progress["processed_items"], 1)

    def test_worker_cancels_cooperatively_without_losing_confirmed_work(self):
        events = []

        def cancel_after_first_file(event):
            events.append(event)
            if event.event_type == "file_found":
                self.worker.cancel()

        self.worker.subscribe(cancel_after_first_file)
        with tempfile.TemporaryDirectory() as directory:
            self._write_wav(directory, "first.wav")
            self._write_wav(directory, "second.wav")
            self.worker.start(directory)
            result = self.worker.wait(timeout=5)

        self.assertEqual(result.status, "cancelled")
        self.assertIn("cancelled", [event.event_type for event in events])
        self.assertGreaterEqual(result.processed_items, 1)

    def test_worker_reports_file_errors_and_resumes_recovered_work(self):
        events = []
        self.worker.subscribe(events.append)
        with tempfile.TemporaryDirectory() as directory:
            corrupt = Path(directory) / "bad.mp3"
            corrupt.write_bytes(b"not audio")
            self.worker.start(directory)
            failed_result = self.worker.wait(timeout=5)
            self.assertEqual(failed_result.status, "failed")
            self.assertIn("failed", [event.event_type for event in events])

            filepath = self._write_wav(directory, "resume.wav")
            job = self.repository.create_job()
            item = self.repository.add_item(job.id, filepath)
            self.repository.update_job_status(job.id, "reading_metadata")
            self.repository.update_item_status(item.id, "reading_metadata")

            recovered = self.worker.recover_incomplete_jobs()
            self.assertEqual([candidate.id for candidate in recovered], [job.id])
            self.worker.resume(job.id)
            resumed_result = self.worker.wait(timeout=5)

        self.assertEqual(resumed_result.status, "imported")
        self.assertEqual(self.repository.get_item(item.id).status, "imported")

    def _write_wav(self, directory, filename):
        filepath = Path(directory) / filename
        with wave.open(str(filepath), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(44100)
            audio.writeframes(b"\x00\x00" * 4410)
        return str(filepath)
