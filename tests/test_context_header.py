import unittest

from app.ui.widgets import ContextHeader
from qt_test_helpers import ensure_qapplication


class ContextHeaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = ensure_qapplication()

    def setUp(self):
        self.header = ContextHeader()

    def tearDown(self):
        self.header.close()

    def test_creates_expected_labels(self):
        self.assertEqual(self.header.appTitle.text(), "DJPlus")
        self.assertEqual(self.header.appSubtitle.text(), "Biblioteca musical")
        self.assertEqual(self.header.page_title_label.text(), "")

    def test_labels_have_expected_object_names(self):
        self.assertEqual(self.header.appTitle.objectName(), "appTitle")
        self.assertEqual(self.header.appSubtitle.objectName(), "appSubtitle")
        self.assertEqual(self.header.page_title_label.objectName(), "pageTitle")

    def test_set_page_title_updates_page_title_only(self):
        self.header.set_page_title("Test Section")
        self.assertEqual(self.header.page_title_label.text(), "Test Section")
        self.assertEqual(self.header.appTitle.text(), "DJPlus")
        self.assertEqual(self.header.appSubtitle.text(), "Biblioteca musical")

    def test_does_not_install_local_stylesheet(self):
        self.assertFalse(self.header.styleSheet())

    def test_layout_hierarchy_is_valid(self):
        layout = self.header.layout()
        self.assertIsNotNone(layout)
        self.assertEqual(layout.count(), 3)
        self.assertIsNotNone(layout.itemAt(0).layout())
        self.assertIsNotNone(layout.itemAt(2).widget())
        self.assertIs(layout.itemAt(2).widget(), self.header.page_title_label)

    def test_accessible_names_are_provided(self):
        self.assertTrue(self.header.appTitle.accessibleName())
        self.assertTrue(self.header.appSubtitle.accessibleName())
        self.assertTrue(self.header.page_title_label.accessibleName())

    def test_works_without_main_window_or_services(self):
        self.assertIsNotNone(self.header)
        self.header.set_page_title("Standalone")
        self.assertEqual(self.header.page_title_label.text(), "Standalone")


if __name__ == "__main__":
    unittest.main()
