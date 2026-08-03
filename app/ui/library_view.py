from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QTableView,
    QLabel,
    QHeaderView,
    QPushButton,
)

from PySide6.QtCore import Qt, Signal

try:
    from ..services.library_service import LibraryService
    from ..services.history_service import HistoryService
    from .models.track_table_model import TrackTableModel
except ImportError:  # pragma: no cover - fallback for direct execution
    from app.services.library_service import LibraryService
    from app.services.history_service import HistoryService
    from app.ui.models.track_table_model import TrackTableModel


class LibraryView(QWidget):

    preview_track_requested = Signal(object)

    def __init__(self):
        super().__init__()

        self.library_service = LibraryService()
        self.history_service = HistoryService()

        self.layout = QVBoxLayout()

        self.counter = QLabel(
            "Biblioteca: cargando..."
        )

        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Buscar artista, título o álbum..."
        )

        self.table = QTableView()
        self.model = TrackTableModel([], self.library_service.load_more)

        self.table.setModel(self.model)
        self.model.rowsInserted.connect(self.update_counter)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        header.sectionClicked.connect(self.sort_tracks)

        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setAlternatingRowColors(True)

        selection = self.table.selectionModel()
        selection.selectionChanged.connect(self.on_selection_changed)

        self.info_label = QLabel("Selecciona una pista")
        self.load_preview_button = QPushButton("Cargar en reproductor")
        self.load_preview_button.setAccessibleName("Cargar pista seleccionada en reproductor")
        self.load_preview_button.setToolTip("Carga la fila activa en la preescucha sin reproducirla")
        self.load_preview_button.setEnabled(False)
        self.load_preview_button.setVisible(False)

        self.layout.addWidget(self.counter)
        self.layout.addWidget(self.search)
        self.layout.addWidget(self.table)
        self.layout.addWidget(self.info_label)
        self.layout.addWidget(self.load_preview_button)

        self.setLayout(self.layout)

        self.search.textChanged.connect(
            self.filter_tracks
        )
        self.load_preview_button.clicked.connect(self.request_preview_load)

        self.load_tracks()

    def setup_table(self):

        self.table.resizeColumnsToContents()

    def load_tracks(self):
        tracks, has_more = self.library_service.load_library()
        self.model.set_page(tracks, has_more)
        self.update_counter()
        self.setup_table()

    def filter_tracks(self, text):

        tracks, has_more = self.library_service.search(text)
        self.model.set_page(tracks, has_more)
        self.update_counter()

    def sort_tracks(self, section):
        columns = ("artist", "title", "album", "bpm", "key", "duration", "rating")
        column = columns[section]
        direction = "desc" if self.table.horizontalHeader().sortIndicatorOrder() == Qt.AscendingOrder else "asc"
        tracks, has_more = self.library_service.sort(column, direction)
        self.model.set_page(tracks, has_more)
        self.update_counter()
        self.table.horizontalHeader().setSortIndicator(section, Qt.DescendingOrder if direction == "desc" else Qt.AscendingOrder)

    def update_counter(self, *_):
        total = self.library_service.count_results()
        loaded = self.model.rowCount()
        self.counter.setText(f"Biblioteca: {loaded} de {total} pistas cargadas")

    def closeEvent(self, event):
        self.library_service.close()
        self.history_service.close()
        super().closeEvent(event)

    def on_selection_changed(self, selected, deselected):

        indexes = selected.indexes()

        if not indexes:
            self.info_label.setText("Selecciona una pista")
            self.load_preview_button.setEnabled(False)
            return

        track = self.model.track_at(indexes[0].row())

        if track:
            self.history_service.record_track_selected(track.id)
            self.load_preview_button.setEnabled(bool(getattr(track, "id", None) is not None and getattr(track, "filepath", None)))
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
            self.info_label.setText("Selecciona una pista valida para cargar")
            return
        self.preview_track_requested.emit(track)
