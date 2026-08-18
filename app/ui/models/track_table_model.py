import json

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QPixmap
from app.services.key_notation import format_key


class TrackTableModel(QAbstractTableModel):
    HEADERS = [
        "Artista", "Título", "Álbum", "Género", "BPM", "Key", "Energía", "Duración", "Rating",
    ]

    HEADERS = HEADERS[:3] + ["Sello"] + HEADERS[3:]
    HEADERS = ["Portada"] + HEADERS

    EDITABLE_FIELDS = {1: "artist", 2: "title", 3: "album", 4: "label", 5: "genre", 6: "bpm", 7: "key", 8: "energy"}

    def __init__(self, tracks=None, load_more=None, has_more=False, update_metadata=None):
        super().__init__()
        self._tracks = tracks or []
        self._load_more = load_more
        self._has_more = has_more
        self._key_notation = "both"
        self._artwork_cache = {}
        self._update_metadata = update_metadata

    def rowCount(self, parent=None):
        return len(self._tracks)

    def columnCount(self, parent=None):
        return len(self.HEADERS)

    def headerData(self, section, orientation, role):
        if role != Qt.DisplayRole:
            return None
        return self.HEADERS[section] if orientation == Qt.Horizontal else str(section + 1)

    def data(self, index, role):
        if not index.isValid():
            return None
        if role == Qt.TextAlignmentRole and index.column() == 10:
            return Qt.AlignCenter
        track = self._tracks[index.row()]
        if role == Qt.DecorationRole and index.column() == 0:
            return self._artwork_for(track)
        if role != Qt.DisplayRole:
            return None
        values = [
            "", track.artist or "", track.title or "", track.album or "", getattr(track, "label", None) or "", track.genre or "",
            track.bpm or "", format_key(track.key, self._key_notation), getattr(track, "energy", None) or "",
            self.format_duration(track.duration), self.format_rating(track.rating),
        ]
        return str(values[index.column()])

    def flags(self, index):
        # Metadata editing is temporarily disabled until the table editor has
        # a safe, validated commit flow.  A mouse gesture must never be able
        # to mutate a track as a side effect of selecting it.
        return super().flags(index)

    def setData(self, index, value, role=Qt.EditRole):
        """Block cell commits until inline editing is rebuilt safely."""
        return False

    @staticmethod
    def _clean_edit_value(field, value):
        if field == "bpm":
            return float(value) if str(value).strip() else None
        if field == "energy":
            energy = int(value)
            if not 0 <= energy <= 100:
                raise ValueError("energy fuera de rango")
            return energy
        return str(value).strip() or None

    def _artwork_for(self, track):
        identifier = getattr(track, "id", None)
        if identifier in self._artwork_cache:
            return self._artwork_cache[identifier]
        pixmap = QPixmap()
        data = getattr(track, "artwork_data", None)
        if isinstance(data, bytes) and data and pixmap.loadFromData(data):
            pixmap = pixmap.scaled(34, 34, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        self._artwork_cache[identifier] = pixmap if not pixmap.isNull() else None
        return self._artwork_cache[identifier]

    @staticmethod
    def format_duration(seconds):
        if not seconds:
            return ""
        return f"{int(seconds // 60)}:{int(seconds % 60):02d}"

    @staticmethod
    def format_classification(value):
        if not value:
            return ""
        if not isinstance(value, str):
            return str(value)
        try:
            items = json.loads(value)
        except (TypeError, ValueError):
            return value
        if not isinstance(items, list):
            return value
        labels = []
        for item in items:
            if isinstance(item, (list, tuple)) and item:
                labels.append(str(item[1] if len(item) > 1 and item[1] else item[0]))
            elif isinstance(item, str):
                labels.append(item)
        return ", ".join(labels)

    @staticmethod
    def format_rating(value):
        try:
            rating = max(0, min(5, int(value or 0)))
        except (TypeError, ValueError):
            rating = 0
        return "★" * rating + "☆" * (5 - rating)

    def set_tracks(self, tracks):
        self.beginResetModel()
        self._tracks = tracks
        self._artwork_cache = {}
        self.endResetModel()

    def set_key_notation(self, notation):
        self._key_notation = notation if notation in {"camelot", "musical", "both"} else "both"
        if self._tracks:
            first = self.index(0, 7)
            last = self.index(len(self._tracks) - 1, 7)
            self.dataChanged.emit(first, last, [Qt.DisplayRole])

    def set_page(self, tracks, has_more):
        self._has_more = has_more
        self.set_tracks(tracks)

    def canFetchMore(self, parent=None):
        return self._has_more and self._load_more is not None

    def fetchMore(self, parent=None):
        tracks, self._has_more = self._load_more()
        if not tracks:
            return
        start = len(self._tracks)
        self.beginInsertRows(QModelIndex(), start, start + len(tracks) - 1)
        self._tracks.extend(tracks)
        self.endInsertRows()

    def track_at(self, row):
        return self._tracks[row] if 0 <= row < len(self._tracks) else None
