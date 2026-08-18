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
        self.setStyleSheet("QFrame#playlistToolbar,QFrame#playlistListSection { background:#10182A; border:1px solid #253550; border-radius:9px; } QLabel#playlistTitle { color:#F1F5FF; font-size:19px; font-weight:700; } QLabel#playlistHint,QLabel#playlistEmpty { color:#8FA1BD; } QPushButton#playlistPrimary { background:#6259E8; border:1px solid #817AFF; color:white; font-weight:600; }")
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
        self.energy_section = QFrame(); self.energy_section.setObjectName("playlistEnergySection")
        energy_layout = QVBoxLayout(self.energy_section); energy_layout.setContentsMargins(12, 10, 12, 10); energy_layout.setSpacing(6)
        energy_heading = QHBoxLayout(); energy_title = QLabel("Secuencia de energía"); energy_title.setObjectName("playlistEnergyTitle"); self.energy_summary = QLabel("Seleccioná una playlist para ver su recorrido."); self.energy_summary.setObjectName("playlistHint"); self.energy_summary.setAlignment(Qt.AlignRight | Qt.AlignVCenter); energy_heading.addWidget(energy_title); energy_heading.addStretch(1); energy_heading.addWidget(self.energy_summary); energy_layout.addLayout(energy_heading)
        self.energy_segments = QHBoxLayout(); self.energy_segments.setSpacing(4); energy_layout.addLayout(self.energy_segments)
        self.energy_empty = QLabel("Agregá pistas con energía y duración para visualizar la secuencia."); self.energy_empty.setObjectName("playlistEmpty"); self.energy_empty.setAlignment(Qt.AlignCenter); energy_layout.addWidget(self.energy_empty)
        self.energy_section.setVisible(False); layout.addWidget(self.energy_section)
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
        else:
            self.selected_playlist_id = None; self.status.setText("Sin resultados" if query else "Seleccioná una playlist")
            self._render_energy_sequence(())
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
        list_tracks = getattr(self.playlist_service, "list_tracks", None)
        tracks = tuple(list_tracks(self.selected_playlist_id)) if callable(list_tracks) else ()
        self._render_energy_sequence(tracks)

    def _render_energy_sequence(self, tracks):
        """Render the service-owned playlist order without modifying it."""
        while self.energy_segments.count():
            item = self.energy_segments.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.energy_section.setVisible(bool(self.selected_playlist_id))
        self.energy_empty.setVisible(not tracks)
        if not tracks:
            self.energy_summary.setText("Sin pistas para visualizar")
            return
        duration = sum(max(0, int(getattr(track, "duration", 0) or 0)) for track in tracks)
        self.energy_summary.setText(f"{len(tracks)} pistas · {self._format_duration(duration)}")
        for position, track in enumerate(tracks, start=1):
            energy = max(0, min(100, int(getattr(track, "energy", 0) or 0)))
            segment = QPushButton(str(position))
            segment.setObjectName("playlistEnergySegment")
            segment.setProperty("energyBand", self._energy_band(energy))
            segment.setMinimumHeight(26 + round(energy * 0.34))
            segment.setToolTip(self._track_energy_description(track, position, energy))
            segment.setAccessibleName(self._track_energy_description(track, position, energy))
            segment.setEnabled(False)
            stretch = max(1, round(max(0, int(getattr(track, "duration", 0) or 0)) / 60))
            self.energy_segments.addWidget(segment, stretch)

    @staticmethod
    def _energy_band(energy):
        if energy >= 85:
            return "peak"
        if energy >= 65:
            return "high"
        if energy >= 40:
            return "medium"
        return "low"

    @staticmethod
    def _format_duration(seconds):
        minutes, remaining = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours}:{minutes:02d}:{remaining:02d}" if hours else f"{minutes}:{remaining:02d}"

    def _track_energy_description(self, track, position, energy):
        artist = getattr(track, "artist", None) or "Artista desconocido"
        title = getattr(track, "title", None) or "Pista sin título"
        bpm = getattr(track, "bpm", None)
        key = getattr(track, "key", None)
        duration = self._format_duration(max(0, int(getattr(track, "duration", 0) or 0)))
        details = [f"{position}. {artist} — {title}", f"energía {energy}", duration]
        if bpm:
            details.append(f"{bpm:g} BPM")
        if key:
            details.append(str(key))
        return " · ".join(details)
    def closeEvent(self, event): self.playlist_service.close(); super().closeEvent(event)
