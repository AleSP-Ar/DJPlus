from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

try:
    from ..services.playlist_service import PlaylistService
except ImportError:  # pragma: no cover - fallback for direct execution
    from app.services.playlist_service import PlaylistService


class PlaylistPanel(QWidget):
    """Basic playlist administration without track editing or drag and drop."""

    def __init__(self):
        super().__init__()
        self.playlist_service = PlaylistService()
        self.selected_playlist_id = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Playlists"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Nombre de playlist")
        self.name_input.returnPressed.connect(self.create_playlist)
        layout.addWidget(self.name_input)

        self.playlist_list = QListWidget()
        self.playlist_list.itemSelectionChanged.connect(self.select_playlist)
        layout.addWidget(self.playlist_list)

        buttons = QHBoxLayout()
        create_button = QPushButton("Crear")
        create_button.clicked.connect(self.create_playlist)
        rename_button = QPushButton("Renombrar")
        rename_button.clicked.connect(self.rename_playlist)
        delete_button = QPushButton("Eliminar")
        delete_button.clicked.connect(self.delete_playlist)
        buttons.addWidget(create_button)
        buttons.addWidget(rename_button)
        buttons.addWidget(delete_button)
        layout.addLayout(buttons)

        self.status = QLabel("Selecciona una playlist")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

    def refresh(self, select_id=None):
        selected_id = self.selected_playlist_id if select_id is None else select_id
        self.playlist_list.blockSignals(True)
        self.playlist_list.clear()
        selected_item = None
        for playlist in self.playlist_service.list_playlists():
            item = QListWidgetItem(playlist.name)
            item.setData(Qt.UserRole, playlist.id)
            self.playlist_list.addItem(item)
            if playlist.id == selected_id:
                selected_item = item
        self.playlist_list.blockSignals(False)
        if selected_item is not None:
            self.playlist_list.setCurrentItem(selected_item)
            self.select_playlist()
        else:
            self.selected_playlist_id = None
            self.status.setText("Selecciona una playlist")

    def create_playlist(self):
        try:
            playlist = self.playlist_service.create_playlist(self.name_input.text())
        except ValueError as error:
            self.status.setText(str(error))
            return
        self.name_input.clear()
        self.refresh(select_id=playlist.id)

    def rename_playlist(self):
        if self.selected_playlist_id is None:
            self.status.setText("Selecciona una playlist para renombrarla.")
            return
        try:
            playlist = self.playlist_service.rename_playlist(
                self.selected_playlist_id,
                self.name_input.text(),
            )
        except ValueError as error:
            self.status.setText(str(error))
            return
        self.name_input.clear()
        self.refresh(select_id=playlist.id)

    def delete_playlist(self):
        if self.selected_playlist_id is None:
            self.status.setText("Selecciona una playlist para eliminarla.")
            return
        self.playlist_service.delete_playlist(self.selected_playlist_id)
        self.refresh()

    def select_playlist(self):
        item = self.playlist_list.currentItem()
        if item is None:
            self.selected_playlist_id = None
            self.status.setText("Selecciona una playlist")
            return
        self.selected_playlist_id = item.data(Qt.UserRole)
        count = self.playlist_service.count_tracks(self.selected_playlist_id)
        self.status.setText(f"{item.text()}: {count} pistas")

    def closeEvent(self, event):
        self.playlist_service.close()
        super().closeEvent(event)
