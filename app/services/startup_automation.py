"""Safe, non-blocking startup chores controlled by saved preferences."""

from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock, Thread

from .backup_restore_service import BackupRequestDTO
from .settings_service import SettingsService


class StartupAutomationService:
    """Starts only local, reversible startup work; it never changes audio files."""

    def __init__(self, settings_service, backup_service, import_adapter, automatic_metadata_service=None, automatic_analysis_service=None, directory_exists=None, logger=None):
        if not isinstance(settings_service, SettingsService):
            raise TypeError("StartupAutomationService requiere SettingsService.")
        self._settings = settings_service
        self._backup = backup_service
        self._import_adapter = import_adapter
        self._automatic_metadata = automatic_metadata_service
        self._automatic_analysis = automatic_analysis_service
        self._directory_exists = directory_exists or (lambda value: Path(value).is_dir())
        self._logger = logger or logging.getLogger("djplus.automation")
        self._backup_thread = None
        self._metadata_thread = None
        self._analysis_thread = None
        self._automation_lock = Lock()
        self._post_import_pending = False
        completed_signal = getattr(self._import_adapter, "import_completed", None)
        if completed_signal is not None and callable(getattr(completed_signal, "connect", None)):
            completed_signal.connect(self._run_post_import_automation)

    def start(self):
        """Schedule enabled jobs and return their names without blocking the UI."""
        configuration = self._settings.get()
        started = []
        if configuration.backup.auto_backup_enabled:
            self._backup_thread = Thread(target=self._run_backup_and_maintenance, daemon=True, name="djplus-startup-backup")
            self._backup_thread.start()
            started.append("backup")
        started.extend(self._start_metadata_and_analysis())
        folder = configuration.library.default_music_path
        if configuration.library.scan_on_start and folder and self._directory_exists(folder):
            try:
                self._import_adapter.start(folder)
                started.append("scan")
            except (RuntimeError, ValueError) as error:
                self._logger.warning("Automatic scan was not started", extra={"event_name": "automatic_scan_skipped", "component": "automation", "context": {"exception_type": type(error).__name__}})
        return tuple(started)

    def _run_post_import_automation(self):
        with self._automation_lock:
            if self._thread_running(self._metadata_thread) or self._thread_running(self._analysis_thread):
                self._post_import_pending = True
                return
        self._start_metadata_and_analysis()

    def _start_metadata_and_analysis(self):
        configuration = self._settings.get()
        started = []
        if configuration.library.auto_external_metadata_enabled and self._automatic_metadata is not None and not self._thread_running(self._metadata_thread):
            self._metadata_thread = Thread(target=self._run_external_metadata, daemon=True, name="djplus-automatic-metadata")
            self._metadata_thread.start()
            started.append("metadata")
        if configuration.analysis.auto_analysis_enabled and self._automatic_analysis is not None and not self._thread_running(self._analysis_thread):
            self._analysis_thread = Thread(target=self._run_analysis, daemon=True, name="djplus-automatic-analysis")
            self._analysis_thread.start()
            started.append("analysis")
        return started

    @staticmethod
    def _thread_running(thread):
        return thread is not None and thread.is_alive()

    def _run_backup_and_maintenance(self):
        try:
            result = self._backup.create_backup(BackupRequestDTO(reason="automatic", operation_id="startup"))
            if result.success:
                self._backup.apply_retention(protected_paths=(result.backup_path,))
        except Exception as error:  # Startup automation must never prevent DJPlus from opening.
            self._logger.warning("Automatic backup failed", exc_info=True, extra={"event_name": "automatic_backup_failed", "component": "automation", "context": {"exception_type": type(error).__name__}})

    def _run_external_metadata(self):
        try:
            self._automatic_metadata.run()
        except Exception as error:
            self._logger.warning("Automatic external metadata failed", exc_info=True, extra={"event_name": "automatic_metadata_failed", "component": "automation", "context": {"exception_type": type(error).__name__}})
        finally:
            self._post_work_finished("metadata")

    def _run_analysis(self):
        try:
            self._automatic_analysis.run()
        except Exception as error:
            self._logger.warning("Automatic analysis failed", exc_info=True, extra={"event_name": "automatic_analysis_failed", "component": "automation", "context": {"exception_type": type(error).__name__}})
        finally:
            self._post_work_finished("analysis")

    def _post_work_finished(self, kind):
        with self._automation_lock:
            metadata_running = kind != "metadata" and self._thread_running(self._metadata_thread)
            analysis_running = kind != "analysis" and self._thread_running(self._analysis_thread)
            if not self._post_import_pending or metadata_running or analysis_running:
                return
            self._post_import_pending = False
        self._start_metadata_and_analysis()
