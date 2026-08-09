import unittest

from app.services.key_notation import format_key, normalize_key
from app.services.settings_service import LibrarySettingsDTO, SettingsValidationError


class KeyNotationTests(unittest.TestCase):
    def test_recognized_camelot_and_musical_keys_are_equivalent(self):
        self.assertEqual(normalize_key("8A"), ("8A", "A minor"))
        self.assertEqual(normalize_key("a min"), ("8A", "A minor"))
        self.assertEqual(normalize_key("C major"), ("8B", "C major"))

    def test_formats_key_in_each_user_display_mode(self):
        self.assertEqual(format_key("8A", "camelot"), "8A")
        self.assertEqual(format_key("A minor", "musical"), "A minor")
        self.assertEqual(format_key("A minor", "both"), "8A · A minor")
        self.assertEqual(format_key("custom key", "both"), "custom key")

    def test_key_notation_preference_is_validated(self):
        self.assertEqual(LibrarySettingsDTO(key_notation="camelot").key_notation, "camelot")
        with self.assertRaises(SettingsValidationError):
            LibrarySettingsDTO(key_notation="invalid")
