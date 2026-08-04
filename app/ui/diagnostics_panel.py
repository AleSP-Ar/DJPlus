"""Read-only diagnostics presentation backed by DiagnosticsService."""
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget
from app.services.diagnostics_service import DiagnosticsService


class DiagnosticsPanel(QWidget):
    def __init__(self, diagnostics_service, parent=None):
        super().__init__(parent)
        if not isinstance(diagnostics_service, DiagnosticsService):
            raise TypeError("DiagnosticsPanel requiere DiagnosticsService.")
        self._service = diagnostics_service
        layout = QVBoxLayout(self); layout.setContentsMargins(16, 16, 16, 16); layout.setSpacing(12)
        title = QLabel("Diagnóstico"); title.setObjectName("diagnosticsTitle"); layout.addWidget(title)
        self.status_label = QLabel("Listo para actualizar"); layout.addWidget(self.status_label)
        actions = QHBoxLayout(); self.refresh_button = QPushButton("Actualizar"); self.export_button = QPushButton("Exportar resumen"); actions.addWidget(self.refresh_button); actions.addWidget(self.export_button); actions.addStretch(1); layout.addLayout(actions)
        frame = QFrame(); frame.setObjectName("diagnosticsResult"); box = QVBoxLayout(frame); self.output = QTextEdit(); self.output.setReadOnly(True); self.output.setPlaceholderText("Sin diagnósticos disponibles."); box.addWidget(self.output); layout.addWidget(frame)
        self.refresh_button.clicked.connect(self.refresh); self.export_button.clicked.connect(self.export_text); self.refresh()
    def refresh(self):
        try:
            snapshot = self._service.snapshot(); self.output.setPlainText(snapshot.export_text()); self.status_label.setText("Actualizado · diagnóstico de sólo lectura")
        except Exception as error:
            self.output.setPlainText(str(error)); self.status_label.setText("Error al actualizar diagnóstico")
    def export_text(self):
        self.refresh(); self.status_label.setText("Resumen diagnóstico listo para copiar")
