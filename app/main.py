import sys

from PySide6.QtWidgets import QApplication

try:
    from .database import init_database
    from .ui.main_window import MainWindow
    from .ui.styles import apply_global_stylesheet
    from .services.settings_service import SettingsService
    from .services.app_logging_service import AppLoggingService
    from .services.history_service import HistoryService
    from .services.preview_player import HistoryPlaybackPortAdapter, create_preview_player_service
except ImportError:  # pragma: no cover - fallback for direct execution
    from app.database import init_database
    from app.ui.main_window import MainWindow
    from app.ui.styles import apply_global_stylesheet
    from app.services.settings_service import SettingsService
    from app.services.app_logging_service import AppLoggingService
    from app.services.history_service import HistoryService
    from app.services.preview_player import HistoryPlaybackPortAdapter, create_preview_player_service


def main():
    settings = SettingsService()
    configuration = settings.load()
    logging_service = AppLoggingService(configuration.logging)
    logging_service.install_exception_hooks()
    logger = logging_service.get_logger("ui")
    preview_player = None
    history_service = None
    try:
        init_database()
        logger.info("Application started", extra={"event_name": "application_started", "component": "ui"})
        app = QApplication(sys.argv)
        apply_global_stylesheet(app)
        history_service = HistoryService()
        preview_player = create_preview_player_service(
            logger=logging_service.get_logger("preview"), settings_service=settings,
            history_port=HistoryPlaybackPortAdapter(history_service),
        )
        window = MainWindow(preview_player_service=preview_player)
        window.show()
        return app.exec()
    finally:
        if preview_player is not None:
            preview_player.close()
        if history_service is not None:
            history_service.close()
        logger.info("Application shutdown", extra={"event_name": "application_shutdown", "component": "ui"})
        logging_service.shutdown()


if __name__ == "__main__":
    sys.exit(main())
