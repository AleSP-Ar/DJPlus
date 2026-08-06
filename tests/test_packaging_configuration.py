import json
from pathlib import Path
import unittest


class PackagingConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]

    def test_manifest_declares_runtime_and_excludes_mutable_development_content(self):
        manifest = json.loads((self.root / "packaging" / "included-files.json").read_text(encoding="utf-8"))
        self.assertIn("runtime/ffmpeg/ffmpeg.exe", manifest["included"])
        self.assertTrue({"tests", "data", ".venv", "*.db", "*.sqlite"}.issubset(manifest["excluded"]))

    def test_spec_and_script_are_relative_and_validate_required_ffmpeg_files(self):
        spec = (self.root / "packaging" / "DJPlus.spec").read_text(encoding="utf-8")
        script = (self.root / "tools" / "build_windows.ps1").read_text(encoding="utf-8")
        self.assertIn("Path(SPECPATH).parent", spec)
        self.assertIn("runtime/ffmpeg", spec)
        self.assertNotIn("collect_all(\"PySide6\")", spec)
        self.assertIn("official PySide6 hooks", spec)
        self.assertIn("Remove-Item -LiteralPath $target -Recurse -Force", script)
        self.assertIn("checksum", script.casefold())
        self.assertNotIn("D:\\", spec + script)

    def test_smoke_script_and_desktop_guide_cover_clean_artifact_validation(self):
        smoke = (self.root / "tools" / "smoke_artifact_windows.ps1").read_text(encoding="utf-8")
        guide = (self.root / "docs" / "distribution" / "WINDOWS_DESKTOP_VALIDATION.md").read_text(encoding="utf-8")
        for expected in (
            "DJPLUS_USER_DATA_DIR", "DJPlus.exe", "CHECKSUM.sha256",
            "PRAGMA integrity_check", "schema_migrations", "PYTHONPATH",
            "PYTHONHOME", "VIRTUAL_ENV", "Assert-ArtifactHasNoMutableData",
        ):
            self.assertIn(expected, smoke)
        for expected in ("Biblioteca", "Colecciones", "Playlists", "Importar", "Metadata", "Assistant", "Diagnóstico", "MP3", "FLAC", "AIFF", "WAV"):
            self.assertIn(expected, guide)
    def test_spec_bundles_global_stylesheet(self):
        spec = (self.root / "packaging" / "DJPlus.spec").read_text(encoding="utf-8")
        self.assertIn("app.qss", spec)
        self.assertIn("app/ui/styles", spec)
