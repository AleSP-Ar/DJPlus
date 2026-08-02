"""Import Manager UI surface backed exclusively by ImportManagerAdapter."""

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.import_manager_adapter import ImportManagerAdapter
from PySide6.QtCore import Qt


class ImportManagerPanel(QWidget):
    """Select a folder and display import activity without persistence access."""

    def __init__(self, adapter=None, parent=None):
        super().__init__(parent)
        self.adapter = adapter or ImportManagerAdapter(parent=self)
        self._build_ui()
        self._connect_adapter()
        self._set_running(False)
        self.adapter.load_history()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Import Manager"))

        folder_layout = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Carpeta de música")
        self.browse_button = QPushButton("Seleccionar carpeta")
        self.browse_button.clicked.connect(self.select_folder)
        folder_layout.addWidget(self.folder_input, 1)
        folder_layout.addWidget(self.browse_button)
        layout.addLayout(folder_layout)

        buttons = QHBoxLayout()
        self.start_button = QPushButton("Iniciar importación")
        self.start_button.clicked.connect(self.start_import)
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.cancel_import)
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)

        self.status_label = QLabel("Sin importación activa")
        self.progress_label = QLabel("Procesados: 0 / 0")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.current_file_label = QLabel("Archivo actual: —")
        self.current_file_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.current_file_label)

        layout.addWidget(QLabel("Archivos procesados"))
        self.processed_files = QListWidget()
        self.processed_files.setMaximumHeight(140)
        layout.addWidget(self.processed_files)

        layout.addWidget(QLabel("Errores"))
        self.errors = QListWidget()
        self.errors.setMaximumHeight(100)
        layout.addWidget(self.errors)

        layout.addWidget(QLabel("Historial de importaciones"))
        self.history = QListWidget()
        self.history.itemSelectionChanged.connect(self.load_selected_job_detail)
        self.history.setMaximumHeight(120)
        layout.addWidget(self.history)
        self.recover_button = QPushButton("Recuperar trabajos incompletos")
        self.recover_button.clicked.connect(self.recover_incomplete_jobs)
        layout.addWidget(self.recover_button)
        self.job_detail_label = QLabel("Selecciona un trabajo para ver el detalle")
        self.job_detail_label.setWordWrap(True)
        layout.addWidget(self.job_detail_label)

    def _connect_adapter(self):
        self.adapter.progress_changed.connect(self.update_progress)
        self.adapter.job_status_changed.connect(self.update_job_status)
        self.adapter.file_processed.connect(self.add_processed_file)
        self.adapter.error_reported.connect(self.add_error)
        self.adapter.running_changed.connect(self._set_running)
        self.adapter.history_loaded.connect(self.show_history)
        self.adapter.job_detail_loaded.connect(self.show_job_detail)
        self.adapter.recovery_completed.connect(self.show_recovery)

    def select_folder(self):
        selected = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de música", self.folder_input.text())
        if selected:
            self.folder_input.setText(selected)

    def start_import(self):
        try:
            self.adapter.start(self.folder_input.text())
        except ValueError as error:
            self.status_label.setText(str(error))
            return
        self.processed_files.clear()
        self.errors.clear()
        self.current_file_label.setText("Archivo actual: preparando importación…")

    def cancel_import(self):
        self.adapter.cancel()
        self.status_label.setText("Cancelación solicitada")

    def update_progress(self, progress):
        total = progress.get("total_items", 0)
        processed = progress.get("processed_items", 0)
        self.progress_bar.setRange(0, max(total, 1))
        self.progress_bar.setValue(min(processed, max(total, 1)))
        self.progress_label.setText(f"Procesados: {processed} / {total}")

    def update_job_status(self, status):
        self.status_label.setText(f"Estado: {status}")

    def add_processed_file(self, filepath, event_type):
        labels = {
            "track_imported": "Importado",
            "skipped": "Omitido",
            "failed": "Falló",
        }
        filename = Path(filepath).name
        self.current_file_label.setText(f"Archivo actual: {filename}")
        self.processed_files.addItem(f"{labels[event_type]}: {filename}")

    def add_error(self, filepath, message):
        self.errors.addItem(f"{Path(filepath).name}: {message}")

    def show_history(self, jobs):
        self.history.blockSignals(True)
        self.history.clear()
        for job in jobs:
            item = QListWidgetItem(
                f"#{job.id} · {job.status} · {job.processed_items}/{job.total_items} · errores: {job.error_count}"
            )
            item.setData(Qt.UserRole, job.id)
            self.history.addItem(item)
        self.history.blockSignals(False)

    def load_selected_job_detail(self):
        item = self.history.currentItem()
        if item is not None:
            self.adapter.load_job_detail(item.data(Qt.UserRole))

    def show_job_detail(self, detail):
        failed_items = [item for item in detail.items if item.error_message]
        error_text = "; ".join(f"{Path(item.filepath).name}: {item.error_message}" for item in failed_items)
        self.job_detail_label.setText(
            f"Trabajo #{detail.job.id}: {detail.job.status}. "
            f"{detail.job.processed_items}/{detail.job.total_items} procesados. "
            f"Errores: {detail.job.error_count}. "
            f"{error_text}".strip()
        )

    def recover_incomplete_jobs(self):
        self.adapter.recover_incomplete_jobs()

    def show_recovery(self, jobs):
        if jobs:
            self.status_label.setText(f"{len(jobs)} trabajo(s) recuperado(s)")
        else:
            self.status_label.setText("No hay trabajos incompletos para recuperar")

    def _set_running(self, running):
        self.start_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)
        self.browse_button.setEnabled(not running)
        self.folder_input.setReadOnly(running)

    def closeEvent(self, event):
        if self.adapter.is_running:
            self.adapter.cancel()
        self.adapter.close()
        super().closeEvent(event)
