"""Minimal PySide6 panel for the explicitly local, read-only assistant MVP."""

from PySide6.QtCore import QThread
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget

from app.services.local_assistant_mvp import LocalAssistantMVP
from .assistant_worker import AssistantWorker


class AssistantPanel(QWidget):
    """Display local assistant answers and read-only tool results without actions."""

    def __init__(self, assistant_mvp, parent=None):
        super().__init__(parent)
        if not isinstance(assistant_mvp, LocalAssistantMVP):
            raise TypeError("AssistantPanel requiere LocalAssistantMVP.")
        self._assistant_mvp = assistant_mvp
        self._thread = None
        self._worker = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Asistente local (Ollama / solo lectura)"))
        row = QHBoxLayout()
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Consultá la biblioteca…")
        self.send_button = QPushButton("Consultar")
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setEnabled(False)
        row.addWidget(self.query_input, 1)
        row.addWidget(self.send_button)
        row.addWidget(self.cancel_button)
        layout.addLayout(row)
        self.status_label = QLabel("Listo")
        layout.addWidget(self.status_label)
        self.response_view = QTextEdit()
        self.response_view.setReadOnly(True)
        layout.addWidget(self.response_view)
        self.send_button.clicked.connect(self._submit)
        self.cancel_button.clicked.connect(self._cancel)
        self.query_input.returnPressed.connect(self._submit)

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
        self.response_view.setPlainText("\n\n".join(lines) or "Sin respuesta local.")
        self.status_label.setText("Listo")

    def _show_error(self, message):
        self.response_view.setPlainText(message)
        self.status_label.setText("Error")

    def _show_cancelled(self):
        self.response_view.setPlainText("Consulta cancelada.")
        self.status_label.setText("Cancelada")

    def _cleanup_worker(self):
        self._thread = None
        self._worker = None
        self.send_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

    def closeEvent(self, event: QCloseEvent):
        if self._thread is not None and self._thread.isRunning():
            self._cancel()
            if not self._thread.wait(2000):
                self.status_label.setText("Esperando cancelacion segura…")
                event.ignore()
                return
        event.accept()
