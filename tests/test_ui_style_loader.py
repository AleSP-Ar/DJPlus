import tempfile
import unittest
from pathlib import Path

from app.ui.styles import (
    GlobalStyleSheetError,
    apply_global_stylesheet,
    global_stylesheet_path,
    load_global_stylesheet,
)


class FakeApplication:
    def __init__(self) -> None:
        self.stylesheet = None

    def setStyleSheet(self, stylesheet: str) -> None:
        self.stylesheet = stylesheet


class TestUIStyleLoader(unittest.TestCase):
    def test_default_qss_file_exists_and_loads_non_empty_content(self) -> None:
        path = global_stylesheet_path()
        content = load_global_stylesheet(path)
        self.assertIsInstance(content, str)
        self.assertTrue(content.strip())

    def test_apply_global_stylesheet_calls_setStyleSheet_with_loaded_styles(self) -> None:
        path = global_stylesheet_path()
        fake_app = FakeApplication()

        returned = apply_global_stylesheet(fake_app, path)
        self.assertEqual(fake_app.stylesheet, returned)
        self.assertIsInstance(fake_app.stylesheet, str)
        self.assertTrue(fake_app.stylesheet.strip())

    def test_load_global_stylesheet_raises_when_file_missing(self) -> None:
        missing_path = Path(tempfile.gettempdir()) / "this_file_does_not_exist_1234567890.qss"
        with self.assertRaises(GlobalStyleSheetError):
            load_global_stylesheet(missing_path)

    def test_load_global_stylesheet_raises_when_file_is_empty(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".qss", delete=False, mode="w", encoding="utf-8") as temp_file:
            empty_path = Path(temp_file.name)
        try:
            with self.assertRaises(GlobalStyleSheetError):
                load_global_stylesheet(empty_path)
        finally:
            empty_path.unlink(missing_ok=True)

    def test_app_ui_styles_exposes_expected_symbols(self) -> None:
        import app.ui.styles as styles_package

        for symbol_name in (
            "GlobalStyleSheetError",
            "apply_global_stylesheet",
            "global_stylesheet_path",
            "load_global_stylesheet",
        ):
            self.assertTrue(
                hasattr(styles_package, symbol_name),
                f"app.ui.styles no expone {symbol_name}",
            )

        self.assertEqual(
            sorted(styles_package.__all__),
            sorted([
                "GlobalStyleSheetError",
                "apply_global_stylesheet",
                "global_stylesheet_path",
                "load_global_stylesheet",
            ]),
        )


if __name__ == "__main__":
    unittest.main()
