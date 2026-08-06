from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

try:
    from .library_view import LibraryView
    from .collection_panel import CollectionPanel
    from .import_manager_panel import ImportManagerPanel
    from .playlist_panel import PlaylistPanel
    from .track_metadata_panel import TrackMetadataPanel
    from .widgets.preview_player_bar import PreviewPlayerBar
    from .widgets.navigation_sidebar import NavigationSidebar
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
    from app.ui.widgets.navigation_sidebar import NavigationSidebar
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
    composition. This is not a service container: it only replaces widget
    construction at the MainWindow boundary.
    """

    library_view: object | None = None
    collection_panel: object | None = None
    playlist_panel: object | None = None
    import_panel: object | None = None
    track_metadata_panel: object | None = None
    assistant_panel: object | None = None
    diagnostics_panel: object | None = None


class MainWindow(QMainWindow):
    """Primary visual shell that keeps the existing workspace widgets intact."""

    SECTIONS = (
        ("library", "Biblioteca"),
        ("collections", "Colecciones"),
        ("playlists", "Playlists"),
        ("import", "Importar"),
        ("metadata", "Metadata"),
        ("assistant", "Assistant"),
        ("diagnostics", "Diagnóstico"),
    )

    def __init__(self, preview_player_service=None, dependencies=None):
        super().__init__()
        if dependencies is not None and not isinstance(dependencies, MainWindowDependencies):
            raise TypeError("dependencies requiere MainWindowDependencies.")
        self.preview_player_service = preview_player_service
        self._dependencies = dependencies or MainWindowDependencies()
        self._resources_closed = False
        self._page_indexes = {}
        self.navigation_buttons = {}

        self.setWindowTitle("DJPlus")
        self.resize(1280, 800)
        self.setMinimumSize(900, 560)
        self.create_ui()

    def create_ui(self):
        central = QWidget(self)
        central.setObjectName("appShell")
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addLayout(self._build_header())

        shell = QHBoxLayout()
        shell.setSpacing(12)
        shell.addWidget(self._build_navigation())

        self.workspace_stack = QStackedWidget()
        self.workspace_stack.setObjectName("workspaceStack")
        shell.addWidget(self.workspace_stack, 1)
        root.addLayout(shell, 1)

        library = self._dependencies.library_view or LibraryView()
        self.library_view = library
        self.collection_panel = self._dependencies.collection_panel or CollectionPanel()
        self.playlist_panel = self._dependencies.playlist_panel or PlaylistPanel()
        self.import_panel = self._dependencies.import_panel or ImportManagerPanel()
        self.track_metadata_panel = self._build_metadata_panel(library)

        self._add_workspace("library", library)
        self._add_workspace("collections", self.collection_panel)
        self._add_workspace("playlists", self.playlist_panel)
        self._add_workspace("import", self.import_panel)
        self._add_workspace("metadata", self.track_metadata_panel)
        self._add_workspace(
            "assistant",
            self._dependencies.assistant_panel or self._create_availability_page(
                "Assistant", "El assistant local estará disponible cuando se configure su proveedor."
            ),
        )
        self._add_workspace(
            "diagnostics",
            self._dependencies.diagnostics_panel or self._create_availability_page(
                "Diagnóstico", "El diagnóstico del sistema se mostrará aquí cuando esté configurado."
            ),
        )

        self.preview_player_bar = None
        if self.preview_player_service is not None:
            try:
                self.preview_player_bar = PreviewPlayerBar(self.preview_player_service, central)
                library.set_preview_player_available(True)
                library.preview_track_requested.connect(self.load_selected_track_in_preview)
            except Exception:
                self.preview_player_bar = None
        if self.preview_player_bar is not None:
            root.addWidget(self.preview_player_bar)

        self._compose_optional_facades(library)
        self.setCentralWidget(central)
        self.navigate_to("library")

    def _build_header(self):
        header = QHBoxLayout()
        header.setSpacing(8)
        identity = QVBoxLayout()
        identity.setSpacing(2)
        title = QLabel("DJPlus")
        title.setObjectName("appTitle")
        subtitle = QLabel("Biblioteca musical")
        subtitle.setObjectName("appSubtitle")
        identity.addWidget(title)
        identity.addWidget(subtitle)
        header.addLayout(identity)
        header.addStretch(1)
        self.page_title_label = QLabel()
        self.page_title_label.setObjectName("pageTitle")
        header.addWidget(self.page_title_label, alignment=Qt.AlignRight | Qt.AlignVCenter)
        return header

    def _build_navigation(self):
        nav = NavigationSidebar(self.SECTIONS)
        nav.setMinimumWidth(220)
        nav.setMaximumWidth(280)
        # expose the mapping for backward compatibility with existing tests/code
        self.navigation_sidebar = nav
        self.navigation_buttons = nav.buttons
        nav.section_requested.connect(self.navigate_to)
        return nav

    def _build_metadata_panel(self, library):
        if self._dependencies.track_metadata_panel is not None:
            return self._dependencies.track_metadata_panel
        try:
            pipeline = ActionPipeline()
            editor = TrackMetadataEditorService(pipeline, ConfirmationManager(pipeline))
            return TrackMetadataPanel(TrackMetadataFacade(library.library_service, editor))
        except Exception:
            return self._create_availability_page(
                "Metadata", "La edición de metadata no está disponible en esta configuración."
            )

    def _create_availability_page(self, title, message):
        page = QFrame()
        page.setObjectName("availabilityPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        heading = QLabel(title)
        heading.setObjectName("availabilityTitle")
        body = QLabel(message)
        body.setObjectName("availabilityMessage")
        body.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(body)
        layout.addStretch(1)
        return page

    def _add_workspace(self, section, widget):
        self._page_indexes[section] = self.workspace_stack.addWidget(widget)

    def _compose_optional_facades(self, library):
        try:
            self.duplicate_detection_facade = DuplicateDetectionFacade(
                library.library_service,
                DuplicateDetectionService(library.library_service),
            )
        except Exception:
            self.duplicate_detection_facade = None
        try:
            self.multi_format_audio_analysis_facade = MultiFormatAudioAnalysisFacade(library.library_service)
        except Exception:
            self.multi_format_audio_analysis_facade = None

    def navigate_to(self, section):
        """Show one existing workspace without recreating or reconfiguring it."""
        if section not in self._page_indexes:
            raise ValueError(f"Sección desconocida: {section}")
        self.workspace_stack.setCurrentIndex(self._page_indexes[section])
        # delegate checked-state updates to the navigation component
        try:
            self.navigation_sidebar.set_current_section(section)
        except Exception:
            # fallback: ensure mapping is kept in sync
            for key, button in self.navigation_buttons.items():
                button.setChecked(key == section)
        label = dict(self.SECTIONS)[section]
        self.page_title_label.setText(label)
        self.current_section = section

    def load_selected_track_in_preview(self, track):
        """Adapt the selected model item without re-querying repository or media backend."""
        if self.preview_player_bar is None:
            return
        try:
            preview_track = PreviewTrackDTO(
                filepath=track.filepath,
                track_id=track.id,
                title=track.title,
                artist=track.artist,
                duration_ms=int(track.duration * 1000) if track.duration else None,
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
        for widget in (
            self.import_panel,
            self.collection_panel,
            self.playlist_panel,
            self.track_metadata_panel,
            self.library_view,
        ):
            try:
                widget.close()
            except Exception:
                pass
        if self.preview_player_bar is not None:
            try:
                self.preview_player_bar.close()
            except Exception:
                pass
        if self.preview_player_service is not None:
            try:
                self.preview_player_service.close()
            except Exception:
                pass
        super().closeEvent(event)
