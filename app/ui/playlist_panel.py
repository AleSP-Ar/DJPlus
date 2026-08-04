from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget
from .feedback import confirm_destructive

try:
    from ..services.playlist_service import PlaylistService
except ImportError:  # pragma: no cover
    from app.services.playlist_service import PlaylistService


class PlaylistPanel(QWidget):
    """Playlist administration surface; membership order remains service-owned."""

    def __init__(self, playlist_service=None):
        super().__init__()
        self.playlist_service = playlist_service or PlaylistService()
        self.selected_playlist_id = None
        self._build_ui(); self.refresh()

    def _build_ui(self):
        self.setObjectName("playlistsPanel")
        self.setStyleSheet("QFrame#playlistToolbar,QFrame#playlistListSection { background:#1f2937; border:1px solid #374151; border-radius:8px; } QLabel#playlistTitle { font-size:18px; font-weight:600; } QLabel#playlistHint,QLabel#playlistEmpty { color:#9ca3af; } QPushButton#playlistPrimary { background:#2563eb; color:white; font-weight:600; }")
        layout = QVBoxLayout(self); layout.setContentsMargins(16, 16, 16, 16); layout.setSpacing(12)
        title = QLabel("Playlists"); title.setObjectName("playlistTitle"); layout.addWidget(title)
        hint = QLabel("Prepará secuencias manuales; el orden de las pistas se conserva al reordenarlas."); hint.setObjectName("playlistHint"); layout.addWidget(hint)
        toolbar = QFrame(); toolbar.setObjectName("playlistToolbar"); tools = QHBoxLayout(toolbar); tools.setContentsMargins(10, 10, 10, 10); tools.setSpacing(8)
        self.search_input = QLineEdit(); self.search_input.setPlaceholderText("Buscar playlists"); self.search_input.setClearButtonEnabled(True); self.search_input.setAccessibleName("Buscar playlists"); self.search_input.textChanged.connect(self.refresh)
        self.name_input = QLineEdit(); self.name_input.setPlaceholderText("Nombre de playlist"); self.name_input.setAccessibleName("Nombre de playlist"); self.name_input.returnPressed.connect(self.create_playlist)
        self.create_button = QPushButton("Crear"); self.create_button.setObjectName("playlistPrimary"); self.create_button.clicked.connect(self.create_playlist)
        self.rename_button = QPushButton("Renombrar"); self.rename_button.clicked.connect(self.rename_playlist)
        self.delete_button = QPushButton("Eliminar"); self.delete_button.clicked.connect(self.delete_playlist)
        for widget in (self.search_input, self.name_input, self.create_button, self.rename_button, self.delete_button): tools.addWidget(widget)
        tools.addStretch(1); layout.addWidget(toolbar)
        section = QFrame(); section.setObjectName("playlistListSection"); contents = QVBoxLayout(section); contents.setContentsMargins(12, 10, 12, 10); contents.setSpacing(6)
        contents.addWidget(QLabel("Tus playlists")); self.playlist_list = QListWidget(); self.playlist_list.setAccessibleName("Lista de playlists"); self.playlist_list.itemSelectionChanged.connect(self.select_playlist); contents.addWidget(self.playlist_list)
        self.empty_label = QLabel("No hay playlists. Creá una para preparar tu próxima selección."); self.empty_label.setObjectName("playlistEmpty"); self.empty_label.setAlignment(Qt.AlignCenter); self.empty_label.setMinimumHeight(40); contents.addWidget(self.empty_label); layout.addWidget(section)
        self.status = QLabel("Seleccioná una playlist"); self.status.setWordWrap(True); layout.addWidget(self.status)
        self.order_hint = QLabel("El orden y la compactación de pistas se administran al reordenar sus pistas."); self.order_hint.setObjectName("playlistHint"); self.order_hint.setWordWrap(True); layout.addWidget(self.order_hint)

    def refresh(self, _text=None, select_id=None):
        selected_id = self.selected_playlist_id if select_id is None else select_id; query = self.search_input.text().casefold().strip(); self.playlist_list.blockSignals(True); self.playlist_list.clear(); selected_item = None
        for playlist in self.playlist_service.list_playlists():
            if query and query not in playlist.name.casefold(): continue
            item = QListWidgetItem(playlist.name); item.setData(Qt.UserRole, playlist.id); self.playlist_list.addItem(item)
            if playlist.id == selected_id: selected_item = item
        self.empty_label.setVisible(self.playlist_list.count() == 0); self.playlist_list.blockSignals(False)
        if selected_item is not None: self.playlist_list.setCurrentItem(selected_item); self.select_playlist()
        else: self.selected_playlist_id = None; self.status.setText("Sin resultados" if query else "Seleccioná una playlist")
    def create_playlist(self):
        try: playlist = self.playlist_service.create_playlist(self.name_input.text())
        except ValueError as error: self.status.setText(str(error)); return
        self.name_input.clear(); self.refresh(select_id=playlist.id)
    def rename_playlist(self):
        if self.selected_playlist_id is None: self.status.setText("Seleccioná una playlist para renombrarla."); return
        try: playlist = self.playlist_service.rename_playlist(self.selected_playlist_id, self.name_input.text())
        except ValueError as error: self.status.setText(str(error)); return
        self.name_input.clear(); self.refresh(select_id=playlist.id)
    def delete_playlist(self):
        if self.selected_playlist_id is None: self.status.setText("Seleccioná una playlist para eliminarla."); return
        if not confirm_destructive(self, "Eliminar playlist", "Esta acción eliminará la playlist seleccionada."):
            self.status.setText("Eliminación cancelada."); return
        self.playlist_service.delete_playlist(self.selected_playlist_id); self.refresh()
    def select_playlist(self):
        item = self.playlist_list.currentItem()
        if item is None: return
        self.selected_playlist_id = item.data(Qt.UserRole); count = self.playlist_service.count_tracks(self.selected_playlist_id); self.status.setText(f"{item.text()}: {count} pistas · orden preservado")
    def closeEvent(self, event): self.playlist_service.close(); super().closeEvent(event)
