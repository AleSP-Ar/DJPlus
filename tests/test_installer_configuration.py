import unittest
from pathlib import Path


class InstallerConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        self.iss = (self.root / "installer" / "DJPlus.iss").read_text(encoding="utf-8")
        self.build_script = (self.root / "tools" / "build_installer_windows.ps1").read_text(encoding="utf-8")
        self.smoke_script = (self.root / "tools" / "smoke_installer_windows.ps1").read_text(encoding="utf-8")
        self.doc = (self.root / "docs" / "distribution" / "INSTALLER_TESTING.md").read_text(encoding="utf-8")
        self.gitignore = (self.root / ".gitignore").read_text(encoding="utf-8")

    def test_gitignore_ignores_installer_output(self):
        self.assertIn("installer-output/", self.gitignore)

    def test_installer_script_has_expected_settings(self):
        self.assertIn("AppId={{A2C94B17-0E0F-48E1-A351-79A8B0F8B3C2}}", self.iss)
        self.assertIn("DefaultDirName={localappdata}\\Programs\\DJPlus", self.iss)
        self.assertIn("[Tasks]", self.iss)
        self.assertIn("[Icons]", self.iss)
        self.assertIn("Source: \"..\\dist\\DJPlus\\*\"; DestDir: \"{app}\"; Flags: recursesubdirs createallsubdirs", self.iss)

    def test_installer_build_script_validates_ffmpeg_and_installer(self):
        for expected in (
            "ISCC.exe",
            "dist\\DJPlus",
            "runtime/ffmpeg",
            "CHECKSUM.sha256",
            "ffmpeg.exe",
            "installer-output",
        ):
            self.assertIn(expected, self.build_script)

    def test_smoke_installer_script_validates_user_data_and_sqlite(self):
        for expected in (
            "DJPLUS_USER_DATA_DIR",
            "PRAGMA integrity_check",
            "schema_migrations",
            "CloseMainWindow",
            "unins000.exe",
        ):
            self.assertIn(expected, self.smoke_script)

    def test_installer_testing_document_exists_and_describes_build(self):
        self.assertIn("installer-output\\DJPlus-Setup-1.0.0-rc1.exe", self.doc)
        self.assertIn(".\\tools\\build_installer_windows.ps1", self.doc)
        self.assertIn(".\\tools\\smoke_installer_windows.ps1", self.doc)
