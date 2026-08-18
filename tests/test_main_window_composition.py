"""Headless composition seam coverage without the process-global library DB."""

import sqlite3
import tempfile
import threading
import unittest
from unittest import mock
from pathlib import Path

from PySide6.QtWidgets import QWidget
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.migrations import run_migrations
from app.services.history_service import HistoryService
from app.services.library_service import LibraryService
from app.services.preview_player import DeterministicPlaybackBackend, PreviewPlayerService
from app.services.app_logging_service import AppLoggingService
from app.services.backup_restore_service import BackupRestoreService
from app.services.database_migration_coordinator import DatabaseMigrationCoordinator
from app.services.settings_service import LoggingSettingsDTO, SettingsService
from app.repository.history_repository import HistoryRepository
from app.repository.track_repository import TrackRepository
from app.ui.library_view import LibraryView
from app.ui.main_window import MainWindow, MainWindowDependencies
from qt_test_helpers import ensure_qapplication


class _Panel(QWidget):
    pass


class MainWindowCompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = ensure_qapplication()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="djplus-main-window-")
        self.path = Path(self.temporary.name) / "library.sqlite"
        self.engine = create_engine(f"sqlite:///{self.path.as_posix()}")
        run_migrations(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.temporary.cleanup()

    def _injected_window(self):
        library_service = LibraryService(TrackRepository(self.session_factory()))
        history_service = HistoryService(HistoryRepository(self.session_factory()))
        library_view = LibraryView(library_service, history_service)
        player = PreviewPlayerService(DeterministicPlaybackBackend())
        dependencies = MainWindowDependencies(
            library_view=library_view,
            collection_panel=_Panel(),
            playlist_panel=_Panel(),
            import_panel=_Panel(),
            track_metadata_panel=_Panel(),
        )
        return MainWindow(preview_player_service=player, dependencies=dependencies), library_view, player

    def test_injected_composition_uses_existing_services_once_and_closes_them(self):
        window, library_view, player = self._injected_window()
        with mock.patch.object(library_view.library_service, "close", wraps=library_view.library_service.close) as close_library:
            try:
                self.assertIs(window.library_view, library_view)
                self.assertIs(window.library_view.library_service, library_view.library_service)
                rows, has_more = window.library_view.library_service.load_library()
                self.assertEqual((rows, has_more), ([], False))
                self.assertIsNotNone(window.preview_player_bar)
            finally:
                window.close()
                window.close()
            self.assertEqual(close_library.call_count, 1)
        self.assertTrue(player._closed)

    def test_main_window_does_not_install_local_stylesheet(self):
        """Ensure MainWindow relies on global QSS and does not install a local stylesheet."""
        window, _, _ = self._injected_window()
        try:
            # window.styleSheet() returns the widget-local stylesheet; expect empty
            self.assertFalse(window.styleSheet())
        finally:
            window.close()

    def test_constructor_remains_compatible_and_rejects_invalid_dependencies(self):
        with self.assertRaises(TypeError):
            MainWindow(dependencies=object())
        # Existing one-argument construction remains available; the canonical
        # global DB is initialized by the established headless UI tests.
        self.assertEqual(MainWindow.__init__.__defaults__, (None, None))

    def test_navigation_switches_existing_workspaces_and_keeps_preview_persistent(self):
        window, library_view, player = self._injected_window()
        try:
            self.assertEqual(window.current_section, "library")
            self.assertIs(window.workspace_stack.currentWidget(), library_view)
            self.assertEqual(window.workspace_stack.indexOf(window.preview_player_bar), -1)

            for section, label in MainWindow.SECTIONS:
                previous_bar = window.preview_player_bar
                window.navigation_buttons[section].click()
                self.assertEqual(window.current_section, section)
                self.assertEqual(window.page_title_label.text(), label)
                self.assertTrue(window.navigation_buttons[section].isChecked())
                self.assertIsNotNone(window.workspace_stack.currentWidget())
                self.assertIsNotNone(window.preview_player_bar)
                self.assertIs(window.preview_player_bar, previous_bar)
                self.assertEqual(window.workspace_stack.indexOf(window.preview_player_bar), -1)
        finally:
            window.close()
        self.assertTrue(player._closed)

    def test_navigation_compacts_without_losing_accessibility_in_a_narrow_window(self):
        window, _, _ = self._injected_window()
        try:
            window.resize(900, 560)
            window.show()
            self.app.processEvents()
            self.assertEqual(window.navigation_buttons["library"].text(), "B")
            self.assertEqual(window.navigation_buttons["dj_set"].text(), "DJ")
            self.assertEqual(window.navigation_buttons["dj_set"].accessibleName(), "Ir a DJ Set")
            self.assertEqual(window.navigation_buttons["dj_set"].toolTip(), "DJ Set")
            window.resize(1280, 800)
            self.app.processEvents()
            self.assertEqual(window.navigation_buttons["library"].text(), "Biblioteca")
        finally:
            window.close()

    def test_clean_isolated_lifecycle_uses_only_temporary_paths(self):
        """Exercise the real local boundaries without the global application DB."""
        before_threads = {thread.ident for thread in threading.enumerate()}
        with tempfile.TemporaryDirectory(prefix="djplus-clean-install-") as temporary:
            root = Path(temporary)
            settings = SettingsService(root / "appdata" / "DJPlus" / "config.json")
            config = settings.load()
            self.assertEqual(config.schema_version, 3)
            logging_service = AppLoggingService(LoggingSettingsDTO(directory=str(root / "logs")))
            try:
                database = root / "state" / "library.sqlite"
                database.parent.mkdir(parents=True)
                backup_service = BackupRestoreService(settings, database, logging_service.get_logger("backup"))
                coordinator = DatabaseMigrationCoordinator(database, backup_service, logger=logging_service.get_logger("database"))
                self.assertEqual(coordinator.prepare_database_for_startup().status, "MIGRATED")
                self.assertEqual(coordinator.prepare_database_for_startup().status, "CURRENT")
                engine = create_engine(f"sqlite:///{database.as_posix()}")
                sessions = sessionmaker(bind=engine)
                library = LibraryView(
                    LibraryService(TrackRepository(sessions())),
                    HistoryService(HistoryRepository(sessions())),
                )
                player = PreviewPlayerService(DeterministicPlaybackBackend(available=False, devices=()))
                dependencies = MainWindowDependencies(library, _Panel(), _Panel(), _Panel(), _Panel())
                window = MainWindow(preview_player_service=player, dependencies=dependencies)
                try:
                    self.assertEqual(window.library_view.library_service.load_library(), ([], False))
                    settings.update({"general": {"theme": "dark"}})
                    logging_service.get_logger("clean").info("clean lifecycle", extra={"event_name": "clean_lifecycle", "component": "test"})
                    logging_service.flush()
                    self.assertTrue(logging_service.get_current_log_file().is_file())
                    connection = sqlite3.connect(database)
                    try:
                        self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                        self.assertIsNone(connection.execute("PRAGMA foreign_key_check").fetchone())
                    finally:
                        connection.close()
                finally:
                    window.close(); window.close(); player.close()
                    engine.dispose()
            finally:
                logging_service.shutdown(); logging_service.shutdown()
            self.assertFalse(list(root.rglob("*.tmp")))
            self.assertFalse(list(root.rglob("*.restore")))
            self.assertFalse(list((root / "backups").glob("*.zip")) if (root / "backups").exists() else [])
        self.assertEqual(before_threads, {thread.ident for thread in threading.enumerate()})


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
