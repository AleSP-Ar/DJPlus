import unittest

from PySide6.QtWidgets import QApplication

from qt_test_helpers import IncompatibleQtApplicationError, ensure_qapplication


class _CoreOnlyApplication:
    pass


class _FakeQApplication:
    pass


class QtTestHelperTests(unittest.TestCase):
    def test_creates_qapplication_when_no_qt_application_exists(self):
        created = []

        def factory(_arguments):
            app = _FakeQApplication()
            created.append(app)
            return app

        result = ensure_qapplication(
            instance_getter=lambda: None,
            application_factory=factory,
            application_type=_FakeQApplication,
        )

        self.assertIs(result, created[0])

    def test_reuses_existing_qapplication(self):
        existing = _FakeQApplication()

        result = ensure_qapplication(
            instance_getter=lambda: existing,
            application_factory=lambda _arguments: self.fail("No debe crear otra aplicación."),
            application_type=_FakeQApplication,
        )

        self.assertIs(result, existing)

    def test_rejects_incompatible_qcoreapplication_before_widget_creation(self):
        with self.assertRaises(IncompatibleQtApplicationError):
            ensure_qapplication(
                instance_getter=_CoreOnlyApplication,
                application_factory=lambda _arguments: self.fail("No debe reemplazar la instancia existente."),
                application_type=_FakeQApplication,
            )

    def test_backend_then_preview_bar_fixture_uses_a_real_qapplication(self):
        from test_preview_player_bar import PreviewPlayerBarTests
        from test_qt_multimedia_playback_backend import QtMultimediaPlaybackBackendTests

        QtMultimediaPlaybackBackendTests.setUpClass()
        PreviewPlayerBarTests.setUpClass()
        self.assertIsInstance(QtMultimediaPlaybackBackendTests.application, QApplication)
        self.assertIsInstance(PreviewPlayerBarTests.app, QApplication)

        case = PreviewPlayerBarTests("test_time_format_and_empty_or_degraded_states")
        case.setUp()
        try:
            self.assertIsNotNone(case.bar)
        finally:
            case.tearDown()

    def test_preview_bar_then_backend_fixture_uses_the_same_qapplication(self):
        from test_preview_player_bar import PreviewPlayerBarTests
        from test_qt_multimedia_playback_backend import QtMultimediaPlaybackBackendTests

        PreviewPlayerBarTests.setUpClass()
        application = PreviewPlayerBarTests.app
        QtMultimediaPlaybackBackendTests.setUpClass()
        self.assertIs(application, QtMultimediaPlaybackBackendTests.application)
