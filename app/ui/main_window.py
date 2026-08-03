from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
)

try:
    from .library_view import LibraryView
    from .collection_panel import CollectionPanel
    from .import_manager_panel import ImportManagerPanel
    from .playlist_panel import PlaylistPanel
    from .track_metadata_panel import TrackMetadataPanel
    from app.services.track_metadata_facade import TrackMetadataFacade
    from app.services.track_metadata_editor import TrackMetadataEditorService
    from app.services.action_pipeline import ActionPipeline
    from app.services.confirmation_manager import ConfirmationManager
except ImportError:  # pragma: no cover - fallback for direct execution
    from ui.library_view import LibraryView
    from ui.collection_panel import CollectionPanel
    from ui.import_manager_panel import ImportManagerPanel
    from ui.playlist_panel import PlaylistPanel
    from app.ui.track_metadata_panel import TrackMetadataPanel
    from app.services.track_metadata_facade import TrackMetadataFacade
    from app.services.track_metadata_editor import TrackMetadataEditorService
    from app.services.action_pipeline import ActionPipeline
    from app.services.confirmation_manager import ConfirmationManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

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
        library = LibraryView()
        collections = CollectionPanel()
        collections.setMaximumWidth(280)
        navigation.addWidget(collections)
        playlists = PlaylistPanel()
        playlists.setMaximumWidth(280)
        navigation.addWidget(playlists)
        imports = ImportManagerPanel()
        imports.setMaximumWidth(280)
        navigation.addWidget(imports)
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
        content.addWidget(library, 1)
        layout.addLayout(content, 1)

        self.setCentralWidget(central)
