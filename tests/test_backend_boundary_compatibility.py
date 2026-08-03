import importlib
import unittest
import warnings

from app.services import AudioFileMusicAnalysisService, ProviderMusicAnalysisService
from app.services.assistant_facade import DJCompatibilityTool, LegacyDJCompatibilityTool, LegacyLibraryQueryTool, LibraryQueryTool
from app.services.music_analysis_service import MusicAnalysisService


class BackendBoundaryCompatibilityTests(unittest.TestCase):
    def test_analysis_public_names_preserve_provider_compatibility(self):
        self.assertIs(MusicAnalysisService, ProviderMusicAnalysisService)
        self.assertNotEqual(AudioFileMusicAnalysisService, ProviderMusicAnalysisService)

    def test_legacy_tool_names_remain_compatible_aliases(self):
        self.assertIs(LibraryQueryTool, LegacyLibraryQueryTool)
        self.assertIs(DJCompatibilityTool, LegacyDJCompatibilityTool)

    def test_legacy_modules_remain_importable_with_deprecation_notice(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            for name in ("app.library", "app.scanner", "app.gui"):
                importlib.reload(importlib.import_module(name))
        self.assertGreaterEqual(sum(item.category is DeprecationWarning for item in caught), 3)

    def test_config_module_is_importable_without_a_second_settings_api(self):
        module = importlib.import_module("app.config")
        self.assertIn("configuration", module.__doc__.casefold())
