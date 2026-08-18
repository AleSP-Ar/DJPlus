"""Simple import screen backed exclusively by ImportManagerAdapter."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton, QVBoxLayout, QWidget

from app.services.settings_service import SettingsService
from app.ui.import_manager_adapter import ImportManagerAdapter


class ImportManagerPanel(QWidget):
    """Choose an import folder and show only the useful import summary."""

    def __init__(self, adapter=None, settings_service=None, parent=None):
        super().__init__(parent)
        self.adapter = adapter or ImportManagerAdapter(parent=self)
        self.settings_service = settings_service
        self._duplicate_count = 0
        self._build_ui()
        self._connect_adapter()
        self._set_running(False)
        self._refresh_last_import_summary()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        self.setObjectName("importManagerPanel")
        self.setStyleSheet("QFrame#importSection { background:#10182A; border:1px solid #253550; border-radius:9px; } QLabel#importTitle { color:#F1F5FF; font-size:19px; font-weight:700; } QLabel#importHint { color:#8FA1BD; } QPushButton#importPrimary { background:#6259E8; border:1px solid #817AFF; color:white; font-weight:600; }")

        title = QLabel("Importar música"); title.setObjectName("importTitle"); layout.addWidget(title)
        hint = QLabel("Elegí una carpeta para analizar sus archivos y agregarlos a tu biblioteca."); hint.setObjectName("importHint"); layout.addWidget(hint)
        folder_layout = QHBoxLayout()
        self.folder_input = QLineEdit(); self.folder_input.setPlaceholderText("Carpeta de música")
        self.browse_button = QPushButton("Seleccionar carpeta"); self.browse_button.clicked.connect(self.select_folder)
        folder_layout.addWidget(self.folder_input, 1); folder_layout.addWidget(self.browse_button); layout.addLayout(folder_layout)

        default_section = QFrame(); default_section.setObjectName("importSection")
        default_layout = QVBoxLayout(default_section); default_layout.setContentsMargins(12, 10, 12, 10)
        default_layout.addWidget(QLabel("Carpeta predeterminada"))
        default_hint = QLabel("La carpeta elegida aquí se usará automáticamente al abrir DJPlus."); default_hint.setObjectName("importHint"); default_hint.setWordWrap(True); default_layout.addWidget(default_hint)
        default_row = QHBoxLayout()
        self.default_folder_combo = QComboBox(); self.default_folder_combo.setAccessibleName("Carpetas de música configuradas"); self.default_folder_combo.setMinimumHeight(30); self.default_folder_combo.currentIndexChanged.connect(self.use_selected_default_folder)
        self.set_default_folder_button = QPushButton("Usar esta carpeta"); self.set_default_folder_button.setAccessibleName("Definir carpeta de música predeterminada"); self.set_default_folder_button.clicked.connect(self.save_default_folder)
        default_row.addWidget(self.default_folder_combo, 1); default_row.addWidget(self.set_default_folder_button); default_layout.addLayout(default_row); layout.addWidget(default_section)

        automation_hint = QLabel("DJPlus analiza, completa metadata y respalda la biblioteca automáticamente."); automation_hint.setObjectName("importHint"); automation_hint.setWordWrap(True); layout.addWidget(automation_hint)
        buttons = QHBoxLayout()
        self.start_button = QPushButton("Analizar e importar"); self.start_button.setObjectName("importPrimary"); self.start_button.clicked.connect(self.start_import)
        self.cancel_button = QPushButton("Cancelar"); self.cancel_button.clicked.connect(self.cancel_import)
        buttons.addWidget(self.start_button); buttons.addWidget(self.cancel_button); layout.addLayout(buttons)

        self.status_label = QLabel("Sin importación activa")
        self.progress_label = QLabel("Total de archivos: 0 / 0")
        self.progress_bar = QProgressBar(); self.progress_bar.setRange(0, 1); self.progress_bar.setValue(0)
        self.current_file_label = QLabel("Archivo actual: —"); self.current_file_label.setWordWrap(True)
        self.current_file_progress_label = QLabel("Archivo actual: esperando")
        self.current_file_progress_bar = QProgressBar(); self.current_file_progress_bar.setRange(0, 2); self.current_file_progress_bar.setValue(0)
        for widget in (self.status_label, self.progress_label, self.progress_bar, self.current_file_label, self.current_file_progress_label, self.current_file_progress_bar): layout.addWidget(widget)
        self.duplicate_summary_label = QLabel(); self.duplicate_summary_label.setWordWrap(True); self.duplicate_summary_label.hide()
        self.last_import_summary_label = QLabel("Última importación: todavía no hay importaciones."); self.last_import_summary_label.setObjectName("importHint")
        layout.addWidget(self.duplicate_summary_label); layout.addWidget(self.last_import_summary_label); layout.addStretch(1)
        self.load_automation_preferences()

    def _connect_adapter(self):
        self.adapter.progress_changed.connect(self.update_progress)
        self.adapter.event_received.connect(self.update_current_file_progress)
        self.adapter.job_status_changed.connect(self.update_job_status)
        self.adapter.file_processed.connect(self.record_processed_file)
        self.adapter.running_changed.connect(self._set_running)
        self.adapter.import_completed.connect(self._refresh_last_import_summary)

    def select_folder(self):
        selected = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de música", self.folder_input.text())
        if selected: self.folder_input.setText(selected)

    def load_automation_preferences(self):
        if self.settings_service is None: return
        library = self.settings_service.get().library
        self.folder_input.setText(library.default_music_path or "")
        self._show_default_folders(library.music_paths, library.default_music_path)

    def _show_default_folders(self, paths, default_path):
        self.default_folder_combo.blockSignals(True); self.default_folder_combo.clear()
        if not paths: self.default_folder_combo.addItem("Sin carpeta predeterminada", None)
        for path in paths: self.default_folder_combo.addItem(f"Predeterminada: {path}" if path == default_path else path, path)
        index = self.default_folder_combo.findData(default_path)
        self.default_folder_combo.setCurrentIndex(index if index >= 0 else 0)
        self.default_folder_combo.blockSignals(False)

    def use_selected_default_folder(self, _index=None):
        path = self.default_folder_combo.currentData(Qt.UserRole)
        if path: self.folder_input.setText(path)

    def save_default_folder(self):
        if self.settings_service is None: return
        selected = self.folder_input.text().strip()
        if not selected:
            self.status_label.setText("Seleccioná una carpeta antes de definirla como predeterminada."); return
        current = self.settings_service.get().library; paths = list(current.music_paths)
        if all(item.casefold() != selected.casefold() for item in paths): paths.append(selected)
        self.settings_service.update({"library": {"music_paths": paths, "default_music_path": selected, "scan_on_start": True, "auto_external_metadata_enabled": True}, "analysis": {"auto_analysis_enabled": True}, "backup": {"auto_backup_enabled": True}})
        updated = self.settings_service.get().library; self._show_default_folders(updated.music_paths, updated.default_music_path)
        self.status_label.setText("Carpeta predeterminada actualizada")

    def start_import(self):
        try: self.adapter.start(self.folder_input.text())
        except ValueError as error: self.status_label.setText(str(error)); return
        self._duplicate_count = 0; self.duplicate_summary_label.hide()
        self.current_file_label.setText("Archivo actual: preparando importación…")
        self.current_file_progress_label.setText("Archivo actual: esperando"); self.current_file_progress_bar.setValue(0)

    def cancel_import(self): self.adapter.cancel(); self.status_label.setText("Cancelación solicitada")

    def update_progress(self, progress):
        total, processed = progress.get("total_items", 0), progress.get("processed_items", 0)
        self.progress_bar.setRange(0, max(total, 1)); self.progress_bar.setValue(min(processed, max(total, 1)))
        self.progress_label.setText(f"Total de archivos: {processed} / {total}")

    def update_current_file_progress(self, event):
        if event.filepath: self.current_file_label.setText(f"Archivo actual: {Path(event.filepath).name}")
        steps = {"processing_started": (0, "Leyendo metadata nativa"), "metadata_processed": (1, "Guardando en biblioteca"), "track_imported": (2, "Completado"), "skipped": (2, "Sin cambios"), "failed": (2, "Con error")}
        if event.event_type in steps:
            value, label = steps[event.event_type]; self.current_file_progress_bar.setValue(value); self.current_file_progress_label.setText(f"Archivo actual: {label}")

    def update_job_status(self, status):
        labels = {"completed": "Completado", "cancelled": "Cancelado", "failed": "Error", "running": "Procesando", "pending": "Analizando"}
        self.status_label.setText(f"Estado: {labels.get(status, status)}")

    def record_processed_file(self, _filepath, event_type):
        if event_type != "skipped": return
        self._duplicate_count += 1; suffix = "archivo repetido" if self._duplicate_count == 1 else "archivos repetidos"
        self.duplicate_summary_label.setText(f"Se omitieron {self._duplicate_count} {suffix}."); self.duplicate_summary_label.show()

    def _refresh_last_import_summary(self):
        jobs = self.adapter.facade.list_jobs(limit=1)
        if not jobs: self.last_import_summary_label.setText("Última importación: todavía no hay importaciones."); return
        job = jobs[0]; date = job.finished_at or job.created_at
        date_text = date.strftime("%d/%m/%Y") if date is not None else "sin fecha"
        self.last_import_summary_label.setText(f"Última importación: {date_text} · {job.processed_items} archivos")

    def _set_running(self, running):
        self.start_button.setEnabled(not running); self.cancel_button.setEnabled(running); self.browse_button.setEnabled(not running); self.folder_input.setReadOnly(running)
        self.default_folder_combo.setEnabled(not running); self.set_default_folder_button.setEnabled(not running)

    def closeEvent(self, event):
        if self.adapter.is_running: self.adapter.cancel()
        self.adapter.close(); super().closeEvent(event)
