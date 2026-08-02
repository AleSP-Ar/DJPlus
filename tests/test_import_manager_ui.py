import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.services.import_events import ImportEvent
from app.services.import_manager_facade import ImportItemDetail, ImportJobDetail, ImportJobSummary
from app.ui.import_manager_adapter import ImportManagerAdapter
from app.ui.import_manager_panel import ImportManagerPanel


class FakeImportWorker:
    def __init__(self):
        self.callbacks = []
        self.started_paths = []
        self.cancel_calls = 0
        self.is_running = False

    def subscribe(self, callback):
        self.callbacks.append(callback)

    def start(self, folder_path):
        self.started_paths.append(folder_path)
        self.is_running = True
        return object()

    def cancel(self):
        self.cancel_calls += 1

    def emit(self, event):
        for callback in self.callbacks:
            callback(event)


class FakeImportManagerFacade:
    def __init__(self):
        self.jobs = [
            ImportJobSummary(7, "failed", None, None, None, 2, 2, 1),
        ]
        self.recovery_calls = 0

    def list_jobs(self):
        return tuple(self.jobs)

    def get_job_detail(self, job_id):
        return ImportJobDetail(
            self.jobs[0],
            (ImportItemDetail(4, "music/broken.mp3", "failed", "invalid audio"),),
        )

    def recover_incomplete_jobs(self):
        self.recovery_calls += 1
        return tuple()

    def close(self):
        pass


class ImportManagerUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.worker = FakeImportWorker()
        self.facade = FakeImportManagerFacade()
        self.adapter = ImportManagerAdapter(worker=self.worker, facade=self.facade)

    def tearDown(self):
        self.application.processEvents()

    def test_adapter_converts_worker_events_into_progress_and_error_signals(self):
        progress_events = []
        processed_files = []
        errors = []
        self.adapter.progress_changed.connect(progress_events.append)
        self.adapter.file_processed.connect(lambda filepath, state: processed_files.append((filepath, state)))
        self.adapter.error_reported.connect(lambda filepath, message: errors.append((filepath, message)))

        self.worker.emit(
            ImportEvent(
                "failed",
                job_id=4,
                filepath="broken.mp3",
                progress={"status": "reading_metadata", "total_items": 2, "processed_items": 1, "error_count": 1},
                error_message="metadata unreadable",
            )
        )

        self.assertEqual(progress_events[-1]["processed_items"], 1)
        self.assertEqual(processed_files, [("broken.mp3", "failed")])
        self.assertEqual(errors, [("broken.mp3", "metadata unreadable")])

    def test_panel_updates_progress_and_error_list_from_adapter_events(self):
        panel = ImportManagerPanel(adapter=self.adapter)
        self.worker.emit(
            ImportEvent(
                "track_imported",
                job_id=5,
                filepath="music/ready.wav",
                progress={"status": "imported", "total_items": 3, "processed_items": 2, "error_count": 0},
            )
        )
        self.worker.emit(
            ImportEvent(
                "failed",
                job_id=5,
                filepath="music/broken.mp3",
                progress={"status": "imported", "total_items": 3, "processed_items": 3, "error_count": 1},
                error_message="invalid audio",
            )
        )
        self.application.processEvents()

        self.assertEqual(panel.progress_bar.maximum(), 3)
        self.assertEqual(panel.progress_bar.value(), 3)
        self.assertIn("3 / 3", panel.progress_label.text())
        self.assertEqual(panel.processed_files.count(), 2)
        self.assertEqual(panel.errors.count(), 1)
        panel.close()

    def test_cancellation_from_panel_delegates_only_to_adapter_worker(self):
        panel = ImportManagerPanel(adapter=self.adapter)
        panel.folder_input.setText("music")

        panel.start_import()
        panel.cancel_import()

        self.assertEqual(self.worker.started_paths, ["music"])
        self.assertEqual(self.worker.cancel_calls, 1)
        self.assertIn("Cancelación", panel.status_label.text())
        panel.close()

    def test_panel_loads_history_detail_and_requests_recovery_through_adapter(self):
        panel = ImportManagerPanel(adapter=self.adapter)
        self.application.processEvents()

        self.assertEqual(panel.history.count(), 1)
        panel.history.setCurrentRow(0)
        self.application.processEvents()
        self.assertIn("invalid audio", panel.job_detail_label.text())

        panel.recover_incomplete_jobs()

        self.assertEqual(self.facade.recovery_calls, 1)
        self.assertIn("No hay trabajos", panel.status_label.text())
        panel.close()
