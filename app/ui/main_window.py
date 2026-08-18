from dataclasses import dataclass
from types import SimpleNamespace

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

try:
    from .library_view import LibraryView
    from .collection_panel import CollectionPanel
    from .import_manager_panel import ImportManagerPanel
    from .playlist_panel import PlaylistPanel
    from .dj_set_panel import DJSetPanel
    from .track_metadata_panel import TrackMetadataPanel
    from .settings_panel import SettingsPanel
    from .widgets.preview_player_bar import PreviewPlayerBar
    from .widgets.navigation_sidebar import NavigationSidebar
    from .widgets.context_header import ContextHeader
    from app.services.track_metadata_facade import TrackMetadataFacade
    from app.services.track_metadata_editor import TrackMetadataEditorService
    from app.services.action_pipeline import ActionPipeline
    from app.services.confirmation_manager import ConfirmationManager
    from app.services.duplicate_detection_service import DuplicateDetectionService
    from app.services.duplicate_detection_facade import DuplicateDetectionFacade
    from app.services.multi_format_audio_analysis_facade import MultiFormatAudioAnalysisFacade
    from app.services.preview_player import PreviewTrackDTO
    from app.services.metadata_service import MetadataService
    from app.services.history_service import HistoryService
    from app.services.library_service import LibraryService
    from app.services.dj_intelligence_service import DJIntelligenceService
    from app.services.energy_journey import EnergyJourneyPlanner
    from app.services.recommendation_scoring import RecommendationScoringEngine
    from app.services.recommendation_service import RecommendationService
    from app.services.set_builder_facade import SetBuilderFacade, SetBuilderQueryDTO
    from app.services.set_planning import SetPlanningEngine
except ImportError:  # pragma: no cover - fallback for direct execution
    from ui.library_view import LibraryView
    from ui.collection_panel import CollectionPanel
    from ui.import_manager_panel import ImportManagerPanel
    from ui.playlist_panel import PlaylistPanel
    from app.ui.dj_set_panel import DJSetPanel
    from app.ui.track_metadata_panel import TrackMetadataPanel
    from app.ui.settings_panel import SettingsPanel
    from app.ui.widgets.preview_player_bar import PreviewPlayerBar
    from app.ui.widgets.navigation_sidebar import NavigationSidebar
    from app.ui.widgets.context_header import ContextHeader
    from app.services.track_metadata_facade import TrackMetadataFacade
    from app.services.track_metadata_editor import TrackMetadataEditorService
    from app.services.action_pipeline import ActionPipeline
    from app.services.confirmation_manager import ConfirmationManager
    from app.services.duplicate_detection_service import DuplicateDetectionService
    from app.services.duplicate_detection_facade import DuplicateDetectionFacade
    from app.services.multi_format_audio_analysis_facade import MultiFormatAudioAnalysisFacade
    from app.services.preview_player import PreviewTrackDTO
    from app.services.metadata_service import MetadataService
    from app.services.history_service import HistoryService
    from app.services.library_service import LibraryService
    from app.services.dj_intelligence_service import DJIntelligenceService
    from app.services.energy_journey import EnergyJourneyPlanner
    from app.services.recommendation_scoring import RecommendationScoringEngine
    from app.services.recommendation_service import RecommendationService
    from app.services.set_builder_facade import SetBuilderFacade, SetBuilderQueryDTO
    from app.services.set_planning import SetPlanningEngine


class _DJSetProposalWorker(QObject):
    """Build a proposal with worker-owned services, never the UI session."""

    result = Signal(object, object)
    cancelled = Signal()
    failed = Signal(str)
    finished = Signal()

    def __init__(self, reference_track):
        super().__init__()
        self._reference_track = reference_track

    @Slot()
    def run(self):
        library = history = None
        try:
            if QThread.currentThread().isInterruptionRequested():
                self.cancelled.emit()
                return
            library, history = LibraryService(), HistoryService()
            recommendation = RecommendationService(RecommendationScoringEngine(DJIntelligenceService(), history))
            facade = SetBuilderFacade(library, history, EnergyJourneyPlanner(SetPlanningEngine(recommendation)))
            result = facade.build(SetBuilderQueryDTO(self._reference_track, target_track_count=8))
            if QThread.currentThread().isInterruptionRequested():
                self.cancelled.emit()
                return
            rows, _has_more = library.query(text="")
            self.result.emit(result, tuple(self._display_track(track) for track in rows))
        except Exception as error:  # pragma: no cover - defensive UI boundary
            self.failed.emit(str(error))
        finally:
            if history is not None:
                history.close()
            if library is not None:
                library.close()
            self.finished.emit()

    @staticmethod
    def _display_track(track):
        return SimpleNamespace(**{
            name: getattr(track, name, None)
            for name in ("id", "artist", "title", "bpm", "key", "energy", "duration")
        })


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
    dj_set_panel: object | None = None


class MainWindow(QMainWindow):
    """Primary visual shell that keeps the existing workspace widgets intact."""

    SECTIONS = (
        ("library", "Biblioteca"),
        ("collections", "Colecciones"),
        ("playlists", "Playlists"),
        ("dj_set", "DJ Set"),
        ("import", "Importar"),
        ("metadata", "Metadata"),
        ("assistant", "Assistant"),
        ("settings", "Ajustes"),
    )
    _COMPACT_NAVIGATION_WIDTH = 1040

    def __init__(self, preview_player_service=None, dependencies=None):
        super().__init__()
        if dependencies is not None and not isinstance(dependencies, MainWindowDependencies):
            raise TypeError("dependencies requiere MainWindowDependencies.")
        self.preview_player_service = preview_player_service
        self._dependencies = dependencies or MainWindowDependencies()
        self._resources_closed = False
        self._page_indexes = {}
        self.navigation_buttons = {}
        self._dj_set_thread = None
        self._dj_set_worker = None

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

        self.context_header = ContextHeader()
        self.page_title_label = self.context_header.page_title_label
        # Workspace pages already carry their own identity.  Keeping the old
        # application banner consumed vertical space and competed with the DJ
        # workspace, so the identity now lives in the navigation rail.
        self.context_header.setVisible(False)
        root.addWidget(self.context_header)

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
        self.dj_set_panel = self._dependencies.dj_set_panel or DJSetPanel()
        self.import_panel = self._dependencies.import_panel or ImportManagerPanel()
        self.track_metadata_panel = self._build_metadata_panel(library)
        self._connect_library_metadata_selection(library)
        self._connect_library_metadata_editor(library)
        self._connect_metadata_refresh(library)
        self._connect_dj_set_flow(library)

        self._add_workspace("library", library)
        self._add_workspace("collections", self.collection_panel)
        self._add_workspace("playlists", self.playlist_panel)
        self._add_workspace("dj_set", self.dj_set_panel)
        self._add_workspace("import", self.import_panel)
        self._add_workspace("metadata", self._scrollable_workspace(self.track_metadata_panel))
        self._add_workspace(
            "assistant",
            self._dependencies.assistant_panel or self._create_availability_page(
                "Assistant", "El assistant local estará disponible cuando se configure su proveedor."
            ),
        )
        self.settings_panel = SettingsPanel(self.preview_player_service)
        self._add_workspace("settings", self.settings_panel)

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

    def _build_navigation(self):
        nav = NavigationSidebar(self.SECTIONS)
        nav.setMinimumWidth(142)
        nav.setMaximumWidth(164)
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

    def _connect_library_metadata_selection(self, library):
        selection_signal = getattr(library, "track_selected", None)
        set_selected_track = getattr(self.track_metadata_panel, "set_selected_track", None)
        if selection_signal is not None and callable(set_selected_track):
            selection_signal.connect(set_selected_track)

    def _connect_library_metadata_editor(self, library):
        request_signal = getattr(library, "edit_metadata_requested", None)
        set_selected_track = getattr(self.track_metadata_panel, "set_selected_track", None)
        if request_signal is not None and callable(set_selected_track):
            request_signal.connect(self._open_metadata_editor)

    def _open_metadata_editor(self, track):
        self.track_metadata_panel.set_selected_track(track)
        self.navigate_to("metadata")

    def _connect_metadata_refresh(self, library):
        changed_signal = getattr(self.track_metadata_panel, "metadata_changed", None)
        refresh = getattr(library, "refresh_tracks", None)
        if changed_signal is not None and callable(refresh):
            changed_signal.connect(lambda: refresh())

    def _connect_dj_set_flow(self, library):
        selected_signal = getattr(library, "track_selected", None)
        set_reference = getattr(self.dj_set_panel, "set_reference_track", None)
        if selected_signal is not None and callable(set_reference):
            selected_signal.connect(set_reference)
        request_signal = getattr(library, "dj_set_requested", None)
        if request_signal is not None:
            request_signal.connect(self._generate_dj_set)
        choose_signal = getattr(self.dj_set_panel, "select_reference_requested", None)
        if choose_signal is not None:
            choose_signal.connect(lambda: self.navigate_to("library"))
        generate_signal = getattr(self.dj_set_panel, "generate_requested", None)
        if generate_signal is not None:
            generate_signal.connect(self._generate_dj_set)
        cancel_signal = getattr(self.dj_set_panel, "cancel_requested", None)
        if cancel_signal is not None:
            cancel_signal.connect(self._cancel_dj_set_generation)

    def _generate_dj_set(self, track):
        if self._dj_set_thread is not None and self._dj_set_thread.isRunning():
            return
        reference = _DJSetProposalWorker._display_track(track)
        self._dj_set_thread = QThread(self)
        self._dj_set_worker = _DJSetProposalWorker(reference)
        self._dj_set_worker.moveToThread(self._dj_set_thread)
        self._dj_set_thread.started.connect(self._dj_set_worker.run)
        self._dj_set_worker.result.connect(self._show_dj_set_result)
        self._dj_set_worker.cancelled.connect(self._show_dj_set_cancelled)
        self._dj_set_worker.failed.connect(self._show_dj_set_error)
        self._dj_set_worker.finished.connect(self._dj_set_thread.quit)
        self._dj_set_worker.finished.connect(self._dj_set_worker.deleteLater)
        self._dj_set_thread.finished.connect(self._finish_dj_set_worker)
        self._dj_set_thread.finished.connect(self._dj_set_thread.deleteLater)
        self.dj_set_panel.set_generation_running(True)
        self.navigate_to("dj_set")
        self._dj_set_thread.start()

    def _cancel_dj_set_generation(self):
        if self._dj_set_thread is not None and self._dj_set_thread.isRunning():
            self._dj_set_thread.requestInterruption()
            self.dj_set_panel.status.setText("Cancelación solicitada; la biblioteca no fue modificada.")
            self.dj_set_panel.cancel_button.setEnabled(False)

    def _show_dj_set_result(self, result, tracks):
        self.dj_set_panel.set_result(result, tracks)

    def _show_dj_set_cancelled(self):
        self.dj_set_panel.clear_result()
        self.dj_set_panel.status.setText("Generación cancelada; la biblioteca no fue modificada.")

    def _show_dj_set_error(self, _message):
        self.dj_set_panel.clear_result()
        self.dj_set_panel.status.setText("No se pudo generar el DJ Set. Probá con otra pista de referencia.")

    def _finish_dj_set_worker(self):
        self.dj_set_panel.set_generation_running(False)
        self.dj_set_panel.cancel_button.setEnabled(True)
        self._dj_set_worker = None
        self._dj_set_thread = None

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

    def _scrollable_workspace(self, widget):
        """Keep long review flows reachable in short application windows."""
        scroll_area = QScrollArea()
        scroll_area.setObjectName("metadataScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setWidget(widget)
        return scroll_area

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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.navigation_sidebar.set_compact(event.size().width() < self._COMPACT_NAVIGATION_WIDTH)

    def load_selected_track_in_preview(self, track):
        """Adapt the selected model item without re-querying repository or media backend."""
        if self.preview_player_bar is None:
            return
        try:
            artwork_data = getattr(track, "artwork_data", None)
            if artwork_data is None:
                try:
                    artwork_data = MetadataService().read_embedded(track.filepath).artwork_data
                except Exception:
                    artwork_data = None
            preview_track = PreviewTrackDTO(
                filepath=track.filepath,
                track_id=track.id,
                title=track.title,
                artist=track.artist,
                duration_ms=int(track.duration * 1000) if track.duration else None,
                artwork_data=artwork_data,
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
        if self._dj_set_thread is not None and self._dj_set_thread.isRunning():
            self._cancel_dj_set_generation()
            if not self._dj_set_thread.wait(2000):
                event.ignore()
                return
        self._resources_closed = True
        for widget in (
            self.import_panel,
            self.collection_panel,
            self.playlist_panel,
            self.dj_set_panel,
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
