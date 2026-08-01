from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
)

try:
    from ..database import SessionLocal
    from ..models import Track
except ImportError:  # pragma: no cover - fallback for direct execution
    from database import SessionLocal
    from models import Track


class LibraryView(QWidget):
    def __init__(self):
        super().__init__()

        self.layout = QVBoxLayout()

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar artista o título...")

        self.table = QTableWidget()

        self.layout.addWidget(self.search)
        self.layout.addWidget(self.table)

        self.setLayout(self.layout)

        self.search.textChanged.connect(self.filter_tracks)

        self.load_tracks()

    def load_tracks(self):
        session = SessionLocal()

        tracks = (
            session.query(Track)
            .limit(500)
            .all()
        )

        self.table.setRowCount(len(tracks))
        self.table.setColumnCount(5)

        self.table.setHorizontalHeaderLabels(
            [
                "Artista",
                "Título",
                "BPM",
                "Key",
                "Duración",
            ]
        )

        for row, track in enumerate(tracks):
            self.table.setItem(row, 0, QTableWidgetItem(track.artist or ""))
            self.table.setItem(row, 1, QTableWidgetItem(track.title or ""))
            self.table.setItem(row, 2, QTableWidgetItem(str(track.bpm or "")))
            self.table.setItem(row, 3, QTableWidgetItem(track.key or ""))
            self.table.setItem(row, 4, QTableWidgetItem(str(track.duration or "")))

        session.close()

    def filter_tracks(self, text):
        session = SessionLocal()

        tracks = (
            session.query(Track)
            .filter(
                (Track.artist.ilike(f"%{text}%")) |
                (Track.title.ilike(f"%{text}%"))
            )
            .limit(500)
            .all()
        )

        self.table.setRowCount(len(tracks))

        for row, track in enumerate(tracks):
            self.table.setItem(row, 0, QTableWidgetItem(track.artist or ""))
            self.table.setItem(row, 1, QTableWidgetItem(track.title or ""))

        session.close()
