from PySide6.QtWidgets import QComboBox, QFormLayout, QFrame, QLabel, QPushButton, QVBoxLayout, QWidget


class SettingsPanel(QWidget):
    """Small settings surface for persistent application preferences."""

    def __init__(self, preview_player_service=None, parent=None):
        super().__init__(parent)
        self._service = preview_player_service
        self._updating = False
        self.setObjectName("settingsPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        title = QLabel("Ajustes")
        title.setObjectName("settingsTitle")
        layout.addWidget(title)
        description = QLabel("Configurá la preescucha y las preferencias de DJPlus.")
        description.setObjectName("settingsDescription")
        layout.addWidget(description)

        audio = QFrame()
        audio.setObjectName("settingsAudio")
        form = QFormLayout(audio)
        form.setContentsMargins(16, 14, 16, 14)
        self.output_combo = QComboBox()
        self.output_combo.setAccessibleName("Dispositivo de salida de audio")
        self.output_combo.setToolTip("Seleccionar salida de audio de preescucha")
        self.refresh_button = QPushButton("Actualizar dispositivos")
        self.status_label = QLabel("")
        self.status_label.setObjectName("settingsStatus")
        form.addRow("Salida de audio", self.output_combo)
        form.addRow("", self.refresh_button)
        form.addRow("", self.status_label)
        layout.addWidget(audio)
        layout.addStretch(1)

        self.output_combo.currentIndexChanged.connect(self._select_output)
        self.refresh_button.clicked.connect(self.refresh_devices)
        self.refresh_devices()

    def refresh_devices(self):
        self._updating = True
        try:
            self.output_combo.clear()
            if self._service is None:
                self.output_combo.addItem("Sin salida de audio disponible", "")
                self.output_combo.setEnabled(False)
                self.status_label.setText("La preescucha no está disponible en esta sesión.")
                return
            self.output_combo.addItem("Usar salida predeterminada", "__default__")
            for device in self._service.list_output_devices():
                label = device.description[:100] or "Salida sin nombre"
                if device.is_default:
                    label += " (predeterminada)"
                if not device.is_available:
                    label += " (no disponible)"
                self.output_combo.addItem(label, device.device_id)
            snapshot = self._service.snapshot()
            index = self.output_combo.findData(snapshot.output_device_id) if snapshot.output_device_id else 0
            self.output_combo.setCurrentIndex(index if index >= 0 else 0)
            self.output_combo.setEnabled(True)
            self.status_label.setText("")
        except Exception:
            self.output_combo.clear()
            self.output_combo.addItem("Sin salida de audio disponible", "")
            self.output_combo.setEnabled(False)
            self.status_label.setText("No se pudieron consultar los dispositivos de audio.")
        finally:
            self._updating = False

    def _select_output(self, _index):
        if self._updating or self._service is None:
            return
        device_id = self.output_combo.currentData()
        try:
            if device_id == "__default__":
                self._service.use_default_output_device()
            elif device_id:
                self._service.select_output_device(device_id)
            else:
                return
            self._service.save_preferences()
            self.status_label.setText("Salida de audio guardada.")
        except Exception:
            self.status_label.setText("La salida seleccionada no está disponible.")
            self.refresh_devices()
