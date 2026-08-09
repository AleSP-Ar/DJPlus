"""Deterministic local recommendation panel for compatible tracks."""

from types import SimpleNamespace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.services.recommendation_facade import RecommendationFacade, RecommendationFacadeQueryDTO


class LocalIntelligencePanel(QWidget):
    """Display compatible track recommendations using only local services."""

    def __init__(self, recommendation_facade, library_view=None, settings_service=None, parent=None):
        super().__init__(parent)
        if not isinstance(recommendation_facade, RecommendationFacade):
            raise TypeError("LocalIntelligencePanel requiere RecommendationFacade.")
        self._recommendation_facade = recommendation_facade
        self._library_view = library_view
        self._settings_service = settings_service
        self._reference_track = None
        self.setObjectName("intelligencePanel")

        self._build_ui()
        if library_view is not None:
            self._connect_to_library_view(library_view)
        self._update_reference_display()

    def _build_ui(self):
        self.setStyleSheet(
            "QFrame#intelligenceSection { background:#1f2937; border:1px solid #374151; border-radius:8px; } "
            "QLabel#intelligenceTitle { font-size:18px; font-weight:600; } "
            "QLabel#intelligenceSubtitle { color:#9ca3af; } "
            "QPushButton#intelligencePrimary { background:#2563eb; color:white; font-weight:600; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Inteligencia musical local")
        title.setObjectName("intelligenceTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Seleccioná una pista en Biblioteca y buscá compatibles sin usar proveedores externos."
        )
        subtitle.setObjectName("intelligenceSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.reference_frame = QFrame()
        self.reference_frame.setObjectName("intelligenceSection")
        reference_layout = QVBoxLayout(self.reference_frame)
        reference_layout.setContentsMargins(12, 12, 12, 12)
        reference_layout.setSpacing(6)

        self.reference_title = QLabel("Referencia: ninguna pista seleccionada")
        self.reference_title.setWordWrap(True)
        reference_layout.addWidget(self.reference_title)

        self.reference_artist = QLabel("")
        self.reference_artist.setWordWrap(True)
        reference_layout.addWidget(self.reference_artist)

        self.reference_details = QLabel("")
        self.reference_details.setWordWrap(True)
        reference_layout.addWidget(self.reference_details)

        layout.addWidget(self.reference_frame)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addStretch(1)
        actions.addWidget(QLabel("Score mínimo"))
        self.min_score = QSpinBox()
        self.min_score.setRange(1, 100)
        self.min_score.setAccessibleName("Score mínimo de recomendaciones")
        self.min_score.setValue(self._load_min_score())
        self.min_score.valueChanged.connect(self._save_min_score)
        actions.addWidget(self.min_score)
        self.search_button = QPushButton("Buscar compatibles")
        self.search_button.setObjectName("intelligencePrimary")
        self.search_button.clicked.connect(self._search_recommendations)
        actions.addWidget(self.search_button)
        layout.addLayout(actions)

        self.status_label = QLabel("Listo")
        layout.addWidget(self.status_label)

        self.result_view = QTextEdit()
        self.result_view.setReadOnly(True)
        self.result_view.setPlaceholderText("Los resultados aparecerán acá después de buscar compatibles.")
        layout.addWidget(self.result_view, 1)

    def _connect_to_library_view(self, library_view):
        table = getattr(library_view, "table", None)
        if table is None:
            return
        selection_model = getattr(table, "selectionModel", None)
        if selection_model is None:
            return
        selection_model().selectionChanged.connect(self._on_library_selection_changed)

    def _on_library_selection_changed(self, selected, deselected):
        self._sync_reference_from_library()

    def _sync_reference_from_library(self):
        if self._library_view is None:
            return
        index = self._library_view.table.currentIndex()
        track = self._library_view.model.track_at(index.row()) if index.isValid() else None
        self.set_reference_track(track)

    def set_reference_track(self, track):
        self._reference_track = track
        self._update_reference_display()

    def _update_reference_display(self):
        if self._reference_track is None:
            self.reference_title.setText("Referencia: ninguna pista seleccionada")
            self.reference_artist.setText("Seleccioná una pista en Biblioteca para comenzar.")
            self.reference_details.setText("")
            self.search_button.setEnabled(False)
            self.result_view.clear()
            return

        title = self._reference_track.title or "Sin título"
        artist = self._reference_track.artist or "Desconocido"
        self.reference_title.setText(f"{artist} — {title}")
        self.reference_artist.setText(
            f"Álbum: {self._reference_track.album or 'N/A'}"
        )
        self.reference_details.setText(
            f"BPM: {self._reference_track.bpm or '—'} · Key: {self._reference_track.key or '—'} · Energía: {self._reference_track.energy or '—'}"
        )
        self.search_button.setEnabled(True)

    def _search_recommendations(self):
        if self._reference_track is None:
            self.status_label.setText("Seleccione una pista antes de buscar.")
            return
        self.status_label.setText("Buscando compatibles…")
        try:
            page = self._recommendation_facade.recommend(
                RecommendationFacadeQueryDTO(current_track=self._reference_track, min_score=self.min_score.value())
            )
            self._show_recommendation_page(page)
            self.status_label.setText("Resultados actualizados")
        except Exception as error:
            self.result_view.setPlainText(str(error))
            self.status_label.setText("Error")

    def _load_min_score(self):
        if self._settings_service is not None:
            try:
                return self._settings_service.get().library.recommendation_min_score
            except Exception:
                pass
        return 45

    def _save_min_score(self, value):
        if self._settings_service is None:
            return
        try:
            self._settings_service.update({"library": {"recommendation_min_score": int(value)}})
        except Exception:
            self.status_label.setText("No se pudo guardar el score mínimo")

    def _show_recommendation_page(self, page):
        lines = [page.explanation, ""]
        if not page.recommendations:
            lines.append("No se encontraron compatibles para la pista seleccionada.")
        for item in page.recommendations:
            candidate = self._lookup_candidate(item.candidate_track_id)
            lines.append(
                f"{item.rank}. {candidate.artist if candidate else item.candidate_track_id} — "
                f"{candidate.title if candidate else 'Track'} | score {item.score} | confianza {item.confidence:.2f}"
            )
            if candidate is not None:
                lines.append(
                    f"   BPM: {candidate.bpm or '—'} · Key: {candidate.key or '—'} · Energía: {candidate.energy or '—'}"
                )
            lines.extend(
                f"   • {reason.explanation}" for reason in item.reasons
            )
            lines.append("")
        self.result_view.setPlainText("\n".join(lines).strip())

    def _lookup_candidate(self, track_id):
        if self._library_view is None or not hasattr(self._library_view, "library_service"):
            return None
        repository = getattr(self._library_view.library_service, "repository", None)
        if repository is None or not callable(getattr(repository, "get_by_id", None)):
            return None
        return repository.get_by_id(track_id)
