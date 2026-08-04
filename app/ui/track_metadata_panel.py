"""Confirmed metadata edit surface; no audio-file mutation."""
from datetime import datetime, timezone

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget

from app.services.track_metadata_editor import BulkMetadataEditQueryDTO, TrackMetadataPatchDTO


class TrackMetadataPanel(QWidget):
    """UI-only presentation of the existing preview/confirmation edit flow."""

    def __init__(self, facade, parent=None):
        super().__init__(parent)
        self.facade, self.preview_result, self.proposal = facade, None, None
        self._build_ui()

    def _build_ui(self):
        self.setObjectName("metadataPanel")
        self.setStyleSheet("QFrame#metadataSection { background:#1f2937; border:1px solid #374151; border-radius:8px; } QLabel#metadataTitle { font-size:18px; font-weight:600; } QLabel#metadataStep { color:#93c5fd; font-weight:600; } QLabel#metadataHint { color:#9ca3af; } QPushButton#metadataPrimary { background:#2563eb; color:white; font-weight:600; }")
        layout = QVBoxLayout(self); layout.setContentsMargins(16, 16, 16, 16); layout.setSpacing(12)
        title = QLabel("Editar metadata"); title.setObjectName("metadataTitle"); layout.addWidget(title)
        hint = QLabel("Seleccioná una o varias pistas, revisá los cambios y confirmá sólo después de la vista previa."); hint.setObjectName("metadataHint"); layout.addWidget(hint)

        selection = self._section("1 · Selección de pistas")
        self.ids = QLineEdit(); self.ids.setPlaceholderText("IDs separados por coma, por ejemplo: 12, 18, 42"); self.ids.setAccessibleName("IDs de pistas")
        selection.layout().addWidget(self.ids); self.selection_summary = QLabel("Sin pistas seleccionadas"); self.selection_summary.setObjectName("metadataHint"); selection.layout().addWidget(self.selection_summary); layout.addWidget(selection)

        fields = self._section("2 · Campos actuales y cambios propuestos")
        self.title = QLineEdit(); self.title.setPlaceholderText("Nuevo título"); self.title.setAccessibleName("Título propuesto")
        fields.layout().addWidget(QLabel("Título")); fields.layout().addWidget(self.title)
        self.mixed_fields_label = QLabel("Para varias pistas, la vista previa indica valores mixtos, sin cambios y validaciones."); self.mixed_fields_label.setObjectName("metadataHint"); self.mixed_fields_label.setWordWrap(True); fields.layout().addWidget(self.mixed_fields_label); layout.addWidget(fields)

        actions = QHBoxLayout(); self.preview_button = QPushButton("Generar vista previa"); self.preview_button.setObjectName("metadataPrimary"); self.apply_button = QPushButton("Confirmar y aplicar"); self.apply_button.setEnabled(False); actions.addWidget(self.preview_button); actions.addWidget(self.apply_button); actions.addStretch(1); layout.addLayout(actions)
        result = self._section("3–5 · Vista previa, confirmación y resultado")
        self.output = QTextEdit(); self.output.setReadOnly(True); self.output.setPlaceholderText("La vista previa y los errores aparecerán aquí."); self.output.setMinimumHeight(150); result.layout().addWidget(self.output); layout.addWidget(result)
        self.preview_button.clicked.connect(self.preview); self.apply_button.clicked.connect(self.apply); self.ids.textChanged.connect(self._update_selection_summary)

    def _section(self, heading):
        frame = QFrame(); frame.setObjectName("metadataSection"); box = QVBoxLayout(frame); box.setContentsMargins(12, 10, 12, 10); box.setSpacing(6)
        label = QLabel(heading); label.setObjectName("metadataStep"); box.addWidget(label); return frame

    def _update_selection_summary(self, text):
        values = [value.strip() for value in text.split(",") if value.strip()]
        self.selection_summary.setText("Sin pistas seleccionadas" if not values else ("Edición individual" if len(values) == 1 else f"Edición múltiple: {len(values)} pistas"))

    def preview(self):
        try:
            ids = tuple(int(value.strip()) for value in self.ids.text().split(",") if value.strip())
            query = BulkMetadataEditQueryDTO(ids, TrackMetadataPatchDTO.from_mapping({"title": self.title.text()}))
            self.preview_result = self.facade.preview(query); self.proposal = self.facade.editor.propose(self.preview_result)
            self.output.setPlainText(self.facade.export_preview(self.preview_result)); self.apply_button.setEnabled(True)
        except Exception as error:
            self.output.setPlainText(str(error)); self.apply_button.setEnabled(False)

    def apply(self):
        result = self.facade.editor.apply(self.preview_result, self.proposal, ConfirmationRequestDTO(self.proposal.action_id, datetime.now(timezone.utc)))
        self.output.setPlainText(self.facade.export_result(result)); self.apply_button.setEnabled(False)


from app.services.confirmation_manager import ConfirmationRequestDTO
