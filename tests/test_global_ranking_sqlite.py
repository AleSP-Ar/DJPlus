import unittest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, Track
from app.repository.track_repository import TrackRepository
from app.services.dj_intelligence_service import DJIntelligenceService
from app.services.global_ranking_factory import create_global_recommendation_facade
from app.services.library_service import LibraryService


class _History:
    def list_history(self, track_id=None, event_type=None, limit=None): return ()
    def count_history(self, track_id=None, event_type=None): return 0


class GlobalRankingSQLiteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine); self.session = sessionmaker(bind=self.engine)()
        tracks = [Track(id=1, title="origin", artist="a", filepath="origin.mp3", bpm=124, key="8A", energy=70)]
        tracks += [Track(id=index, title="x", artist="a", filepath=f"{index}.mp3", bpm=90, key="1A", energy=10) for index in range(2, 651)]
        tracks += [Track(id=651, title="best", artist="a", filepath="best.mp3", bpm=124, key="8A", energy=70)]
        tracks += [Track(id=652, title="missing", artist="a", filepath="missing.mp3", bpm=None, key=None, energy=None)]
        self.session.add_all(tracks); self.session.commit()
        self.library = LibraryService(TrackRepository(session=self.session), page_size=5)
        self.current = self.session.get(Track, 1)
    def tearDown(self): self.session.close(); self.engine.dispose()
    def test_real_source_finds_best_beyond_page_and_lot_without_n_plus_one(self):
        facade = create_global_recommendation_facade(self.library, _History(), DJIntelligenceService())
        statements = []
        listener = lambda *_args: statements.append(1)
        event.listen(self.engine, "before_cursor_execute", listener)
        try:
            from app.services.recommendation_facade import RecommendationFacadeQueryDTO
            result = facade.recommend(RecommendationFacadeQueryDTO(self.current, limit=5))
        finally: event.remove(self.engine, "before_cursor_execute", listener)
        self.assertEqual(result.recommendations[0].candidate_track_id, 651)
        self.assertIn("Alcance global", result.explanation)
        self.assertLess(len(statements), 8, "El ranking no debe consultar por candidata")
        self.assertEqual(result.page_number, 1)

    def test_page_size_and_insertion_visual_order_do_not_change_global_winner(self):
        facade = create_global_recommendation_facade(self.library, _History(), DJIntelligenceService())
        from app.services.recommendation_facade import RecommendationFacadeQueryDTO
        first = facade.recommend(RecommendationFacadeQueryDTO(self.current, limit=5))
        alternate = create_global_recommendation_facade(
            LibraryService(TrackRepository(session=self.session), page_size=97), _History(), DJIntelligenceService()
        ).recommend(RecommendationFacadeQueryDTO(self.current, limit=5))
        self.assertEqual(first.recommendations[0].candidate_track_id, 651)
        self.assertEqual(first.recommendations, alternate.recommendations)

    def test_existing_file_policy_is_opt_in_and_preserves_default_compatibility(self):
        from app.services.global_ranking_service import GlobalRankingRequestDTO
        facade = create_global_recommendation_facade(self.library, _History(), DJIntelligenceService())
        compatible = facade.recommend(__import__("app.services.recommendation_facade", fromlist=["RecommendationFacadeQueryDTO"]).RecommendationFacadeQueryDTO(self.current, limit=5))
        strict = facade._global_ranking_service.rank(GlobalRankingRequestDTO(self.current, limit=5, require_existing_file=True))
        self.assertEqual(compatible.recommendations[0].candidate_track_id, 651)
        self.assertEqual(strict.recommendations, ())
        self.assertGreater(strict.stats.discarded, 0)
