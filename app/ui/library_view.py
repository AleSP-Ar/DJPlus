from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QTableView,
    QLabel,
    QHeaderView,
)

from PySide6.QtCore import Qt

try:
    from ..services.library_service import LibraryService
    from ..services.history_service import HistoryService
    from .models.track_table_model import TrackTableModel
except ImportError:  # pragma: no cover - fallback for direct execution
    from app.services.library_service import LibraryService
    from app.services.history_service import HistoryService
    from app.ui.models.track_table_model import TrackTableModel


class LibraryView(QWidget):

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

        self.layout.addWidget(self.counter)
        self.layout.addWidget(self.search)
        self.layout.addWidget(self.table)
        self.layout.addWidget(self.info_label)

        self.setLayout(self.layout)

        self.search.textChanged.connect(
            self.filter_tracks
        )

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
            return

        track = self.model.track_at(indexes[0].row())

        if track:
            self.history_service.record_track_selected(track.id)
            self.info_label.setText(
                f"{track.artist or 'Desconocido'} - {track.title or 'Sin título'}"
            )
