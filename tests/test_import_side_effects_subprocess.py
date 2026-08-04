"""Regression smoke tests for import-time side effects at backend boundaries."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ImportSideEffectsSubprocessTests(unittest.TestCase):
    """Imports run in a fresh process so global engines and hooks cannot mask writes."""

    def _run_clean_process(self, arguments):
        project = Path(__file__).resolve().parents[1]
        environment = os.environ.copy()
        environment.update({
            "PYTHONPATH": str(project),
            "PYTHONDONTWRITEBYTECODE": "1",
            "QT_QPA_PLATFORM": "offscreen",
        })
        return subprocess.run(
            [sys.executable, *arguments], cwd=project, env=environment,
            capture_output=True, text=True, timeout=45,
        )

    def test_track_repository_imports_in_a_clean_process(self):
        completed = self._run_clean_process([
            "-c", "from app.repository.track_repository import TrackRepository; assert TrackRepository",
        ])
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_library_service_then_track_repository_imports_in_a_clean_process(self):
        completed = self._run_clean_process([
            "-c", "from app.services.library_service import LibraryService; from app.repository.track_repository import TrackRepository",
        ])
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_track_repository_then_library_service_imports_in_a_clean_process(self):
        completed = self._run_clean_process([
            "-c", "from app.repository.track_repository import TrackRepository; from app.services.library_service import LibraryService",
        ])
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_global_ranking_sqlite_loads_in_an_isolated_process(self):
        completed = self._run_clean_process([
            "-m", "unittest", "discover", "-s", "tests", "-p", "test_global_ranking_sqlite.py", "-v",
        ])
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_boundary_imports_do_not_create_configuration_or_database_files(self):
        project = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="djplus-import-smoke-") as temporary:
            root = Path(temporary)
            working_directory = root / "working"
            appdata = root / "appdata"
            working_directory.mkdir()
            appdata.mkdir()
            environment = os.environ.copy()
            environment.update({
                "APPDATA": str(appdata),
                "LOCALAPPDATA": str(appdata),
                "XDG_CONFIG_HOME": str(appdata),
                "PYTHONPATH": str(project),
                "PYTHONDONTWRITEBYTECODE": "1",
                "QT_QPA_PLATFORM": "offscreen",
            })
            code = """
import importlib
import os
modules = (
    'app.config', 'app.database', 'app.database.database', 'app.services',
    'app.services.settings_service', 'app.services.app_logging_service',
    'app.services.backup_restore_service', 'app.ui.main_window',
    'app.gui', 'app.library', 'app.scanner',
)
for name in modules:
    importlib.import_module(name)
created = []
for directory, _children, files in os.walk('.'):
    created.extend(os.path.normpath(os.path.join(directory, name)) for name in files)
print('\\n'.join(sorted(created)))
"""
            completed = subprocess.run(
                [sys.executable, "-c", code], cwd=working_directory, env=environment,
                capture_output=True, text=True, timeout=45,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(completed.stdout.strip(), "")
            self.assertEqual(list(appdata.rglob("*")), [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
