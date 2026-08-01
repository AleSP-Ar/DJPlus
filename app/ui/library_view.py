from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QTableView,
    QLabel,
    QHeaderView,
)

from PySide6.QtCore import Qt, QSortFilterProxyModel

try:
    from ..repository.track_repository import TrackRepository
    from .models.track_table_model import TrackTableModel
except ImportError:  # pragma: no cover - fallback for direct execution
    from app.repository.track_repository import TrackRepository
    from app.ui.models.track_table_model import TrackTableModel


class LibraryView(QWidget):

    def __init__(self):
        super().__init__()

        self.repository = TrackRepository()

        self.layout = QVBoxLayout()

        self.counter = QLabel(
            "Biblioteca: cargando..."
        )

        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Buscar artista, título o álbum..."
        )

        self.table = QTableView()
        self.model = TrackTableModel([])

        self.proxy = QSortFilterProxyModel()
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1)

        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)

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

        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()

    def load_tracks(self):

        total = self.repository.count_tracks()

        self.counter.setText(
            f"Biblioteca: {total} pistas"
        )

        tracks = self.repository.get_tracks(limit=500)

        self.model.set_tracks(tracks)
        self.setup_table()

    def filter_tracks(self, text):

        self.proxy.setFilterFixedString(text)

    def on_selection_changed(self, selected, deselected):

        indexes = selected.indexes()

        if not indexes:
            self.info_label.setText("Selecciona una pista")
            return

        proxy_index = indexes[0]
        source_index = self.proxy.mapToSource(proxy_index)

        track = self.model.track_at(source_index.row())

        if track:
            self.info_label.setText(
                f"{track.artist or 'Desconocido'} - {track.title or 'Sin título'}"
            )
