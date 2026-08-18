"""Confirmed metadata edit surface; no audio-file mutation."""
from datetime import datetime, timezone

from PySide6.QtCore import QObject, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from urllib.parse import urlencode
from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QTextEdit, QVBoxLayout, QWidget

from app.services.metadata_candidate_proposal import MetadataProposalDTO
from app.services.music_classification_persistence_service import ClassificationSelectionDTO
from app.services.track_metadata_editor import BulkMetadataEditQueryDTO, TrackMetadataPatchDTO, TrackMetadataDTO


class _MetadataProposalWorker(QObject):
    result = Signal(object)
    error = Signal(str)
    finished = Signal()

    def __init__(self, service, track_metadata):
        super().__init__()
        self._service = service
        self._track_metadata = track_metadata

    @Slot()
    def run(self):
        try:
            if QThread.currentThread().isInterruptionRequested():
                return
            proposal = self._service.create_metadata_proposal(self._track_metadata)
            if not QThread.currentThread().isInterruptionRequested():
                self.result.emit(proposal)
        except Exception as error:  # pragma: no cover - defensive UI path
            if not QThread.currentThread().isInterruptionRequested():
                self.error.emit(str(error))
        finally:
            self.finished.emit()


class TrackMetadataPanel(QWidget):
    """UI-only presentation of the existing preview/confirmation edit flow and external metadata proposals."""

    external_proposal_ready = Signal(object)
    external_proposal_failed = Signal(str)
    metadata_changed = Signal()

    def __init__(self, facade, parent=None, proposal_service=None, persistence_service=None, native_metadata_service=None):
        super().__init__(parent)
        self.facade, self.preview_result, self.proposal = facade, None, None
        self._proposal_service = proposal_service
        self._persistence_service = persistence_service
        self._native_metadata_service = native_metadata_service
        self._proposal_thread = None
        self._proposal_worker = None
        self._proposal_cancelled = False
        self._native_metadata_used = False
        self._manual_metadata_baseline = {}
        self._build_ui()

    def _build_ui(self):
        self.setObjectName("metadataPanel")
        self.setStyleSheet("QFrame#metadataSection { background:#10182A; border:1px solid #253550; border-radius:9px; } QLabel#metadataTitle { color:#F1F5FF; font-size:19px; font-weight:700; } QLabel#metadataStep { color:#AFA9FF; font-weight:700; } QLabel#metadataHint { color:#8FA1BD; } QPushButton#metadataPrimary { background:#6259E8; border:1px solid #817AFF; color:white; font-weight:600; }")
        layout = QVBoxLayout(self); layout.setContentsMargins(16, 16, 16, 16); layout.setSpacing(12)
        title = QLabel("Editar metadata"); title.setObjectName("metadataTitle"); layout.addWidget(title)
        hint = QLabel("Seleccioná una o varias pistas, revisá los cambios y confirmá sólo después de la vista previa."); hint.setObjectName("metadataHint"); hint.setWordWrap(True); layout.addWidget(hint)

        selection = self._section("1 · Selección de pistas")
        self.ids = QLineEdit(); self.ids.setPlaceholderText("IDs separados por coma, por ejemplo: 12, 18, 42"); self.ids.setAccessibleName("IDs de pistas")
        selection.layout().addWidget(self.ids); self.selection_summary = QLabel("Sin pistas seleccionadas"); self.selection_summary.setObjectName("metadataHint"); selection.layout().addWidget(self.selection_summary); self.selected_track_details = QLabel("Elegí una pista en Biblioteca para revisar su metadata actual."); self.selected_track_details.setObjectName("metadataHint"); self.selected_track_details.setWordWrap(True); selection.layout().addWidget(self.selected_track_details); layout.addWidget(selection)

        fields = self._section("2 · Campos actuales y cambios propuestos")
        fields_form = QGridLayout()
        self.title = QLineEdit(); self.title.setPlaceholderText("Título"); self.title.setAccessibleName("Título propuesto")
        self.artist = QLineEdit(); self.artist.setPlaceholderText("Artista"); self.artist.setAccessibleName("Artista propuesto")
        self.album = QLineEdit(); self.album.setPlaceholderText("Álbum"); self.album.setAccessibleName("Álbum propuesto")
        self.label = QLineEdit(); self.label.setPlaceholderText("Sello discográfico"); self.label.setAccessibleName("Sello discográfico propuesto")
        self.genre = QLineEdit(); self.genre.setPlaceholderText("Género"); self.genre.setAccessibleName("Género propuesto")
        self.bpm = QDoubleSpinBox(); self.bpm.setRange(0, 400); self.bpm.setDecimals(1); self.bpm.setSpecialValueText("Sin BPM"); self.bpm.setAccessibleName("BPM propuesto")
        self.key = QLineEdit(); self.key.setPlaceholderText("Clave"); self.key.setAccessibleName("Clave propuesta")
        self.energy = QSpinBox(); self.energy.setRange(0, 100); self.energy.setAccessibleName("Energía propuesta")
        for column, (label, field) in enumerate((("Título", self.title), ("Artista", self.artist), ("Álbum", self.album), ("Sello", self.label), ("Género", self.genre), ("BPM", self.bpm), ("Clave", self.key), ("Energía", self.energy))):
            row = column // 2; position = (column % 2) * 2; fields_form.addWidget(QLabel(label), row, position); fields_form.addWidget(field, row, position + 1)
        fields.layout().addLayout(fields_form)
        self.mixed_fields_label = QLabel("Para varias pistas, la vista previa indica valores mixtos, sin cambios y validaciones."); self.mixed_fields_label.setObjectName("metadataHint"); self.mixed_fields_label.setWordWrap(True); fields.layout().addWidget(self.mixed_fields_label); layout.addWidget(fields)

        actions = QHBoxLayout(); self.preview_button = QPushButton("Generar vista previa"); self.preview_button.setObjectName("metadataPrimary"); self.apply_button = QPushButton("Confirmar y aplicar"); self.apply_button.setEnabled(False); actions.addWidget(self.preview_button); actions.addWidget(self.apply_button); actions.addStretch(1); layout.addLayout(actions)
        result = self._section("3–5 · Vista previa, confirmación y resultado")
        self.output = QTextEdit(); self.output.setReadOnly(True); self.output.setPlaceholderText("La vista previa y los errores aparecerán aquí."); self.output.setMinimumHeight(150); result.layout().addWidget(self.output); layout.addWidget(result)

        proposal_section = self._section("6 · Metadata externa")
        proposal_controls = QHBoxLayout(); self.external_button = QPushButton("Buscar metadata externa"); self.external_button.setObjectName("metadataPrimary"); self.external_button.setAccessibleName("Buscar metadata externa"); self.external_button.clicked.connect(self.search_external_metadata); self.beatport_button = QPushButton("Buscar en Beatport"); self.beatport_button.setAccessibleName("Buscar la pista actual en Beatport"); self.beatport_button.setToolTip("Abre Beatport para verificar la metadata de esta pista."); self.beatport_button.clicked.connect(self.open_beatport_search); proposal_controls.addWidget(self.external_button); proposal_controls.addWidget(self.beatport_button); proposal_controls.addStretch(1); proposal_section.layout().addLayout(proposal_controls)
        self.proposal_output = QTextEdit(); self.proposal_output.setReadOnly(True); self.proposal_output.setMinimumHeight(120); self.proposal_output.setPlaceholderText("La propuesta externa aparecerá aquí."); self.proposal_output.setAccessibleName("Resultado de metadata externa"); proposal_section.layout().addWidget(self.proposal_output)

        fields_box = QHBoxLayout(); self.genre_checkbox = QCheckBox("Género"); self.genre_checkbox.setAccessibleName("Aplicar género"); self.genre_checkbox.setChecked(True); self.secondary_genres_checkbox = QCheckBox("Géneros secundarios"); self.secondary_genres_checkbox.setAccessibleName("Aplicar géneros secundarios"); self.secondary_genres_checkbox.setChecked(True); self.styles_checkbox = QCheckBox("Estilos"); self.styles_checkbox.setAccessibleName("Aplicar estilos"); self.styles_checkbox.setChecked(True); self.label_checkbox = QCheckBox("Sello"); self.label_checkbox.setAccessibleName("Aplicar sello"); self.label_checkbox.setChecked(True); fields_box.addWidget(self.genre_checkbox); fields_box.addWidget(self.secondary_genres_checkbox); fields_box.addWidget(self.styles_checkbox); fields_box.addWidget(self.label_checkbox); proposal_section.layout().addLayout(fields_box)

        actions_box = QGridLayout(); self.apply_external_button = QPushButton("Aplicar seleccionados"); self.apply_external_button.setAccessibleName("Aplicar campos de metadata seleccionados"); self.apply_external_button.setEnabled(False); self.cancel_external_button = QPushButton("Cancelar"); self.cancel_external_button.setAccessibleName("Cancelar búsqueda de metadata externa"); self.undo_external_button = QPushButton("Deshacer último cambio"); self.undo_external_button.setAccessibleName("Deshacer último cambio de metadata externa"); self.undo_external_button.setEnabled(False); actions_box.addWidget(self.apply_external_button, 0, 0); actions_box.addWidget(self.cancel_external_button, 0, 1); actions_box.addWidget(self.undo_external_button, 1, 0, 1, 2); proposal_section.layout().addLayout(actions_box)
        self.apply_external_button.clicked.connect(self.apply_external_metadata); self.cancel_external_button.clicked.connect(self.cancel_external_metadata); self.undo_external_button.clicked.connect(self.undo_external_metadata)
        self.setTabOrder(self.external_button, self.genre_checkbox)
        self.setTabOrder(self.genre_checkbox, self.secondary_genres_checkbox)
        self.setTabOrder(self.secondary_genres_checkbox, self.styles_checkbox)
        self.setTabOrder(self.styles_checkbox, self.label_checkbox)
        self.setTabOrder(self.label_checkbox, self.apply_external_button)
        self.setTabOrder(self.apply_external_button, self.cancel_external_button)
        self.setTabOrder(self.cancel_external_button, self.undo_external_button)

        self.preview_button.clicked.connect(self.preview); self.apply_button.clicked.connect(self.apply); self.ids.textChanged.connect(self._update_selection_summary)
        layout.addWidget(proposal_section)

    def _section(self, heading):
        frame = QFrame(); frame.setObjectName("metadataSection"); box = QVBoxLayout(frame); box.setContentsMargins(12, 10, 12, 10); box.setSpacing(6)
        label = QLabel(heading); label.setObjectName("metadataStep"); box.addWidget(label); return frame

    def _update_selection_summary(self, text):
        values = [value.strip() for value in text.split(",") if value.strip()]
        self.selection_summary.setText("Sin pistas seleccionadas" if not values else ("Edición individual" if len(values) == 1 else f"Edición múltiple: {len(values)} pistas"))

    @Slot(object)
    def set_selected_track(self, track):
        """Prefill the review workflow from the row chosen in Biblioteca."""
        track_id = getattr(track, "id", None)
        if track_id is None:
            return
        self.ids.setText(str(track_id))
        self.title.setText(getattr(track, "title", "") or "")
        self.artist.setText(getattr(track, "artist", "") or "")
        self.album.setText(getattr(track, "album", "") or "")
        self.label.setText(getattr(track, "label", "") or "")
        self.genre.setText(getattr(track, "genre", "") or "")
        self.bpm.setValue(float(getattr(track, "bpm", 0) or 0))
        self.key.setText(getattr(track, "key", "") or "")
        self.energy.setValue(int(getattr(track, "energy", 0) or 0))
        self._manual_metadata_baseline = {
            "title": self.title.text(), "artist": self.artist.text(), "album": self.album.text(), "label": self.label.text(),
            "genre": self.genre.text(), "bpm": self.bpm.value(), "key": self.key.text(), "energy": self.energy.value(),
        }
        self.selected_track_details.setText(
            " · ".join(
                (
                    f"Artista: {getattr(track, 'artist', None) or 'N/A'}",
                    f"Título: {getattr(track, 'title', None) or 'N/A'}",
                    f"Álbum: {getattr(track, 'album', None) or 'N/A'}",
                    f"Género: {getattr(track, 'genre', None) or 'N/A'}",
                    f"Sello: {getattr(track, 'label', None) or 'N/A'}",
                    f"BPM: {getattr(track, 'bpm', None) or 'N/A'}",
                    f"Clave: {getattr(track, 'key', None) or 'N/A'}",
                )
            )
        )
        self._clear_external_proposal_state("Listo para buscar metadata externa.")

    def search_external_metadata(self):
        self._clear_external_proposal_state()
        try:
            track_id = self._track_id_from_selection()
            track_metadata = self._build_track_metadata(track_id)
            track_metadata = self._enrich_with_embedded_metadata(track_id, track_metadata)
            service = self._proposal_service or self._default_proposal_service()
            message = "Metadata nativa leída; buscando coincidencias externas…" if self._native_metadata_used else "Buscando metadata externa…"
            self.proposal_output.setPlainText(message)
            self._start_proposal_worker(service, track_metadata)
        except Exception as error:
            self.proposal = None
            self._render_external_error(str(error))

    def beatport_search_url(self):
        query = " ".join(value.strip() for value in (self.artist.text(), self.title.text()) if value.strip())
        return QUrl(f"https://www.beatport.com/search?{urlencode({'q': query})}") if query else QUrl()

    def open_beatport_search(self):
        url = self.beatport_search_url()
        if not url.isValid() or not url.query():
            self.proposal_output.setPlainText("Seleccioná una pista o completá artista y título para buscar en Beatport.")
            return
        QDesktopServices.openUrl(url)

    def apply_external_metadata(self):
        if self.proposal is None:
            return
        if not self._proposal_is_valid(self.proposal):
            self._set_external_apply_state(False)
            return
        selection = ClassificationSelectionDTO(
            genre=self.genre_checkbox.isChecked(),
            secondary_genres=self.secondary_genres_checkbox.isChecked(),
            styles=self.styles_checkbox.isChecked(),
            label=self.label_checkbox.isChecked(),
        )
        persistence = self._persistence_service or self._default_persistence_service()
        result = persistence.apply_confirmed_proposal(self.proposal, confirmation=True, selection=selection)
        self.proposal_output.setPlainText(self._format_persistence_result(result))
        applied_values = result.get("values", {}) if isinstance(result, dict) else {}
        if "label" in applied_values:
            self.label.setText(applied_values["label"] or "")
            self._manual_metadata_baseline["label"] = self.label.text()
        self._set_external_apply_state(False)
        self.undo_external_button.setEnabled(True)
        self.metadata_changed.emit()

    def cancel_external_metadata(self):
        self._proposal_cancelled = True
        if self._proposal_thread is not None:
            self._proposal_thread.requestInterruption()
        self.proposal = None
        self.proposal_output.setPlainText("Operación cancelada.")
        self._set_external_apply_state(False)

    def undo_external_metadata(self):
        try:
            track_id = self._track_id_from_selection()
            persistence = self._persistence_service or self._default_persistence_service()
            if persistence.undo_last_classification(track_id):
                self.proposal_output.setPlainText("Último cambio deshecho.")
        except Exception as error:
            self.proposal_output.setPlainText(str(error))

    def _start_proposal_worker(self, service, track_metadata):
        if self._proposal_worker is not None:
            return

        self._proposal_cancelled = False
        thread = QThread(self)
        worker = _MetadataProposalWorker(service, track_metadata)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.result.connect(self._handle_proposal_result)
        worker.error.connect(self._handle_proposal_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._cleanup_proposal_worker)
        self._proposal_thread = thread
        self._proposal_worker = worker
        self.external_button.setEnabled(False)
        thread.start()

    @Slot(object)
    def _handle_proposal_result(self, proposal):
        if self._proposal_cancelled:
            return
        self.proposal = proposal
        self.external_proposal_ready.emit(proposal)
        self._render_external_proposal(proposal)

    @Slot(str)
    def _handle_proposal_error(self, error):
        if self._proposal_cancelled:
            return
        self.proposal = None
        self.external_proposal_failed.emit(error)
        self._render_external_error(error)

    @Slot()
    def _cleanup_proposal_worker(self):
        thread = self._proposal_thread
        if thread is None:
            return
        self._proposal_worker = None
        self._proposal_thread = None
        self.external_button.setEnabled(True)
        thread.deleteLater()

    def closeEvent(self, event):
        self._proposal_cancelled = True
        if self._proposal_thread is not None:
            self._proposal_thread.requestInterruption()
        super().closeEvent(event)

    def _render_external_proposal(self, proposal):
        if proposal is None:
            self.proposal_output.setPlainText("No hay propuesta disponible.")
            self._set_external_apply_state(False)
            return
        lines = []
        if self._proposal_has_content(proposal):
            lines.append(f"Género actual: {proposal.current_metadata.genre or 'N/A'}")
            lines.append(f"Género propuesto: {proposal.proposed_primary_genre_label or proposal.proposed_primary_genre_id or 'N/A'}")
            lines.append(f"Confianza: {proposal.proposed_primary_confidence:.2f}")
            lines.append(f"Secundarios: {', '.join(item[0] for item in proposal.proposed_secondary_genres) if proposal.proposed_secondary_genres else 'N/A'}")
            lines.append(f"Estilos: {', '.join(item[0] for item in proposal.proposed_styles) if proposal.proposed_styles else 'N/A'}")
            lines.append(f"Sello propuesto: {proposal.proposed_label or 'N/A'}")
            if proposal.conflicts:
                lines.append("Conflicts: " + ", ".join(proposal.conflicts))
            if proposal.ambiguous_terms:
                lines.append("Ambiguous: " + ", ".join(term for term, _ in proposal.ambiguous_terms))
            if proposal.unknown_terms:
                lines.append("Unknown: " + ", ".join(proposal.unknown_terms))
            if proposal.warnings:
                lines.append("Warnings: " + "; ".join(proposal.warnings))
            self._set_external_apply_state(self._proposal_has_applicable_fields(proposal))
        else:
            lines.append("Sin coincidencias")
            if proposal.warnings:
                lines.append("Warnings: " + "; ".join(proposal.warnings))
            self._set_external_apply_state(False)
        self.proposal_output.setPlainText("\n".join(lines))

    def _render_external_error(self, error):
        self.proposal_output.setPlainText(f"Error: {error}")
        self._set_external_apply_state(False)

    def _clear_external_proposal_state(self, message="Buscando metadata externa…"):
        self.proposal = None
        self.proposal_output.setPlainText(message)
        self._set_external_apply_state(False)

    def _set_external_apply_state(self, enabled):
        self.apply_external_button.setEnabled(bool(enabled))

    def _proposal_has_content(self, proposal):
        if not isinstance(proposal, MetadataProposalDTO):
            return False
        return bool(
            proposal.proposed_primary_genre_id
            or proposal.proposed_primary_genre_label
            or proposal.proposed_secondary_genres
            or proposal.proposed_styles
            or proposal.proposed_label
            or proposal.conflicts
            or proposal.ambiguous_terms
            or proposal.unknown_terms
            or proposal.warnings
        )

    def _proposal_has_applicable_fields(self, proposal):
        if not self._proposal_has_content(proposal):
            return False
        if self.genre_checkbox.isChecked() and (proposal.proposed_primary_genre_id or proposal.proposed_primary_genre_label):
            return True
        if self.secondary_genres_checkbox.isChecked() and proposal.proposed_secondary_genres:
            return True
        if self.styles_checkbox.isChecked() and proposal.proposed_styles:
            return True
        if self.label_checkbox.isChecked() and proposal.proposed_label:
            return True
        return False

    def _proposal_is_valid(self, proposal):
        if not isinstance(proposal, MetadataProposalDTO):
            return False
        return self._proposal_has_content(proposal)

    def _build_track_metadata(self, track_id):
        track = self._track_from_library(track_id)
        if track is None:
            raise ValueError("No se encuentra la pista seleccionada")
        return TrackMetadataDTO(
            track_id=track_id,
            title=getattr(track, "title", "") or "",
            artist=getattr(track, "artist", "") or "",
            album=getattr(track, "album", None),
            genre=getattr(track, "genre", None),
            rating=getattr(track, "rating", 0) or 0,
            bpm=getattr(track, "bpm", None),
            key=getattr(track, "key", None),
            energy=getattr(track, "energy", 0) or 0,
        )

    def _enrich_with_embedded_metadata(self, track_id, current_metadata):
        self._native_metadata_used = False
        track = self._track_from_library(track_id)
        filepath = getattr(track, "filepath", None)
        if not filepath:
            return current_metadata
        from app.services.metadata_service import MetadataReadError, MetadataService
        service = self._native_metadata_service or MetadataService()
        try:
            embedded = service.read_embedded(filepath)
        except MetadataReadError:
            return current_metadata
        values = {
            "title": embedded.title or current_metadata.title,
            "artist": embedded.artist or current_metadata.artist,
            "album": embedded.album or current_metadata.album,
            "genre": embedded.genre or current_metadata.genre,
            "bpm": embedded.bpm or current_metadata.bpm,
            "key": embedded.key or current_metadata.key,
        }
        self._native_metadata_used = any((embedded.title, embedded.artist, embedded.album, embedded.genre, embedded.bpm, embedded.key))
        self._fill_empty_native_fields(values)
        return TrackMetadataDTO(track_id, values["title"], values["artist"], values["album"], values["genre"], current_metadata.rating, values["bpm"], values["key"], current_metadata.energy)

    def _fill_empty_native_fields(self, values):
        for field in ("title", "artist", "album", "genre", "key"):
            control = getattr(self, field)
            if not control.text().strip() and values[field]:
                control.setText(str(values[field]))
        if self.bpm.value() == 0 and values["bpm"]:
            self.bpm.setValue(float(values["bpm"]))

    def _track_from_library(self, track_id):
        if self.facade is None:
            return None
        library_service = getattr(self.facade, "library_service", None)
        if library_service is None:
            return None
        repository = getattr(library_service, "repository", None)
        if repository is None:
            return None
        return repository.get_by_id(track_id)

    def _track_id_from_selection(self):
        values = [value.strip() for value in self.ids.text().split(",") if value.strip()]
        if not values:
            raise ValueError("Seleccione una pista para metadata externa")
        return int(values[0])

    def _default_proposal_service(self):
        from app.services.metadata_proposal_orchestrator import CombinedMetadataProposalService
        return CombinedMetadataProposalService()

    def _default_persistence_service(self):
        from app.services.music_classification_persistence_service import MusicClassificationPersistenceService
        return MusicClassificationPersistenceService()

    def _format_persistence_result(self, result):
        return "Aplicado" if result.get("applied") else "No se pudo aplicar"

    def preview(self):
        try:
            ids = tuple(int(value.strip()) for value in self.ids.text().split(",") if value.strip())
            values = self._manual_metadata_changes()
            if not values:
                raise ValueError("No hay cambios de metadata para previsualizar")
            query = BulkMetadataEditQueryDTO(ids, TrackMetadataPatchDTO.from_mapping(values))
            self.preview_result = self.facade.preview(query); self.proposal = self.facade.editor.propose(self.preview_result)
            self.output.setPlainText(self.facade.export_preview(self.preview_result)); self.apply_button.setEnabled(True)
        except Exception as error:
            self.output.setPlainText(str(error)); self.apply_button.setEnabled(False)

    def _manual_metadata_changes(self):
        current = {
            "title": self.title.text(), "artist": self.artist.text(), "album": self.album.text() or None, "label": self.label.text() or None,
            "genre": self.genre.text() or None, "bpm": self.bpm.value() or None,
            "key": self.key.text() or None, "energy": self.energy.value(),
        }
        if not self._manual_metadata_baseline:
            return {"title": current["title"]}
        return {
            field: value
            for field, value in current.items()
            if value != (self._manual_metadata_baseline[field] or None)
        }

    def apply(self):
        result = self.facade.editor.apply(self.preview_result, self.proposal, ConfirmationRequestDTO(self.proposal.action_id, datetime.now(timezone.utc)))
        self.output.setPlainText(self.facade.export_result(result)); self.apply_button.setEnabled(False)
        if getattr(result, "success", True):
            self.metadata_changed.emit()


from app.services.confirmation_manager import ConfirmationRequestDTO
