from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

try:
    from ..services.library_service import LibraryService
    from ..services.history_service import HistoryService
    from .models.track_table_model import TrackTableModel
except ImportError:  # pragma: no cover - fallback for direct execution
    from app.services.library_service import LibraryService
    from app.services.history_service import HistoryService
    from app.ui.models.track_table_model import TrackTableModel


class LibraryView(QWidget):
    """Library workspace that keeps the existing service and pagination contract."""

    preview_track_requested = Signal(object)
    track_selected = Signal(object)
    COLUMNS = ("artist", "title", "album", "label", None, None, None, "bpm", "key", None, "duration", "rating")

    def __init__(self, library_service=None, history_service=None, settings_service=None):
        super().__init__()
        self.library_service = library_service or LibraryService()
        self.history_service = history_service or HistoryService()
        self.settings_service = settings_service
        self._active_filters = {}
        self._last_error = None
        self._rating_press_active = False

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 16, 16, 16)
        self.layout.setSpacing(12)
        self._build_ui()
        self._connect_signals()
        self.load_tracks()

    def _build_ui(self):
        self._build_heading()
        self._build_toolbar()
        self._build_filter_panel()
        self._build_table_area()
        self._build_selection_actions()

    def _build_heading(self):
        heading = QHBoxLayout()
        heading.setSpacing(8)
        title_group = QVBoxLayout()
        title_group.setSpacing(2)
        title = QLabel("Biblioteca")
        title.setObjectName("libraryTitle")
        subtitle = QLabel("Explorá, ordená y prepará tu música")
        subtitle.setObjectName("librarySubtitle")
        title_group.addWidget(title)
        title_group.addWidget(subtitle)
        heading.addLayout(title_group)
        heading.addStretch(1)
        self.counter = QLabel("Biblioteca: cargando...")
        self.counter.setObjectName("libraryCounter")
        heading.addWidget(self.counter, alignment=Qt.AlignRight | Qt.AlignVCenter)
        self.layout.addLayout(heading)

    def _build_toolbar(self):
        toolbar = QFrame()
        toolbar.setObjectName("libraryToolbar")
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        self.search = QLineEdit()
        self.search.setObjectName("librarySearch")
        self.search.setPlaceholderText("Buscar artista, título o álbum...")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Buscar en la biblioteca")
        self.filter_toggle_button = QPushButton("Filtros")
        self.filter_toggle_button.setCheckable(True)
        self.filter_toggle_button.setAccessibleName("Mostrar filtros de biblioteca")
        self.refresh_button = QPushButton("Actualizar")
        self.refresh_button.setAccessibleName("Actualizar resultados de biblioteca")
        self.key_notation = QComboBox()
        self.key_notation.setAccessibleName("Notación de tonalidad")
        self.key_notation.addItem("Key: ambas", "both")
        self.key_notation.addItem("Key: Camelot", "camelot")
        self.key_notation.addItem("Key: musical", "musical")
        self._load_key_notation_preference()

        layout.addWidget(self.search, 1)
        layout.addWidget(self.key_notation)
        layout.addWidget(self.filter_toggle_button)
        layout.addWidget(self.refresh_button)
        self.layout.addWidget(toolbar)

    def _build_filter_panel(self):
        self.filter_panel = QFrame()
        self.filter_panel.setObjectName("libraryFilters")
        layout = QHBoxLayout(self.filter_panel)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        self.genre_filter = QLineEdit()
        self.genre_filter.setPlaceholderText("Género")
        self.genre_filter.setAccessibleName("Filtrar por género")
        self.bpm_min_filter = QDoubleSpinBox()
        self.bpm_min_filter.setRange(0, 400)
        self.bpm_min_filter.setDecimals(1)
        self.bpm_min_filter.setSpecialValueText("BPM mínimo")
        self.bpm_max_filter = QDoubleSpinBox()
        self.bpm_max_filter.setRange(0, 400)
        self.bpm_max_filter.setDecimals(1)
        self.bpm_max_filter.setSpecialValueText("BPM máximo")
        self.key_filter = QLineEdit()
        self.key_filter.setPlaceholderText("Clave")
        self.key_filter.setAccessibleName("Filtrar por clave")
        self.rating_filter = QSpinBox()
        self.rating_filter.setRange(0, 5)
        self.rating_filter.setSpecialValueText("Rating mínimo")
        self.apply_filters_button = QPushButton("Aplicar")
        self.clear_filters_button = QPushButton("Limpiar")

        for widget in (
            self.genre_filter,
            self.bpm_min_filter,
            self.bpm_max_filter,
            self.key_filter,
            self.rating_filter,
            self.apply_filters_button,
            self.clear_filters_button,
        ):
            layout.addWidget(widget)
        self.filter_panel.setVisible(False)
        self.layout.addWidget(self.filter_panel)

    def _build_table_area(self):
        self.table = QTableView()
        self.table.setObjectName("libraryTable")
        self.model = TrackTableModel([], self.library_service.load_more)
        self.model.set_key_notation(self.key_notation.currentData())
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.setEditTriggers(QTableView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.viewport().installEventFilter(self)

        header = self.table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSectionsMovable(True)
        header.setSectionResizeMode(QHeaderView.Interactive)
        for section, width in enumerate((170, 180, 150, 130, 130, 180, 150, 80, 70, 80, 90, 130)):
            header.resizeSection(section, width)
        header.sectionClicked.connect(self.sort_tracks)

        self.state_page = QFrame()
        self.state_page.setObjectName("libraryState")
        state_layout = QVBoxLayout(self.state_page)
        state_layout.setContentsMargins(24, 24, 24, 24)
        state_layout.setSpacing(8)
        self.state_title = QLabel("Cargando biblioteca")
        self.state_title.setObjectName("libraryStateTitle")
        self.state_message = QLabel("Preparando resultados…")
        self.state_message.setObjectName("libraryStateMessage")
        self.state_message.setWordWrap(True)
        state_layout.addWidget(self.state_title)
        state_layout.addWidget(self.state_message)
        state_layout.addStretch(1)

        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(self.table)
        self.content_stack.addWidget(self.state_page)
        self.layout.addWidget(self.content_stack, 1)

    def _build_selection_actions(self):
        selection_bar = QFrame()
        selection_bar.setObjectName("librarySelectionBar")
        layout = QHBoxLayout(selection_bar)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        self.info_label = QLabel("Seleccioná una pista")
        self.info_label.setObjectName("librarySelectionInfo")
        self.load_preview_button = QPushButton("Cargar en reproductor")
        self.load_preview_button.setAccessibleName("Cargar pista seleccionada en reproductor")
        self.load_preview_button.setToolTip("Carga la fila activa en la preescucha sin reproducirla")
        self.load_preview_button.setEnabled(False)
        self.load_preview_button.setVisible(False)
        layout.addWidget(self.info_label, 1)
        layout.addWidget(self.load_preview_button)
        self.layout.addWidget(selection_bar)

    def _load_key_notation_preference(self):
        notation = "both"
        if self.settings_service is not None:
            try:
                notation = self.settings_service.get().library.key_notation
            except Exception:
                pass
        index = self.key_notation.findData(notation)
        self.key_notation.setCurrentIndex(index if index >= 0 else 0)

    def _change_key_notation(self):
        notation = self.key_notation.currentData()
        self.model.set_key_notation(notation)
        if self.settings_service is not None:
            try:
                self.settings_service.update({"library": {"key_notation": notation}})
            except Exception:
                self.info_label.setText("No se pudo guardar la preferencia de tonalidad")

    def _connect_signals(self):
        self.search.textChanged.connect(self.filter_tracks)
        self.filter_toggle_button.toggled.connect(self.filter_panel.setVisible)
        self.apply_filters_button.clicked.connect(self.apply_filters)
        self.clear_filters_button.clicked.connect(self.clear_filters)
        self.refresh_button.clicked.connect(self.refresh_tracks)
        self.key_notation.currentIndexChanged.connect(self._change_key_notation)
        self.load_preview_button.clicked.connect(self.request_preview_load)
        self.model.rowsInserted.connect(self._after_rows_inserted)
        self.table.selectionModel().selectionChanged.connect(self.on_selection_changed)
        self.table.doubleClicked.connect(self._handle_table_double_click)

    def load_tracks(self):
        self._show_loading("Cargando biblioteca", "Preparando resultados…")
        try:
            tracks, has_more = self.library_service.load_library()
        except Exception as error:
            self._show_error(error)
            return
        self._present_result(tracks, has_more)

    def refresh_tracks(self):
        self._show_loading("Actualizando biblioteca", "Actualizando los resultados actuales…")
        try:
            tracks, has_more = self.library_service.refresh()
        except Exception as error:
            self._show_error(error)
            return
        self._present_result(tracks, has_more)

    def filter_tracks(self, text):
        self._show_loading("Buscando", "Actualizando los resultados de búsqueda…")
        try:
            tracks, has_more = self.library_service.search(text)
        except Exception as error:
            self._show_error(error)
            return
        self._present_result(tracks, has_more, query_active=bool(text) or bool(self._active_filters))

    def apply_filters(self):
        filters = self._collect_filters()
        self._show_loading("Aplicando filtros", "Actualizando los resultados filtrados…")
        try:
            tracks, has_more = self.library_service.query(self.search.text(), **filters)
        except Exception as error:
            self._show_error(error)
            return
        self._active_filters = filters
        self._present_result(tracks, has_more, query_active=bool(self.search.text()) or bool(filters))

    def clear_filters(self):
        for widget in (self.genre_filter, self.key_filter):
            widget.clear()
        for widget in (self.bpm_min_filter, self.bpm_max_filter, self.rating_filter):
            widget.setValue(0)
        self._active_filters = {}
        self._show_loading("Limpiando filtros", "Restableciendo los resultados de biblioteca…")
        try:
            tracks, has_more = self.library_service.query(self.search.text())
        except Exception as error:
            self._show_error(error)
            return
        self._present_result(tracks, has_more, query_active=bool(self.search.text()))

    def _collect_filters(self):
        values = {
            "genre": self.genre_filter.text().strip() or None,
            "bpm_min": self.bpm_min_filter.value() or None,
            "bpm_max": self.bpm_max_filter.value() or None,
            "key": self.key_filter.text().strip() or None,
            "rating_min": self.rating_filter.value() or None,
        }
        return {name: value for name, value in values.items() if value is not None}

    def sort_tracks(self, section):
        column = self.COLUMNS[section]
        if column is None:
            return
        header = self.table.horizontalHeader()
        direction = "desc" if header.sortIndicatorOrder() == Qt.AscendingOrder else "asc"
        self._show_loading("Ordenando biblioteca", "Aplicando el orden seleccionado…")
        try:
            tracks, has_more = self.library_service.sort(column, direction)
        except Exception as error:
            self._show_error(error)
            return
        self._present_result(tracks, has_more)
        header.setSortIndicator(section, Qt.DescendingOrder if direction == "desc" else Qt.AscendingOrder)

    def _set_track_rating(self, row, rating):
        track = self.model.track_at(row)
        if track is None or getattr(track, "id", None) is None:
            return
        try:
            updated = self.library_service.update_rating(track.id, rating)
        except Exception:
            self.info_label.setText("No se pudo actualizar el rating")
            return
        track.rating = getattr(updated, "rating", rating)
        index = self.model.index(row, 11)
        self.model.dataChanged.emit(index, index, [Qt.DisplayRole])

    def eventFilter(self, watched, event):
        if watched is self.table.viewport() and event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            index = self.table.indexAt(event.position().toPoint())
            if index.isValid() and index.column() == 11:
                bounds = self.table.visualRect(index)
                stars_width = self.table.fontMetrics().horizontalAdvance("★★★★★")
                stars_left = bounds.center().x() - stars_width / 2
                position = event.position().x()
                if stars_left <= position <= stars_left + stars_width:
                    star_width = max(1, stars_width / 5)
                    rating = min(5, max(1, int((position - stars_left) / star_width) + 1))
                    track = self.model.track_at(index.row())
                    if track is not None and int(getattr(track, "rating", 0) or 0) == rating:
                        rating = 0
                    self._set_track_rating(index.row(), rating)
                self._rating_press_active = True
                return True
        if watched is self.table.viewport() and event.type() == QEvent.MouseButtonRelease and self._rating_press_active:
            self._rating_press_active = False
            return True
        return super().eventFilter(watched, event)

    def _present_result(self, tracks, has_more, query_active=None):
        self.model.set_page(tracks, has_more)
        self.update_counter()
        if tracks:
            self.content_stack.setCurrentWidget(self.table)
            self._last_error = None
            return
        active = (bool(self.search.text()) or bool(self._active_filters)) if query_active is None else query_active
        if active:
            self._show_state("Sin resultados", "Probá modificar la búsqueda o limpiar los filtros.")
        else:
            self._show_state("Biblioteca vacía", "Importá música para comenzar a organizar tu biblioteca.")

    def _after_rows_inserted(self, *_):
        self.update_counter()
        if self.model.rowCount():
            self.content_stack.setCurrentWidget(self.table)

    def update_counter(self, *_):
        try:
            total = self.library_service.count_results()
        except Exception:
            total = self.model.rowCount()
        loaded = self.model.rowCount()
        # A newly loaded page can arrive before a lightweight count provider has
        # refreshed its snapshot.  The UI total must never be lower than the
        # rows already present in the model.
        total = max(total, loaded)
        self.counter.setText(f"Biblioteca: {loaded} de {total} pistas cargadas")

    def _show_loading(self, title, message):
        self._show_state(title, message)

    def _show_error(self, error):
        self._last_error = error
        self._show_state("No se pudo cargar la biblioteca", "Reintentá actualizar los resultados.")
        self.info_label.setText("La biblioteca no está disponible temporalmente")
        self.load_preview_button.setEnabled(False)

    def _show_state(self, title, message):
        self.state_title.setText(title)
        self.state_message.setText(message)
        self.content_stack.setCurrentWidget(self.state_page)

    def closeEvent(self, event):
        self.library_service.close()
        self.history_service.close()
        super().closeEvent(event)

    def on_selection_changed(self, selected, deselected):
        indexes = selected.indexes()
        if not indexes:
            self.info_label.setText("Seleccioná una pista")
            self.load_preview_button.setEnabled(False)
            return
        track = self.model.track_at(indexes[0].row())
        if track:
            self.history_service.record_track_selected(track.id)
            self.track_selected.emit(track)
            self.load_preview_button.setEnabled(
                bool(getattr(track, "id", None) is not None and getattr(track, "filepath", None))
            )
            self.info_label.setText(
                f"{track.artist or 'Desconocido'} - {track.title or 'Sin título'}"
            )

    def set_preview_player_available(self, available):
        self.load_preview_button.setVisible(bool(available))
        if not available:
            self.load_preview_button.setEnabled(False)

    def request_preview_load(self):
        """Emit the active model item; consumers do not re-query the library."""
        index = self.table.currentIndex()
        track = self.model.track_at(index.row()) if index.isValid() else None
        if track is None or getattr(track, "id", None) is None or not getattr(track, "filepath", None):
            self.info_label.setText("Seleccioná una pista válida para cargar")
            return
        self.preview_track_requested.emit(track)

    def _handle_table_double_click(self, index):
        """Use the same internal load flow as the explicit button action."""
        if not index.isValid():
            return
        self.table.setCurrentIndex(index)
        self.request_preview_load()
