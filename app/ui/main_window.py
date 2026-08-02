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
except ImportError:  # pragma: no cover - fallback for direct execution
    from ui.library_view import LibraryView
    from ui.collection_panel import CollectionPanel
    from ui.import_manager_panel import ImportManagerPanel
    from ui.playlist_panel import PlaylistPanel


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
        collections = CollectionPanel()
        collections.setMaximumWidth(280)
        navigation.addWidget(collections)
        playlists = PlaylistPanel()
        playlists.setMaximumWidth(280)
        navigation.addWidget(playlists)
        imports = ImportManagerPanel()
        imports.setMaximumWidth(280)
        navigation.addWidget(imports)
        content.addLayout(navigation)

        library = LibraryView()
        content.addWidget(library, 1)
        layout.addLayout(content, 1)

        self.setCentralWidget(central)
