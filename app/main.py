import sys

from PySide6.QtWidgets import QApplication

try:
    from .database import init_database
    from .ui.main_window import MainWindow
    from .services.settings_service import SettingsService
    from .services.app_logging_service import AppLoggingService
except ImportError:  # pragma: no cover - fallback for direct execution
    from app.database import init_database
    from app.ui.main_window import MainWindow
    from app.services.settings_service import SettingsService
    from app.services.app_logging_service import AppLoggingService


def main():
    settings = SettingsService()
    logging_service = AppLoggingService(settings.load().logging)
    logging_service.install_exception_hooks()
    logger = logging_service.get_logger("ui")
    try:
        init_database()
        logger.info("Application started", extra={"event_name": "application_started", "component": "ui"})
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        return app.exec()
    finally:
        logger.info("Application shutdown", extra={"event_name": "application_shutdown", "component": "ui"})
        logging_service.shutdown()


if __name__ == "__main__":
    sys.exit(main())
