"""Minimal PySide6 panel for the explicitly local, read-only assistant MVP."""

from PySide6.QtCore import QThread
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget

from app.services.local_assistant_mvp import LocalAssistantMVP
from app.services.diagnostics_service import DiagnosticsService
from .assistant_worker import AssistantWorker


class AssistantPanel(QWidget):
    """Display local assistant answers and read-only tool results without actions."""

    def __init__(self, assistant_mvp, parent=None, diagnostics_service=None):
        super().__init__(parent)
        if not isinstance(assistant_mvp, LocalAssistantMVP):
            raise TypeError("AssistantPanel requiere LocalAssistantMVP.")
        if diagnostics_service is not None and not isinstance(diagnostics_service, DiagnosticsService):
            raise TypeError("diagnostics_service debe ser DiagnosticsService o nulo.")
        self._assistant_mvp = assistant_mvp
        self._diagnostics_service = diagnostics_service
        self._thread = None
        self._worker = None
        self.setObjectName("assistantPanel")
        self.setStyleSheet("QFrame#assistantSection { background:#10182A; border:1px solid #253550; border-radius:9px; } QLabel#assistantTitle { color:#F1F5FF; font-size:19px; font-weight:700; } QLabel#assistantHint { color:#8FA1BD; } QPushButton#assistantPrimary { background:#6259E8; border:1px solid #817AFF; color:white; font-weight:600; }")
        layout = QVBoxLayout(self); layout.setContentsMargins(16,16,16,16); layout.setSpacing(12)
        title = QLabel("Assistant local"); title.setObjectName("assistantTitle"); layout.addWidget(title)
        hint = QLabel("Conversación y herramientas de sólo lectura. Las acciones se muestran separadas del resultado."); hint.setObjectName("assistantHint"); layout.addWidget(hint)
        conversation = QFrame(); conversation.setObjectName("assistantSection"); conversation_layout = QVBoxLayout(conversation); conversation_layout.setContentsMargins(12,10,12,10)
        conversation_layout.addWidget(QLabel("Conversación"))
        row = QHBoxLayout()
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Consultá la biblioteca…")
        self.send_button = QPushButton("Consultar")
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setEnabled(False)
        row.addWidget(self.query_input, 1)
        self.send_button.setObjectName("assistantPrimary"); row.addWidget(self.send_button)
        row.addWidget(self.cancel_button)
        conversation_layout.addLayout(row)
        self.status_label = QLabel("Listo")
        conversation_layout.addWidget(self.status_label)
        self.diagnostics_label = QLabel("Diagnostico: no disponible")
        conversation_layout.addWidget(self.diagnostics_label)
        layout.addWidget(conversation)
        result = QFrame(); result.setObjectName("assistantSection"); result_layout = QVBoxLayout(result); result_layout.setContentsMargins(12,10,12,10); result_layout.addWidget(QLabel("Resultados y acciones disponibles"))
        self.response_view = QTextEdit()
        self.response_view.setReadOnly(True)
        result_layout.addWidget(self.response_view); layout.addWidget(result)
        self.send_button.clicked.connect(self._submit)
        self.cancel_button.clicked.connect(self._cancel)
        self.query_input.returnPressed.connect(self._submit)
        self._refresh_diagnostics()

    def _submit(self):
        query = self.query_input.text().strip()
        if not query:
            return
        if self._thread is not None:
            return
        self.send_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.status_label.setText("Procesando…")
        self._thread = QThread(self)
        self._worker = AssistantWorker(self._assistant_mvp, query)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.result.connect(self._show_result)
        self._worker.error.connect(self._show_error)
        self._worker.cancelled.connect(self._show_cancelled)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._cleanup_worker)
        self._thread.start()

    def _cancel(self):
        if self._worker is not None:
            self._worker.cancel()
            self.cancel_button.setEnabled(False)
            self.status_label.setText("Cancelando…")

    def _show_result(self, result):
        lines = [result.assistant_response.content] if result.assistant_response is not None else []
        for tool in result.tool_results:
            if not tool.success:
                continue
            lines.append(tool.result.response)
            search_result = tool.result.data_used.get("search_result")
            if search_result is not None and search_result.page_items:
                lines.extend(
                    f"- {item.artist} — {item.title}" for item in search_result.page_items
                )
            recommendation_page = tool.result.data_used.get("recommendation_page")
            if recommendation_page is not None:
                lines.extend(
                    f"#{item.rank} · pista {item.candidate_track_id} · score {item.score} · confianza {item.confidence:.2f}"
                    for item in recommendation_page.recommendations
                )
            set_builder_result = tool.result.data_used.get("set_builder_result")
            if set_builder_result is not None:
                lines.extend(
                    f"#{item.position} · pista {item.track_id} · score {item.score} · confianza {item.confidence}"
                    for item in set_builder_result.sequence
                )
            music_batch = tool.result.data_used.get("music_analysis_batch")
            if music_batch is not None:
                lines.extend(
                    f"Pista {item.track_id}: {item.status} · BPM {item.bpm} · key {item.key} · energia {item.energy}"
                    for item in music_batch.items
                )
        self.response_view.setPlainText("\n\n".join(lines) or "Sin respuesta local.")
        self.status_label.setText("Listo")
        self._refresh_diagnostics()

    def _show_error(self, message):
        self.response_view.setPlainText(message)
        self.status_label.setText("Error")
        self._refresh_diagnostics()

    def _show_cancelled(self):
        self.response_view.setPlainText("Consulta cancelada.")
        self.status_label.setText("Cancelada")
        self._refresh_diagnostics()

    def _cleanup_worker(self):
        self._thread = None
        self._worker = None
        self.send_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self._refresh_diagnostics()

    def _refresh_diagnostics(self):
        if self._diagnostics_service is None:
            return
        snapshot = self._diagnostics_service.snapshot()
        self.diagnostics_label.setText(
            f"Diagnostico: errores {snapshot.errors} · cancelaciones {snapshot.cancellations} · timeouts {snapshot.timeouts}"
        )

    def closeEvent(self, event: QCloseEvent):
        if self._thread is not None and self._thread.isRunning():
            self._cancel()
            if not self._thread.wait(2000):
                self.status_label.setText("Esperando cancelacion segura…")
                event.ignore()
                return
        event.accept()
