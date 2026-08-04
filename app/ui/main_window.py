from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
)
from dataclasses import dataclass

try:
    from .library_view import LibraryView
    from .collection_panel import CollectionPanel
    from .import_manager_panel import ImportManagerPanel
    from .playlist_panel import PlaylistPanel
    from .track_metadata_panel import TrackMetadataPanel
    from .widgets.preview_player_bar import PreviewPlayerBar
    from app.services.track_metadata_facade import TrackMetadataFacade
    from app.services.track_metadata_editor import TrackMetadataEditorService
    from app.services.action_pipeline import ActionPipeline
    from app.services.confirmation_manager import ConfirmationManager
    from app.services.duplicate_detection_service import DuplicateDetectionService
    from app.services.duplicate_detection_facade import DuplicateDetectionFacade
    from app.services.multi_format_audio_analysis_facade import MultiFormatAudioAnalysisFacade
    from app.services.preview_player import PreviewTrackDTO
except ImportError:  # pragma: no cover - fallback for direct execution
    from ui.library_view import LibraryView
    from ui.collection_panel import CollectionPanel
    from ui.import_manager_panel import ImportManagerPanel
    from ui.playlist_panel import PlaylistPanel
    from app.ui.track_metadata_panel import TrackMetadataPanel
    from app.ui.widgets.preview_player_bar import PreviewPlayerBar
    from app.services.track_metadata_facade import TrackMetadataFacade
    from app.services.track_metadata_editor import TrackMetadataEditorService
    from app.services.action_pipeline import ActionPipeline
    from app.services.confirmation_manager import ConfirmationManager
    from app.services.duplicate_detection_service import DuplicateDetectionService
    from app.services.duplicate_detection_facade import DuplicateDetectionFacade
    from app.services.multi_format_audio_analysis_facade import MultiFormatAudioAnalysisFacade
    from app.services.preview_player import PreviewTrackDTO


@dataclass(frozen=True)
class MainWindowDependencies:
    """Optional already-composed widgets for isolated lifecycle tests.

    Production leaves every field as ``None`` and retains the existing
    composition.  This is not a service container: it only replaces widget
    construction at the MainWindow boundary.
    """

    library_view: object | None = None
    collection_panel: object | None = None
    playlist_panel: object | None = None
    import_panel: object | None = None
    track_metadata_panel: object | None = None


class MainWindow(QMainWindow):
    def __init__(self, preview_player_service=None, dependencies=None):
        super().__init__()
        if dependencies is not None and not isinstance(dependencies, MainWindowDependencies):
            raise TypeError("dependencies requiere MainWindowDependencies.")
        self.preview_player_service = preview_player_service
        self._dependencies = dependencies or MainWindowDependencies()
        self._resources_closed = False

        self.setWindowTitle("DJPlus")
        self.resize(1000, 600)

        self.create_ui()

    def create_ui(self):
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("DJPlus - Music Library Manager")
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(title)

        content = QHBoxLayout()
        navigation = QVBoxLayout()
        library = self._dependencies.library_view or LibraryView()
        collections = self._dependencies.collection_panel or CollectionPanel()
        collections.setMaximumWidth(280)
        navigation.addWidget(collections)
        playlists = self._dependencies.playlist_panel or PlaylistPanel()
        playlists.setMaximumWidth(280)
        navigation.addWidget(playlists)
        imports = self._dependencies.import_panel or ImportManagerPanel()
        imports.setMaximumWidth(280)
        navigation.addWidget(imports)
        if self._dependencies.track_metadata_panel is not None:
            self.track_metadata_panel = self._dependencies.track_metadata_panel
            self.track_metadata_panel.setMaximumWidth(280)
            navigation.addWidget(self.track_metadata_panel)
        else:
            try:
                pipeline = ActionPipeline()
                editor = TrackMetadataEditorService(pipeline, ConfirmationManager(pipeline))
                self.track_metadata_panel = TrackMetadataPanel(TrackMetadataFacade(library.library_service, editor))
                self.track_metadata_panel.setMaximumWidth(280)
                navigation.addWidget(self.track_metadata_panel)
            except Exception:
                self.track_metadata_panel = None
        content.addLayout(navigation)

        self.library_view = library
        self.preview_player_bar = None
        if self.preview_player_service is not None:
            try:
                self.preview_player_bar = PreviewPlayerBar(self.preview_player_service, central)
                library.set_preview_player_available(True)
                library.preview_track_requested.connect(self.load_selected_track_in_preview)
            except Exception:
                self.preview_player_bar = None
        try:
            self.duplicate_detection_facade = DuplicateDetectionFacade(
                library.library_service,
                DuplicateDetectionService(library.library_service),
            )
        except Exception:
            # The integration is optional: an unavailable library must not prevent the UI from opening.
            self.duplicate_detection_facade = None
        try:
            self.multi_format_audio_analysis_facade = MultiFormatAudioAnalysisFacade(library.library_service)
        except Exception:
            # FFmpeg remains optional and an unavailable decoder must not prevent startup.
            self.multi_format_audio_analysis_facade = None
        content.addWidget(library, 1)
        layout.addLayout(content, 1)
        if self.preview_player_bar is not None:
            layout.addWidget(self.preview_player_bar)

        self.setCentralWidget(central)

    def load_selected_track_in_preview(self, track):
        """Adapt the selected model item without re-querying repository or media backend."""
        if self.preview_player_bar is None:
            return
        try:
            preview_track = PreviewTrackDTO(
                filepath=track.filepath, track_id=track.id, title=track.title,
                artist=track.artist, duration_ms=int(track.duration * 1000) if track.duration else None,
            )
        except (TypeError, ValueError):
            self.library_view.info_label.setText("La pista seleccionada no se puede cargar")
            return
        self.preview_player_bar.load_track(preview_track)

    def closeEvent(self, event):
        """Own the optional preview resource without coupling widgets to QtMultimedia."""
        if self._resources_closed:
            super().closeEvent(event)
            return
        self._resources_closed = True
        # Closing the supplied LibraryView releases its injected repositories;
        # the default view has the same close contract and remains idempotent.
        try:
            self.library_view.close()
        except Exception:
            pass
        if self.preview_player_service is not None:
            try:
                self.preview_player_service.close()
            except Exception:
                pass
        super().closeEvent(event)
