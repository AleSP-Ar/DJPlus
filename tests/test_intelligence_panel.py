import unittest
from types import SimpleNamespace

from qt_test_helpers import ensure_qapplication
from app.services.recommendation_facade import RecommendationFacade, RecommendationFacadeQueryDTO
from app.services.recommendation_scoring import RecommendationScoringEngine
from app.services.recommendation_service import RecommendationService
from app.services.dj_intelligence_service import DJIntelligenceService
from app.ui.intelligence_panel import LocalIntelligencePanel


class _FakeLibraryService:
    def __init__(self):
        self.queries = []

    def query(self, text="", **filters):
        self.queries.append((text, filters))
        candidate = SimpleNamespace(
            id=2,
            title="Candidate Track",
            artist="Candidate Artist",
            bpm=120,
            key="8A",
            energy=70,
        )
        return ([candidate], False)

    def load_more(self):
        return self.query()

    def count_results(self):
        return 1


class _FakeHistoryService:
    def list_history(self, event_type, limit):
        return []

    def count_history(self, candidate_id, event_type):
        return 0


class _FakeRecommendationService(RecommendationService):
    pass


class IntelligencePanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = ensure_qapplication()

    def setUp(self):
        library_service = _FakeLibraryService()
        history_service = _FakeHistoryService()
        scoring_engine = RecommendationScoringEngine(DJIntelligenceService(), history_service)
        recommendation_service = RecommendationService(scoring_engine)
        self.facade = RecommendationFacade(library_service, history_service, recommendation_service)
        self.panel = LocalIntelligencePanel(self.facade)

    def tearDown(self):
        self.panel.close()

    def test_search_button_is_disabled_without_reference_track(self):
        self.assertFalse(self.panel.search_button.isEnabled())
        self.assertEqual(self.panel.reference_title.text(), "Referencia: ninguna pista seleccionada")

    def test_setting_reference_track_enables_search_and_shows_details(self):
        track = SimpleNamespace(id=1, title="Ref", artist="Artist", album="Album", bpm=128, key="8A", energy=80)
        self.panel.set_reference_track(track)

        self.assertTrue(self.panel.search_button.isEnabled())
        self.assertIn("Artist — Ref", self.panel.reference_title.text())
        self.assertIn("BPM: 128", self.panel.reference_details.text())

    def test_search_recommendations_displays_local_scores(self):
        track = SimpleNamespace(id=1, title="Ref", artist="Artist", album="Album", bpm=120, key="8A", energy=70)
        self.panel.set_reference_track(track)
        self.panel._search_recommendations()

        self.assertIn("Resultados actualizados", self.panel.status_label.text())
        self.assertIn("score", self.panel.result_view.toPlainText().lower())
        self.assertIn("confianza", self.panel.result_view.toPlainText().lower())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
