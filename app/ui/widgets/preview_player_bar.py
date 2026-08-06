"""Functional, service-driven controls for the local preview player."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLayout, QPushButton, QSlider, QVBoxLayout, QWidget

from app.services.preview_player import PreviewPlayerState, PreviewTrackDTO


def format_preview_time(milliseconds: int | None) -> str:
    """Render a safe duration without exposing media paths or metadata."""
    if not isinstance(milliseconds, (int, float)) or isinstance(milliseconds, bool) or milliseconds <= 0:
        return "--:--"
    seconds = int(milliseconds // 1000)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"


class PreviewPlayerBar(QWidget):
    """Persistent view adapter; it owns widgets, never multimedia resources."""

    _service_event = Signal(str, object)
    _COMPACT_WIDTH = 760

    def __init__(self, preview_player_service, parent=None):
        super().__init__(parent)
        self._service = preview_player_service
        self._closed, self._dragging, self._updating, self._compact_layout = False, False, False, None
        self._unsubscribe = None
        self.setObjectName("previewPlayerBar")
        self.setAccessibleName("Controles de preescucha")
        self.setToolTip("Controles de preescucha local")
        self.setMinimumWidth(0)
        self.setMinimumHeight(112)
        self._build_ui()
        self._service_event.connect(self._apply_service_event)
        self._unsubscribe = self._service.subscribe(self._receive_service_event)
        self.refresh_devices()
        self._apply_snapshot(self._service.snapshot())

    def _build_ui(self):
        self.setStyleSheet(
            """
            QWidget#previewPlayerBar { background: #1f2937; border: 1px solid #374151; border-radius: 8px; }
            QFrame#previewTrackBlock { background: #111827; border-radius: 6px; padding: 2px; }
            QLabel#previewTrackLabel { color: #f9fafb; font-weight: 600; }
            QLabel#previewTrackHint, QLabel#previewControlLabel { color: #9ca3af; }
            QLabel#previewState { border-radius: 9px; padding: 2px 8px; font-weight: 600; }
            QLabel#previewState[previewState="empty"], QLabel#previewState[previewState="closed"] { color: #cbd5e1; background: #334155; }
            QLabel#previewState[previewState="loading"] { color: #fef3c7; background: #92400e; }
            QLabel#previewState[previewState="ready"], QLabel#previewState[previewState="stopped"], QLabel#previewState[previewState="paused"], QLabel#previewState[previewState="ended"] { color: #dbeafe; background: #1e40af; }
            QLabel#previewState[previewState="playing"] { color: #dcfce7; background: #166534; }
            QLabel#previewState[previewState="error"], QLabel#previewState[previewState="degraded"] { color: #fee2e2; background: #991b1b; }
            QLabel#previewError { color: #fca5a5; }
            QPushButton#previewPlayButton { font-weight: 600; min-width: 92px; }
            QSlider::groove:horizontal { height: 4px; border-radius: 2px; background: #475569; }
            QSlider::handle:horizontal { width: 14px; margin: -5px 0; border-radius: 7px; background: #60a5fa; }
            """
        )
        root = QVBoxLayout(self)
        root.setSizeConstraint(QLayout.SetNoConstraint)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        track_block = QFrame()
        track_block.setObjectName("previewTrackBlock")
        track_block.setMinimumWidth(0)
        track_layout = QVBoxLayout(track_block)
        track_layout.setContentsMargins(10, 6, 10, 6)
        track_layout.setSpacing(1)
        self.track_label = QLabel("Sin pista cargada")
        self.track_label.setObjectName("previewTrackLabel")
        self.track_label.setAccessibleName("Pista cargada")
        self.track_label.setMinimumWidth(0)
        self.track_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        track_layout.addWidget(self.track_label)
        title_row.addWidget(track_block, 1)
        root.addLayout(title_row)

        self.track_hint_label = QLabel("Cargá una pista desde Biblioteca para preescucharla.")
        self.track_hint_label.setObjectName("previewTrackHint")
        self.track_hint_label.setWordWrap(True)
        self.track_hint_label.setMinimumWidth(0)
        root.addWidget(self.track_hint_label)

        controls_container = QVBoxLayout()
        controls_container.setSpacing(6)
        self.state_label = QLabel("Sin pista cargada")
        self.state_label.setObjectName("previewState")
        self.state_label.setAccessibleName("Estado de preescucha")
        controls_container.addWidget(self.state_label, alignment=Qt.AlignRight | Qt.AlignVCenter)

        self.controls = QGridLayout()
        self.controls.setHorizontalSpacing(8)
        self.controls.setVerticalSpacing(6)
        controls_container.addLayout(self.controls)
        root.addLayout(controls_container)
        self.play_button = QPushButton("Reproducir")
        self.play_button.setObjectName("previewPlayButton")
        self.play_button.setAccessibleName("Reproducir o pausar")
        self.play_button.setToolTip("Reproducir o pausar la pista cargada")
        self.stop_button = QPushButton("Detener")
        self.stop_button.setAccessibleName("Detener preescucha")
        self.stop_button.setToolTip("Detener la preescucha")
        self.current_time_label = QLabel("--:--")
        self.current_time_label.setAccessibleName("Tiempo actual")
        self.duration_label = QLabel("--:--")
        self.duration_label.setAccessibleName("Duración")
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setAccessibleName("Posición de reproducción")
        self.position_slider.setToolTip("Arrastre y suelte para buscar una posición")
        self.position_slider.setRange(0, 1)
        self.volume_label = QLabel("Volumen")
        self.volume_label.setObjectName("previewControlLabel")
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setAccessibleName("Volumen de preescucha")
        self.volume_slider.setToolTip("Volumen privado de la preescucha")
        self.volume_slider.setRange(0, 100)
        self.device_label = QLabel("Salida")
        self.device_label.setObjectName("previewControlLabel")
        self.device_combo = QComboBox()
        self.device_combo.setAccessibleName("Dispositivo de salida")
        self.device_combo.setToolTip("Seleccionar salida de audio de preescucha")
        self._arrange_controls(False)

        self.error_label = QLabel("")
        self.error_label.setObjectName("previewError")
        self.error_label.setAccessibleName("Error de preescucha")
        self.error_label.setWordWrap(True)
        root.addWidget(self.error_label)

        self.play_button.clicked.connect(self.toggle_play_pause)
        self.stop_button.clicked.connect(self.stop)
        self.position_slider.sliderPressed.connect(self._begin_seek)
        self.position_slider.sliderMoved.connect(self._preview_seek_time)
        self.position_slider.sliderReleased.connect(self._finish_seek)
        self.volume_slider.valueChanged.connect(self._set_volume)
        self.volume_slider.sliderReleased.connect(self._save_volume_preferences)
        self.device_combo.currentIndexChanged.connect(self._select_device)
        self.setFocusPolicy(Qt.StrongFocus)
        QWidget.setTabOrder(self.play_button, self.stop_button)
        QWidget.setTabOrder(self.stop_button, self.position_slider)
        QWidget.setTabOrder(self.position_slider, self.volume_slider)
        QWidget.setTabOrder(self.volume_slider, self.device_combo)

    def _arrange_controls(self, compact):
        """Keep every control available while moving secondary controls below on narrow windows."""
        if self._compact_layout is compact:
            return
        self._compact_layout = compact
        while self.controls.count():
            self.controls.takeAt(0)
        self.controls.addWidget(self.play_button, 0, 0)
        self.controls.addWidget(self.stop_button, 0, 1)
        self.controls.addWidget(self.current_time_label, 0, 2)
        self.controls.addWidget(self.position_slider, 0, 3)
        self.controls.addWidget(self.duration_label, 0, 4)
        self.controls.setColumnStretch(3, 1)
        if compact:
            self.controls.addWidget(self.volume_label, 1, 0)
            self.controls.addWidget(self.volume_slider, 1, 1, 1, 2)
            self.controls.addWidget(self.device_label, 1, 3)
            self.controls.addWidget(self.device_combo, 1, 4)
            self.volume_slider.setMinimumWidth(80)
            self.volume_slider.setMaximumWidth(16777215)
            self.device_combo.setMinimumWidth(130)
            self.device_combo.setMaximumWidth(16777215)
        else:
            self.controls.addWidget(self.volume_label, 0, 5)
            self.controls.addWidget(self.volume_slider, 0, 6)
            self.controls.addWidget(self.device_label, 0, 7)
            self.controls.addWidget(self.device_combo, 0, 8)
            self.volume_slider.setMinimumWidth(80)
            self.volume_slider.setMaximumWidth(110)
            self.device_combo.setMinimumWidth(180)
            self.device_combo.setMaximumWidth(280)

    def resizeEvent(self, event):
        self._arrange_controls(event.size().width() < self._COMPACT_WIDTH)
        super().resizeEvent(event)

    def load_track(self, track: PreviewTrackDTO):
        """Load explicitly; this deliberately does not start audio."""
        if self._closed:
            return
        try:
            self._service.load_track(track)
            self.error_label.setText("")
        except Exception:
            self._apply_snapshot(self._service.snapshot())
            self.error_label.setText("No se pudo cargar la pista seleccionada.")

    def refresh_devices(self):
        if self._closed:
            return
        self._updating = True
        try:
            self.device_combo.clear()
            self.device_combo.addItem("Usar salida predeterminada", "__default__")
            for device in self._service.list_output_devices():
                label = device.description[:100] or "Salida sin nombre"
                if device.is_default:
                    label += " (predeterminada)"
                if not device.is_available:
                    label += " (no disponible)"
                self.device_combo.addItem(label, device.device_id)
        except Exception:
            self.device_combo.clear()
            self.device_combo.addItem("Sin salida de audio", "")
        finally:
            self._updating = False

    def toggle_play_pause(self):
        if self._closed:
            return
        try:
            snapshot = self._service.snapshot()
            if snapshot.state == PreviewPlayerState.PLAYING:
                self._service.pause()
            elif snapshot.state in {PreviewPlayerState.READY, PreviewPlayerState.STOPPED, PreviewPlayerState.PAUSED, PreviewPlayerState.ENDED}:
                self._service.play()
        except Exception:
            self.error_label.setText("No se pudo cambiar la reproducción.")

    def stop(self):
        if self._closed:
            return
        try:
            self._service.stop()
        except Exception:
            self.error_label.setText("No se pudo detener la reproducción.")

    def _begin_seek(self):
        self._dragging = True

    def _preview_seek_time(self, value):
        self.current_time_label.setText(format_preview_time(value))

    def _finish_seek(self):
        value = self.position_slider.value()
        self._dragging = False
        try:
            self._service.seek(value)
        except Exception:
            self.error_label.setText("No se pudo cambiar la posición.")

    def _set_volume(self, value):
        if self._updating or self._closed:
            return
        try:
            self._service.set_volume(value / 100.0)
        except Exception:
            self.error_label.setText("No se pudo cambiar el volumen.")

    def _save_volume_preferences(self):
        if self._closed:
            return
        try:
            self._service.save_preferences()
        except Exception:
            pass

    def _select_device(self, _index):
        if self._updating or self._closed:
            return
        device_id = self.device_combo.currentData()
        try:
            if device_id == "__default__":
                self._service.use_default_output_device()
            elif device_id:
                self._service.select_output_device(device_id)
            else:
                return
            self._service.save_preferences()
        except Exception:
            self.error_label.setText("La salida seleccionada no está disponible.")
            self.refresh_devices()

    def _receive_service_event(self, event, snapshot):
        if not self._closed:
            self._service_event.emit(event, snapshot)

    @Slot(str, object)
    def _apply_service_event(self, _event, snapshot):
        if not self._closed:
            self._apply_snapshot(snapshot)

    def _apply_snapshot(self, snapshot):
        if self._closed:
            return
        track = snapshot.track
        title = track.title if track and track.title else "Pista sin título"
        artist = track.artist if track and track.artist else "Artista desconocido"
        self.track_label.setText("Sin pista cargada" if track is None else f"{artist} — {title}")
        self.track_hint_label.setText(
            "Cargá una pista desde Biblioteca para preescucharla."
            if track is None else "Carga explícita: la reproducción nunca comienza automáticamente."
        )
        duration = max(0, snapshot.duration_ms)
        if not self._dragging:
            self._updating = True
            self.position_slider.setRange(0, max(1, duration))
            self.position_slider.setValue(min(snapshot.position_ms, max(1, duration)))
            self._updating = False
            self.current_time_label.setText(format_preview_time(snapshot.position_ms))
        self.duration_label.setText(format_preview_time(duration))
        self._updating = True
        self.volume_slider.setValue(round(snapshot.volume * 100))
        self._updating = False
        has_track = track is not None and snapshot.state not in {PreviewPlayerState.ERROR, PreviewPlayerState.CLOSED}
        can_play = has_track and snapshot.output_available and snapshot.state in {PreviewPlayerState.READY, PreviewPlayerState.STOPPED, PreviewPlayerState.PLAYING, PreviewPlayerState.PAUSED, PreviewPlayerState.ENDED}
        self.play_button.setEnabled(can_play)
        self.stop_button.setEnabled(has_track and snapshot.state not in {PreviewPlayerState.LOADING})
        self.position_slider.setEnabled(has_track and snapshot.seekable and duration > 0)
        self.play_button.setText("Pausar" if snapshot.state == PreviewPlayerState.PLAYING else "Reproducir")
        self._set_visual_state(snapshot)
        if snapshot.error:
            self.error_label.setText("La preescucha no está disponible." if snapshot.error == "backend_unavailable" else "Ocurrió un error de reproducción.")
        else:
            self.error_label.setText("")
        self._select_current_device(snapshot.output_device_id)

    def _set_visual_state(self, snapshot):
        state_key = "degraded" if not snapshot.output_available else snapshot.state.value.lower()
        self.state_label.setProperty("previewState", state_key)
        self.style().unpolish(self.state_label)
        self.style().polish(self.state_label)
        self.state_label.setText(self._state_text(snapshot))

    def _select_current_device(self, device_id):
        self._updating = True
        index = self.device_combo.findData(device_id) if device_id else 0
        if index >= 0:
            self.device_combo.setCurrentIndex(index)
        self._updating = False

    @staticmethod
    def _state_text(snapshot):
        if not snapshot.output_available:
            return "Modo degradado · sin salida de audio"
        return {
            PreviewPlayerState.EMPTY: "Sin pista cargada",
            PreviewPlayerState.LOADING: "Cargando",
            PreviewPlayerState.READY: "Lista para reproducir",
            PreviewPlayerState.PLAYING: "Reproduciendo",
            PreviewPlayerState.PAUSED: "Pausada",
            PreviewPlayerState.STOPPED: "Detenida",
            PreviewPlayerState.ENDED: "Finalizada",
            PreviewPlayerState.ERROR: "Error de reproducción",
            PreviewPlayerState.CLOSED: "Cerrada",
        }[snapshot.state]

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            self.toggle_play_pause()
            event.accept()
            return
        if event.key() == Qt.Key_Escape:
            self.stop()
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        self._closed = True
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        super().closeEvent(event)
