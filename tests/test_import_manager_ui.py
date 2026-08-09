import os
import tempfile
import unittest
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qt_test_helpers import ensure_qapplication
from app.services.import_events import ImportEvent
from app.services.import_manager_facade import ImportJobSummary
from app.services.settings_service import SettingsService
from app.ui.import_manager_adapter import ImportManagerAdapter
from app.ui.import_manager_panel import ImportManagerPanel


class FakeImportWorker:
    def __init__(self): self.callbacks = []; self.started_paths = []; self.cancel_calls = 0; self.is_running = False
    def subscribe(self, callback): self.callbacks.append(callback)
    def start(self, folder_path): self.started_paths.append(folder_path); self.is_running = True; return object()
    def cancel(self): self.cancel_calls += 1
    def emit(self, event):
        for callback in self.callbacks: callback(event)


class FakeImportManagerFacade:
    def __init__(self): self.jobs = [ImportJobSummary(7, "completed", datetime(2026, 8, 9), None, datetime(2026, 8, 9), 2, 2, 0)]
    def list_jobs(self, limit=100): return tuple(self.jobs[:limit])
    def close(self): pass


class ImportManagerUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.application = ensure_qapplication()

    def setUp(self):
        self.worker = FakeImportWorker(); self.facade = FakeImportManagerFacade()
        self.adapter = ImportManagerAdapter(worker=self.worker, facade=self.facade)

    def tearDown(self): self.application.processEvents()

    def test_adapter_emits_completion_for_post_import_automation(self):
        completed = []; self.adapter.import_completed.connect(lambda: completed.append(True))
        self.worker.emit(ImportEvent("completed", job_id=4, progress={"status": "completed", "total_items": 1, "processed_items": 1}))
        self.assertEqual(completed, [True])

    def test_panel_keeps_progress_and_only_shows_duplicate_summary(self):
        panel = ImportManagerPanel(adapter=self.adapter)
        self.worker.emit(ImportEvent("track_imported", job_id=5, filepath="music/ready.wav", progress={"status": "running", "total_items": 3, "processed_items": 2}))
        self.worker.emit(ImportEvent("skipped", job_id=5, filepath="music/known.mp3", progress={"status": "running", "total_items": 3, "processed_items": 3}))
        self.application.processEvents()
        self.assertEqual(panel.progress_bar.maximum(), 3); self.assertEqual(panel.progress_bar.value(), 3)
        self.assertIn("3 / 3", panel.progress_label.text())
        self.assertFalse(panel.duplicate_summary_label.isHidden())
        self.assertIn("1 archivo repetido", panel.duplicate_summary_label.text())
        self.assertFalse(hasattr(panel, "processed_files")); self.assertFalse(hasattr(panel, "history"))
        self.assertIn("09/08/2026", panel.last_import_summary_label.text()); panel.close()

    def test_cancellation_from_panel_delegates_only_to_adapter_worker(self):
        panel = ImportManagerPanel(adapter=self.adapter); panel.folder_input.setText("music")
        panel.start_import(); panel.cancel_import()
        self.assertEqual(self.worker.started_paths, ["music"]); self.assertEqual(self.worker.cancel_calls, 1)
        panel.close()

    def test_panel_saves_only_explicitly_confirmed_default_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = SettingsService(os.path.join(directory, "config.json"))
            panel = ImportManagerPanel(adapter=self.adapter, settings_service=settings)
            folder = os.path.join(directory, "music"); panel.folder_input.setText(folder)
            self.assertIsNone(settings.get().library.default_music_path); panel.save_default_folder()
            self.assertEqual(settings.get().library.default_music_path, folder)
            self.assertIn("Predeterminada", panel.default_folder_combo.currentText())
            panel.close()
