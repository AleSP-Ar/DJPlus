import sys

from PySide6.QtWidgets import QApplication

try:
    from .database import init_database
    from .services.app_logging_service import AppLoggingService
    from .services.history_service import HistoryService
    from .services.library_service import LibraryService
    from .services.global_ranking_factory import create_global_recommendation_facade
    from .services.settings_service import SettingsService
    from .services.preview_player import HistoryPlaybackPortAdapter, create_preview_player_service
    from .ui.intelligence_panel import LocalIntelligencePanel
    from .ui.library_view import LibraryView
    from .ui.main_window import MainWindow, MainWindowDependencies
    from .ui.styles import apply_global_stylesheet
except ImportError:  # pragma: no cover - fallback for direct execution
    from app.database import init_database
    from app.services.app_logging_service import AppLoggingService
    from app.services.history_service import HistoryService
    from app.services.library_service import LibraryService
    from app.services.global_ranking_factory import create_global_recommendation_facade
    from app.services.settings_service import SettingsService
    from app.services.preview_player import HistoryPlaybackPortAdapter, create_preview_player_service
    from app.ui.intelligence_panel import LocalIntelligencePanel
    from app.ui.library_view import LibraryView
    from app.ui.main_window import MainWindow, MainWindowDependencies
    from app.ui.styles import apply_global_stylesheet

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
        library_service = LibraryService()
        history_service = HistoryService()
        library_view = LibraryView(library_service, history_service, settings)
        recommendation_facade = create_global_recommendation_facade(library_service, history_service)
        intelligence_panel = LocalIntelligencePanel(recommendation_facade, library_view=library_view, settings_service=settings)
        preview_player = create_preview_player_service(
            logger=logging_service.get_logger("preview"), settings_service=settings,
            history_port=HistoryPlaybackPortAdapter(history_service),
        )
        window = MainWindow(
            preview_player_service=preview_player,
            dependencies=MainWindowDependencies(
                library_view=library_view,
                assistant_panel=intelligence_panel,
            ),
        )
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
