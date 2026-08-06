import unittest

from qt_test_helpers import ensure_qapplication

from app.ui.widgets.navigation_sidebar import NavigationSidebar


class NavigationSidebarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = ensure_qapplication()

    def setUp(self):
        self.sections = [
            ("a", "A"),
            ("b", "B"),
            ("c", "C"),
        ]

    def test_creates_button_per_section_and_preserves_order(self):
        nav = NavigationSidebar(self.sections)
        try:
            self.assertEqual(list(nav.buttons.keys()), [k for k, _ in self.sections])
            self.assertEqual([btn.text() for btn in nav.buttons.values()], [l for _, l in self.sections])
        finally:
            nav.close()

    def test_buttons_are_checkable_and_named(self):
        nav = NavigationSidebar(self.sections)
        try:
            for key, btn in nav.buttons.items():
                self.assertTrue(btn.isCheckable())
                self.assertEqual(btn.objectName(), f"navigation_{key}")
        finally:
            nav.close()

    def test_click_emits_section_requested(self):
        nav = NavigationSidebar(self.sections)
        try:
            recorded = []

            def on_requested(k):
                recorded.append(k)

            nav.section_requested.connect(on_requested)
            # click second button
            nav.buttons["b"].click()
            self.assertEqual(recorded, ["b"])
        finally:
            nav.close()

    def test_set_current_section_marks_only_one(self):
        nav = NavigationSidebar(self.sections)
        try:
            nav.set_current_section("c")
            self.assertTrue(nav.buttons["c"].isChecked())
            self.assertFalse(nav.buttons["a"].isChecked())
        finally:
            nav.close()

    def test_set_current_section_invalid_raises(self):
        nav = NavigationSidebar(self.sections)
        try:
            with self.assertRaises(ValueError):
                nav.set_current_section("invalid")
        finally:
            nav.close()

    def test_component_does_not_install_local_stylesheet(self):
        nav = NavigationSidebar(self.sections)
        try:
            self.assertFalse(nav.styleSheet())
        finally:
            nav.close()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
