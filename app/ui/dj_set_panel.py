"""Read-only presentation of an existing energy-aware DJ set result."""

from collections.abc import Iterable, Mapping

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget


class DJSetPanel(QWidget):
    """Render a SetBuilder result without invoking, altering, or persisting it."""

    select_reference_requested = Signal()
    generate_requested = Signal(object)
    cancel_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._result, self._tracks_by_id, self._show_target, self._reference_track = None, {}, True, None
        self._build_ui()
        self._render_empty()

    def _build_ui(self):
        self.setObjectName("djSetPanel")
        layout = QVBoxLayout(self); layout.setContentsMargins(16, 16, 16, 16); layout.setSpacing(12)
        header = QHBoxLayout(); group = QVBoxLayout()
        title = QLabel("DJ Set"); title.setObjectName("djSetTitle")
        hint = QLabel("Recorrido de energía, capítulos y transiciones del set propuesto."); hint.setObjectName("djSetHint"); hint.setWordWrap(True)
        group.addWidget(title); group.addWidget(hint); header.addLayout(group, 1)
        self.summary = QLabel(); self.summary.setObjectName("djSetSummary"); header.addWidget(self.summary, 0, Qt.AlignRight | Qt.AlignVCenter); layout.addLayout(header)
        toolbar = QFrame(); toolbar.setObjectName("djSetToolbar"); tools = QHBoxLayout(toolbar); tools.setContentsMargins(10, 8, 10, 8)
        self.target_toggle = QCheckBox("Mostrar curva objetivo"); self.target_toggle.setChecked(True); self.target_toggle.setAccessibleName("Mostrar curva objetivo del DJ Set"); self.target_toggle.toggled.connect(self._toggle_target)
        self.status = QLabel(); self.status.setObjectName("djSetHint"); self.status.setWordWrap(True); tools.addWidget(self.target_toggle); tools.addStretch(1); tools.addWidget(self.status); layout.addWidget(toolbar)
        self.reference_bar = QFrame(); self.reference_bar.setObjectName("djSetReferenceBar"); reference_layout = QHBoxLayout(self.reference_bar); reference_layout.setContentsMargins(10, 8, 10, 8)
        self.reference_label = QLabel(); self.reference_label.setObjectName("djSetHint"); self.reference_label.setWordWrap(True)
        self.choose_reference_button = QPushButton("Elegir en Biblioteca"); self.choose_reference_button.setAccessibleName("Elegir pista de referencia en Biblioteca"); self.choose_reference_button.clicked.connect(self.select_reference_requested)
        self.generate_button = QPushButton("Generar DJ Set"); self.generate_button.setObjectName("djSetPrimary"); self.generate_button.setAccessibleName("Generar DJ Set desde la pista de referencia"); self.generate_button.setEnabled(False); self.generate_button.clicked.connect(self._request_generation)
        self.cancel_button = QPushButton("Cancelar"); self.cancel_button.setAccessibleName("Cancelar generación de DJ Set"); self.cancel_button.setVisible(False); self.cancel_button.clicked.connect(self.cancel_requested)
        reference_layout.addWidget(self.reference_label, 1); reference_layout.addWidget(self.choose_reference_button); reference_layout.addWidget(self.generate_button); reference_layout.addWidget(self.cancel_button); layout.addWidget(self.reference_bar)
        self.journey_section = QFrame(); self.journey_section.setObjectName("djSetJourneySection"); journey = QVBoxLayout(self.journey_section); journey.setContentsMargins(12, 10, 12, 10); journey.setSpacing(6)
        journey_header = QHBoxLayout(); journey_title = QLabel("Viaje de energía"); journey_title.setObjectName("djSetJourneyTitle"); self.journey_legend = QLabel("Real · Objetivo"); self.journey_legend.setObjectName("djSetHint"); journey_header.addWidget(journey_title); journey_header.addStretch(1); journey_header.addWidget(self.journey_legend); journey.addLayout(journey_header)
        self.energy_segments = QHBoxLayout(); self.energy_segments.setSpacing(4); journey.addLayout(self.energy_segments)
        self.phase_labels = QHBoxLayout(); self.phase_labels.setSpacing(4); journey.addLayout(self.phase_labels); layout.addWidget(self.journey_section)
        section = QFrame(); section.setObjectName("djSetTrackSection"); rows = QVBoxLayout(section); rows.setContentsMargins(12, 10, 12, 10); rows.setSpacing(6); rows.addWidget(QLabel("Secuencia propuesta"))
        self.track_list = QListWidget(); self.track_list.setAccessibleName("Secuencia propuesta del DJ Set"); self.track_list.setMinimumHeight(180); rows.addWidget(self.track_list); layout.addWidget(section, 1)

    def set_result(self, result, tracks: Mapping[int, object] | Iterable[object] = ()):
        """Present an already-computed result and optional display metadata by track id."""
        self._result = result
        self._tracks_by_id = dict(tracks) if isinstance(tracks, Mapping) else {getattr(track, "id", None): track for track in tracks if isinstance(getattr(track, "id", None), int)}
        self._render_result()

    def clear_result(self):
        self._result, self._tracks_by_id = None, {}
        self._render_empty()

    def set_reference_track(self, track):
        """Keep the selected library track until the user explicitly generates a set."""
        if not isinstance(getattr(track, "id", None), int):
            return
        self._reference_track = track
        artist = getattr(track, "artist", None) or "Artista desconocido"
        title = getattr(track, "title", None) or "Sin título"
        self.reference_label.setText(f"Referencia: {artist} — {title}")
        self.generate_button.setEnabled(True)

    def _request_generation(self):
        if self._reference_track is not None:
            self.generate_requested.emit(self._reference_track)

    def set_generation_running(self, running):
        """Expose a responsive, cancellable read-only generation state."""
        running = bool(running)
        self.choose_reference_button.setEnabled(not running)
        self.generate_button.setEnabled(not running and self._reference_track is not None)
        self.cancel_button.setVisible(running)
        if running:
            self.status.setText("Generando propuesta de DJ Set… podés cancelar sin modificar tu biblioteca.")

    def _toggle_target(self, visible):
        self._show_target = bool(visible); self._render_result()

    def _render_empty(self):
        self.summary.setText("Sin set generado"); self.status.setText("Elegí una pista de referencia en Biblioteca y generá una propuesta de sólo lectura."); self.reference_label.setText("Referencia: todavía no seleccionada" if self._reference_track is None else self.reference_label.text()); self.journey_section.setVisible(False); self.track_list.clear()
        item = QListWidgetItem("Todavía no hay una secuencia para visualizar."); item.setFlags(Qt.NoItemFlags); self.track_list.addItem(item)

    def _render_result(self):
        journey = getattr(self._result, "journey", None); sequence = tuple(getattr(self._result, "sequence", ()) or ()); targets = tuple(getattr(journey, "target_energy_by_position", ()) or ())
        if journey is None or not sequence:
            self._render_empty(); return
        self.journey_section.setVisible(True); partial = bool(getattr(getattr(journey, "set_plan", None), "is_partial", False))
        self.summary.setText(f"{len(sequence)} pistas" + (" · parcial" if partial else " · completo")); deviations = tuple(getattr(journey, "deviations", ()) or ()); self.status.setText(" · ".join(deviations) if deviations else "Sin desvíos de energía reportados."); self.journey_legend.setText("Real · Objetivo" if self._show_target else "Energía real")
        self._clear_layout(self.energy_segments); self._clear_layout(self.phase_labels); self.track_list.clear()
        for item in sequence:
            track = self._tracks_by_id.get(getattr(item, "track_id", None)); energy = self._energy(track); position = getattr(item, "position", 0); target = targets[position - 1] if position and position <= len(targets) else None
            segment = QPushButton(str(position or "?")); segment.setObjectName("djSetEnergySegment"); segment.setProperty("energyBand", self._energy_band(energy)); segment.setProperty("targetVisible", self._show_target); segment.setMinimumHeight(26 + round(energy * .34)); description = self._track_description(track, item, energy, target); segment.setToolTip(description); segment.setAccessibleName(description); segment.setEnabled(False); self.energy_segments.addWidget(segment, max(1, round(self._duration(track) / 60)))
            row = QListWidgetItem(description); row.setData(Qt.UserRole, getattr(item, "track_id", None)); self.track_list.addItem(row)
        for phase in tuple(getattr(journey, "phases", ()) or ()):
            label = QLabel(str(getattr(phase, "name", "fase")).replace("-", " ").title()); label.setObjectName("djSetPhaseLabel"); label.setAlignment(Qt.AlignCenter); self.phase_labels.addWidget(label, max(1, int(getattr(phase, "end_position", 0)) - int(getattr(phase, "start_position", 0)) + 1))

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None: item.widget().deleteLater()

    @staticmethod
    def _energy(track): return max(0, min(100, int(getattr(track, "energy", 0) or 0)))
    @staticmethod
    def _duration(track): return max(0, int(getattr(track, "duration", 0) or 0))
    @staticmethod
    def _energy_band(energy): return "peak" if energy >= 85 else "high" if energy >= 65 else "medium" if energy >= 40 else "low"

    def _track_description(self, track, item, energy, target):
        position = getattr(item, "position", "?"); artist = getattr(track, "artist", None) or "Artista desconocido"; title = getattr(track, "title", None) or f"Pista {getattr(item, 'track_id', '?')}"; details = [f"{position}. {artist} — {title}", f"energía {energy}"]
        if self._show_target and target is not None: details.append(f"objetivo {target:g}")
        bpm, key = getattr(track, "bpm", None), getattr(track, "key", None)
        if bpm: details.append(f"{bpm:g} BPM")
        if key: details.append(str(key))
        return " · ".join(details)
