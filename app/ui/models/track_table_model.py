from PySide6.QtCore import QAbstractTableModel, Qt


class TrackTableModel(QAbstractTableModel):

    HEADERS = [
        "Artista",
        "Título",
        "Álbum",
        "BPM",
        "Key",
        "Duración",
        "Rating",
    ]

    def __init__(self, tracks=None):
        super().__init__()
        self._tracks = tracks or []

    def rowCount(self, parent=None):
        return len(self._tracks)

    def columnCount(self, parent=None):
        return len(self.HEADERS)

    def headerData(self, section, orientation, role):
        if role != Qt.DisplayRole:
            return None

        if orientation == Qt.Horizontal:
            return self.HEADERS[section]

        return str(section + 1)

    def data(self, index, role):

        if not index.isValid():
            return None

        if role != Qt.DisplayRole:
            return None

        track = self._tracks[index.row()]

        values = [
            track.artist or "",
            track.title or "",
            track.album or "",
            track.bpm or "",
            track.key or "",
            self.format_duration(track.duration),
            track.rating or "",
        ]

        return str(values[index.column()])

    def format_duration(self, seconds):

        if not seconds:
            return ""

        minutes = int(seconds // 60)
        seconds = int(seconds % 60)

        return f"{minutes}:{seconds:02d}"

    def set_tracks(self, tracks):

        self.beginResetModel()
        self._tracks = tracks
        self.endResetModel()

    def track_at(self, row):

        if 0 <= row < len(self._tracks):
            return self._tracks[row]

        return None
