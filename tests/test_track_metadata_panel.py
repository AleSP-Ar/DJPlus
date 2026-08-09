import unittest
from types import SimpleNamespace
from PySide6.QtCore import QEventLoop, QThread, QTimer, Qt
from PySide6.QtWidgets import QScrollArea
from qt_test_helpers import ensure_qapplication
from app.services.metadata_candidate_proposal import MetadataProposalDTO
from app.services.music_classification_persistence_service import ClassificationSelectionDTO
from app.services.track_metadata_editor import TrackMetadataDTO
from app.ui.track_metadata_panel import TrackMetadataPanel
from app.ui.main_window import MainWindow, MainWindowDependencies
from app.ui.library_view import LibraryView


class _Editor:
    def propose(self, r):
        return SimpleNamespace(action_id="a")

    def apply(self, r, p, q):
        return SimpleNamespace(success=True, backups=((1, ()),))


class _Facade:
    def __init__(self):
        self.editor = _Editor()

    def preview(self, q):
        return SimpleNamespace(preview="1:title=new", backups=())

    def export_preview(self, r):
        return r.preview

    def export_result(self, r):
        return "applied"


class _TrackRepository:
    def get_by_id(self, track_id):
        return SimpleNamespace(id=track_id, title="Song", artist="Artist", album="Album", genre="house", rating=0, bpm=120, key="8A", energy=80)


class _LibraryService:
    def __init__(self):
        self.repository = _TrackRepository()


class _ProxyFacade(_Facade):
    def __init__(self):
        super().__init__()
        self.library_service = _LibraryService()


class _ProposalService:
    def __init__(self, proposal):
        self.proposal = proposal
        self.calls = []
        self.call_thread = None

    def create_metadata_proposal(self, track_metadata):
        self.call_thread = QThread.currentThread()
        self.calls.append(track_metadata)
        return self.proposal


class _FailingProposalService:
    def create_metadata_proposal(self, track_metadata):
        raise RuntimeError("external service unavailable")


class _PersistenceService:
    def __init__(self):
        self.calls = []
        self.undo_calls = []

    def apply_confirmed_proposal(self, proposal, confirmation, selection=None):
        self.calls.append((proposal, confirmation, selection))
        return {"applied": True, "values": {"genre": "progressive_house"}}

    def undo_last_classification(self, track_id):
        self.undo_calls.append(track_id)
        return True


class _UiLibraryService:
    def __init__(self, track):
        self.track = track
        self.refresh_calls = 0

    def load_library(self):
        return [self.track], False

    def load_more(self):
        return [], False

    def refresh(self):
        self.refresh_calls += 1
        return [self.track], False

    def count_results(self):
        return 1

    def close(self):
        pass


class _UiHistoryService:
    def record_track_selected(self, track_id):
        pass

    def close(self):
        pass


class _Preview:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class TrackMetadataPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(c):
        c.app = ensure_qapplication()

    def _wait_for_external_proposal(self, panel):
        loop = QEventLoop()
        timed_out = []
        timer = QTimer()
        timer.setSingleShot(True)
        panel.external_proposal_ready.connect(loop.quit)
        panel.external_proposal_failed.connect(loop.quit)
        timer.timeout.connect(lambda: (timed_out.append(True), loop.quit()))
        timer.start(1000)
        loop.exec()
        timer.stop()
        self.assertFalse(timed_out, "Timed out waiting for the external metadata proposal")

    def _wait_for_proposal_worker_to_finish(self, panel):
        loop = QEventLoop()
        timed_out = []
        timer = QTimer()
        timer.setSingleShot(True)
        poller = QTimer()
        poller.timeout.connect(lambda: loop.quit() if panel._proposal_thread is None else None)
        timer.timeout.connect(lambda: (timed_out.append(True), loop.quit()))
        poller.start(10)
        timer.start(1000)
        loop.exec()
        poller.stop()
        timer.stop()
        self.assertFalse(timed_out, "Timed out waiting for the metadata worker to finish")

    def test_headless_preview_confirmation_apply_flow(self):
        p = TrackMetadataPanel(_Facade())
        p.ids.setText("1")
        p.title.setText("New")
        p.preview()
        self.assertTrue(p.apply_button.isEnabled())
        p.apply()
        self.assertEqual(p.output.toPlainText(), "applied")
        p.close()

    def test_external_metadata_controls_have_accessible_names(self):
        panel = TrackMetadataPanel(_ProxyFacade())

        self.assertEqual(panel.external_button.accessibleName(), "Buscar metadata externa")
        self.assertEqual(panel.proposal_output.accessibleName(), "Resultado de metadata externa")
        self.assertEqual(panel.genre_checkbox.accessibleName(), "Aplicar género")
        self.assertEqual(panel.secondary_genres_checkbox.accessibleName(), "Aplicar géneros secundarios")
        self.assertEqual(panel.styles_checkbox.accessibleName(), "Aplicar estilos")
        self.assertEqual(panel.apply_external_button.accessibleName(), "Aplicar campos de metadata seleccionados")
        self.assertEqual(panel.cancel_external_button.accessibleName(), "Cancelar búsqueda de metadata externa")
        self.assertEqual(panel.undo_external_button.accessibleName(), "Deshacer último cambio de metadata externa")
        panel.close()

    def test_selected_library_track_prefills_the_metadata_review(self):
        panel = TrackMetadataPanel(_ProxyFacade())
        track = SimpleNamespace(
            id=7,
            title="Selected Song",
            artist="Selected Artist",
            album="Selected Album",
            genre="house",
            bpm=126,
            key="9A",
        )

        panel.set_selected_track(track)

        self.assertEqual(panel.ids.text(), "7")
        self.assertEqual(panel.title.text(), "Selected Song")
        self.assertEqual(panel.artist.text(), "Selected Artist")
        self.assertEqual(panel.album.text(), "Selected Album")
        self.assertEqual(panel.genre.text(), "house")
        self.assertEqual(panel.bpm.value(), 126)
        self.assertEqual(panel.key.text(), "9A")
        self.assertIn("Selected Artist", panel.selected_track_details.text())
        self.assertIn("Selected Album", panel.selected_track_details.text())
        self.assertIn("126", panel.selected_track_details.text())
        self.assertEqual(panel.proposal_output.toPlainText(), "Listo para buscar metadata externa.")
        panel.close()

    def test_manual_metadata_preview_includes_only_changed_fields(self):
        panel = TrackMetadataPanel(_ProxyFacade())
        panel.set_selected_track(SimpleNamespace(
            id=7, title="Song", artist="Artist", album="Album", label=None, genre="house", bpm=126, key="9A", energy=80,
        ))
        panel.album.setText("Updated Album")
        panel.energy.setValue(90)

        self.assertEqual(
            panel._manual_metadata_changes(),
            {"album": "Updated Album", "energy": 90},
        )
        panel.close()

    def test_main_window_sends_the_library_selection_to_metadata(self):
        track = SimpleNamespace(
            id=7, title="Selected Song", artist="Selected Artist", album="Selected Album",
            genre="house", bpm=126, key="9A", rating=0, energy=80, duration=180, filepath="song.mp3",
        )
        library = LibraryView(_UiLibraryService(track), _UiHistoryService())
        panel = TrackMetadataPanel(_ProxyFacade())
        window = MainWindow(
            dependencies=MainWindowDependencies(
                library_view=library,
                track_metadata_panel=panel,
            )
        )
        try:
            library.table.setCurrentIndex(library.model.index(0, 0))
            self.app.processEvents()
            self.assertEqual(panel.ids.text(), "7")
            self.assertIn("Selected Artist", panel.selected_track_details.text())
            panel.metadata_changed.emit()
            self.app.processEvents()
            self.assertEqual(library.library_service.refresh_calls, 1)
        finally:
            window.close()

    def test_loads_external_proposal_and_enables_apply(self):
        proposal = MetadataProposalDTO(
            current_metadata=TrackMetadataDTO(track_id=1, title="Song", artist="Artist", album="Album", genre="house", rating=0, bpm=120, key="8A", energy=80),
            proposed_primary_genre_id="progressive_house",
            proposed_primary_genre_label="Progressive House",
            proposed_primary_confidence=0.92,
            proposed_evidence_count=2,
            candidate_genres=(("progressive_house", "Progressive House", 0.92, 2),),
            proposed_secondary_genres=(("deep_house", "Deep House", 0.8),),
            proposed_styles=(("deep", "Deep", 0.75),),
            conflicts=(),
            ambiguous_terms=(),
            unknown_terms=(),
            warnings=(),
        )
        proposal_service = _ProposalService(proposal)
        panel = TrackMetadataPanel(_ProxyFacade(), proposal_service=proposal_service, persistence_service=_PersistenceService())
        panel.ids.setText("1")
        panel.search_external_metadata()
        self._wait_for_external_proposal(panel)

        self.assertIsNotNone(panel.proposal)
        self.assertIsNot(proposal_service.call_thread, QThread.currentThread())
        self.assertIn("Progressive House", panel.proposal_output.toPlainText())
        self.assertIn("deep", panel.proposal_output.toPlainText())
        self.assertIn("0.92", panel.proposal_output.toPlainText())
        self.assertTrue(panel.apply_external_button.isEnabled())
        panel.close()
        self.app.processEvents()
        if panel._proposal_thread is not None and panel._proposal_thread.isRunning():
            panel._proposal_thread.quit()
            panel._proposal_thread.wait(1000)

    def test_partial_selection_applies_only_selected_fields(self):
        proposal = MetadataProposalDTO(
            current_metadata=TrackMetadataDTO(track_id=1, title="Song", artist="Artist", album="Album", genre="house", rating=0, bpm=120, key="8A", energy=80),
            proposed_primary_genre_id="progressive_house",
            proposed_primary_genre_label="Progressive House",
            proposed_primary_confidence=0.92,
            proposed_evidence_count=2,
            candidate_genres=(("progressive_house", "Progressive House", 0.92, 2),),
            proposed_secondary_genres=(("deep_house", "Deep House", 0.8),),
            proposed_styles=(("deep", "Deep", 0.75),),
            conflicts=(),
            ambiguous_terms=(),
            unknown_terms=(),
            warnings=(),
        )
        persistence = _PersistenceService()
        panel = TrackMetadataPanel(_ProxyFacade(), proposal_service=_ProposalService(proposal), persistence_service=persistence)
        panel.ids.setText("1")
        panel.search_external_metadata()
        self._wait_for_external_proposal(panel)
        panel.genre_checkbox.setChecked(True)
        panel.secondary_genres_checkbox.setChecked(False)
        panel.styles_checkbox.setChecked(True)
        panel.apply_external_metadata()
        selection = persistence.calls[0][2]
        self.assertIsInstance(selection, ClassificationSelectionDTO)
        self.assertTrue(selection.genre)
        self.assertFalse(selection.secondary_genres)
        self.assertTrue(selection.styles)
        self.assertTrue(selection.label)
        panel.close()
        self.app.processEvents()

    def test_cancel_does_not_apply(self):
        proposal = MetadataProposalDTO(
            current_metadata=TrackMetadataDTO(track_id=1, title="Song", artist="Artist", album="Album", genre="house", rating=0, bpm=120, key="8A", energy=80),
            proposed_primary_genre_id="progressive_house",
            proposed_primary_genre_label="Progressive House",
            proposed_primary_confidence=0.92,
            proposed_evidence_count=2,
            candidate_genres=(("progressive_house", "Progressive House", 0.92, 2),),
            proposed_secondary_genres=(),
            proposed_styles=(),
            conflicts=(),
            ambiguous_terms=(),
            unknown_terms=(),
            warnings=(),
        )
        persistence = _PersistenceService()
        panel = TrackMetadataPanel(_ProxyFacade(), proposal_service=_ProposalService(proposal), persistence_service=persistence)
        panel.ids.setText("1")
        panel.search_external_metadata()
        panel.cancel_external_metadata()
        self._wait_for_proposal_worker_to_finish(panel)
        self.assertFalse(panel.apply_external_button.isEnabled())
        self.assertEqual(persistence.calls, [])
        panel.close()
        self.app.processEvents()

    def test_external_proposal_error_is_rendered_without_enabling_apply(self):
        panel = TrackMetadataPanel(
            _ProxyFacade(),
            proposal_service=_FailingProposalService(),
            persistence_service=_PersistenceService(),
        )
        panel.ids.setText("1")
        panel.search_external_metadata()
        self._wait_for_external_proposal(panel)

        self.assertIsNone(panel.proposal)
        self.assertIn("external service unavailable", panel.proposal_output.toPlainText())
        self.assertFalse(panel.apply_external_button.isEnabled())
        panel.close()
        self.app.processEvents()

    def test_invalid_proposal_disables_apply(self):
        proposal = MetadataProposalDTO(
            current_metadata=TrackMetadataDTO(track_id=1, title="Song", artist="Artist", album="Album", genre="house", rating=0, bpm=120, key="8A", energy=80),
            proposed_primary_genre_id=None,
            proposed_primary_genre_label=None,
            proposed_primary_confidence=0.0,
            proposed_evidence_count=0,
            candidate_genres=(),
            proposed_secondary_genres=(),
            proposed_styles=(),
            conflicts=(),
            ambiguous_terms=(),
            unknown_terms=(),
            warnings=(),
        )
        panel = TrackMetadataPanel(_ProxyFacade(), proposal_service=_ProposalService(proposal), persistence_service=_PersistenceService())
        panel.ids.setText("1")
        panel.search_external_metadata()
        self._wait_for_external_proposal(panel)
        self.assertFalse(panel.apply_external_button.isEnabled())
        panel.close()
        self.app.processEvents()

    def test_undo_restores_previous_state(self):
        proposal = MetadataProposalDTO(
            current_metadata=TrackMetadataDTO(track_id=1, title="Song", artist="Artist", album="Album", genre="house", rating=0, bpm=120, key="8A", energy=80),
            proposed_primary_genre_id="progressive_house",
            proposed_primary_genre_label="Progressive House",
            proposed_primary_confidence=0.92,
            proposed_evidence_count=2,
            candidate_genres=(("progressive_house", "Progressive House", 0.92, 2),),
            proposed_secondary_genres=(),
            proposed_styles=(),
            conflicts=(),
            ambiguous_terms=(),
            unknown_terms=(),
            warnings=(),
        )
        persistence = _PersistenceService()
        panel = TrackMetadataPanel(_ProxyFacade(), proposal_service=_ProposalService(proposal), persistence_service=persistence)
        panel.ids.setText("1")
        panel.search_external_metadata()
        self._wait_for_external_proposal(panel)
        panel.undo_external_metadata()
        self.assertEqual(persistence.undo_calls, [1])
        panel.close()
        self.app.processEvents()

    def test_main_window_exposes_optional_metadata_panel(self):
        window = MainWindow()
        self.assertIsInstance(window.track_metadata_panel, TrackMetadataPanel)
        self.assertIs(
            window.track_metadata_panel.facade.library_service,
            window.library_view.library_service,
        )
        window.navigate_to("metadata")
        metadata_page = window.workspace_stack.currentWidget()
        self.assertIsInstance(metadata_page, QScrollArea)
        self.assertIs(metadata_page.widget(), window.track_metadata_panel)
        self.assertEqual(metadata_page.horizontalScrollBarPolicy(), Qt.ScrollBarAlwaysOff)
        window.close()

    def test_metadata_workspace_remains_reachable_in_a_narrow_window(self):
        window = MainWindow()
        window.resize(900, 560)
        window.navigate_to("metadata")
        window.show()
        self.app.processEvents()

        metadata_page = window.workspace_stack.currentWidget()
        self.assertGreater(metadata_page.verticalScrollBar().maximum(), 0)
        self.assertEqual(window.track_metadata_panel.width(), metadata_page.viewport().width())
        window.close()

    def test_main_window_closes_injected_optional_preview_player(self):
        preview = _Preview()
        window = MainWindow(preview_player_service=preview)
        window.close()
        self.assertTrue(preview.closed)
