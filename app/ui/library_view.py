from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QLabel
)

from PySide6.QtCore import Qt

from database import SessionLocal
from models import Track


class LibraryView(QWidget):

    def __init__(self):
        super().__init__()

        self.layout = QVBoxLayout()

        self.counter = QLabel(
            "Biblioteca: cargando..."
        )

        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Buscar artista, título o álbum..."
        )

        self.table = QTableWidget()

        self.layout.addWidget(self.counter)
        self.layout.addWidget(self.search)
        self.layout.addWidget(self.table)

        self.setLayout(self.layout)

        self.search.textChanged.connect(
            self.filter_tracks
        )

        self.load_tracks()

    def setup_table(self):

        self.table.setColumnCount(8)

        self.table.setHorizontalHeaderLabels(
            [
                "Artista",
                "Título",
                "Álbum",
                "BPM",
                "Key",
                "Duración",
                "Rating",
                "Ruta"
            ]
        )

        self.table.setSortingEnabled(True)

        self.table.horizontalHeader().setStretchLastSection(True)

    def load_tracks(self):

        session = SessionLocal()

        total = session.query(Track).count()

        self.counter.setText(
            f"Biblioteca: {total} pistas"
        )

        tracks = (
            session.query(Track)
            .limit(500)
            .all()
        )

        self.setup_table()

        self.fill_table(tracks)

        session.close()

    def fill_table(self, tracks):

        self.table.setRowCount(
            len(tracks)
        )

        for row, track in enumerate(tracks):

            values = [
                track.artist or "",
                track.title or "",
                track.album or "",
                str(track.bpm or ""),
                track.key or "",
                self.format_duration(track.duration),
                str(track.rating or ""),
                track.filepath or ""
            ]

            for column, value in enumerate(values):

                item = QTableWidgetItem(value)

                self.table.setItem(
                    row,
                    column,
                    item
                )

        self.table.resizeColumnsToContents()

    def filter_tracks(self, text):

        session = SessionLocal()

        tracks = (
            session.query(Track)
            .filter(
                (Track.artist.ilike(f"%{text}%")) |
                (Track.title.ilike(f"%{text}%")) |
                (Track.album.ilike(f"%{text}%"))
            )
            .limit(500)
            .all()
        )

        self.fill_table(tracks)

        session.close()

    def format_duration(self, seconds):

        if not seconds:
            return ""

        minutes = int(seconds // 60)
        seconds = int(seconds % 60)

        return f"{minutes}:{seconds:02d}"
