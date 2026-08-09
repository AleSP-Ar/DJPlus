import unittest
from types import SimpleNamespace

from app.services.dj_intelligence_service import DJIntelligenceService
from app.services.global_ranking_service import GlobalRankingRequestDTO, GlobalRankingService, InvalidRankingRequestError, RankingTrackDTO
from app.services.recommendation_scoring import RecommendationScoringEngine
from app.services.recommendation_service import RecommendationService
from app.services.global_ranking_factory import create_global_recommendation_facade


class _History:
    def count_history(self, track_id=None, event_type=None): return 0
    def list_history(self, track_id=None, event_type=None, limit=None): return ()
class _Source:
    def __init__(self, batches): self.batches = batches; self.calls = []
    def iter_ranking_candidates(self, **kwargs):
        self.calls.append(kwargs)
        yield from self.batches
    def query(self, *args, **kwargs): return (), False
    def load_more(self): return (), False
    def count_results(self): return sum(len(batch) for batch in self.batches)
class _Cancel:
    def __init__(self): self.value = False
    def is_cancelled(self): return self.value


class _CountingCancel:
    def __init__(self, cancel_at): self.cancel_at, self.calls = cancel_at, 0
    def is_cancelled(self):
        self.calls += 1
        return self.calls >= self.cancel_at


class GlobalRankingServiceTests(unittest.TestCase):
    def setUp(self):
        self.current = SimpleNamespace(id=1, bpm=124, key="8A", energy=70, rating=4, is_favorite=True)
        scoring = RecommendationScoringEngine(DJIntelligenceService(), _History())
        self.service = GlobalRankingService(_Source(()), RecommendationService(scoring))
    def _rank(self, batches, **kwargs):
        source = _Source(batches); service = GlobalRankingService(source, self.service._recommendation_service)
        return service.rank(GlobalRankingRequestDTO(self.current, **kwargs)), source
    def test_top_k_is_global_deterministic_and_independent_of_batch_order(self):
        best = RankingTrackDTO(9, 124, "8A", 70); weak = RankingTrackDTO(2, 90, "1A", 10); medium = RankingTrackDTO(3, 123, "8A", 68)
        result, source = self._rank(((weak,), (medium,), (best,)), limit=2, batch_size=1)
        self.assertEqual([item.candidate_track_id for item in result.recommendations], [3, 9])
        self.assertEqual((result.stats.processed, result.stats.batches, source.calls[0]["batch_size"]), (3, 3, 1))
    def test_ties_use_track_id_and_missing_metadata_is_reported(self):
        a = RankingTrackDTO(4, 124, "8A", 70); b = RankingTrackDTO(2, 124, "8A", 70); missing = RankingTrackDTO(3, None, None, None)
        result, _ = self._rank(((a, missing, b),), limit=3)
        self.assertEqual([item.candidate_track_id for item in result.recommendations[:2]], [2, 4])
        self.assertEqual(result.stats.incomplete_metadata, 1)

    def test_zero_score_candidates_are_discarded_before_top_k(self):
        zero_score = RankingTrackDTO(2, None, None, None)
        result, _ = self._rank(((zero_score,),), limit=3)

        self.assertEqual(result.recommendations, ())
        self.assertEqual(result.stats.discarded, 1)
    def test_cancelled_does_not_publish_partial_results_and_validates_k(self):
        token = _Cancel(); token.value = True
        result, _ = self._rank(((RankingTrackDTO(2, 124, "8A", 70),),), cancellation=token)
        self.assertEqual((result.status, result.recommendations), ("cancelled", ()))
        with self.assertRaises(InvalidRankingRequestError): GlobalRankingRequestDTO(self.current, limit=0)

    def test_factory_composes_global_facade_without_page_source(self):
        source = _Source(((RankingTrackDTO(2, 124, "8A", 70),),))
        facade = create_global_recommendation_facade(source, _History())
        result = facade.recommend(__import__("app.services.recommendation_facade", fromlist=["RecommendationFacadeQueryDTO"]).RecommendationFacadeQueryDTO(self.current))
        self.assertIn("Alcance global", result.explanation)

    def test_result_is_bounded_and_cancellation_closes_source_iterator(self):
        closed = []
        class Source(_Source):
            def iter_ranking_candidates(self, **kwargs):
                try:
                    for item in range(2, 1002):
                        yield (RankingTrackDTO(item, 124, "8A", 70),)
                finally:
                    closed.append(True)
        token = _CountingCancel(4)
        service = GlobalRankingService(Source(()), self.service._recommendation_service)
        result = service.rank(GlobalRankingRequestDTO(self.current, limit=5, batch_size=1, cancellation=token))
        self.assertTrue(result.cancelled)
        self.assertEqual(result.recommendations, ())
        self.assertEqual(result.candidates, ())
        self.assertEqual(closed, [True])

    def test_structured_events_contain_only_safe_operational_counts(self):
        records = []
        class Logger:
            def info(self, message, **kwargs): records.append((message, kwargs["extra"]))
        source = _Source(((RankingTrackDTO(2, 124, "8A", 70),),))
        service = GlobalRankingService(source, self.service._recommendation_service, logger=Logger())
        service.rank(GlobalRankingRequestDTO(self.current))
        self.assertEqual([item[0] for item in records], ["global_ranking_started", "global_ranking_completed"])
        serialized = repr(records)
        self.assertNotIn("filepath", serialized)
        self.assertNotIn("title", serialized)

    def test_explicit_availability_policy_discards_known_missing_file(self):
        missing = RankingTrackDTO(2, 124, "8A", 70, filepath="definitely-missing-audio-file.wav")
        result, _ = self._rank(((missing,),), require_existing_file=True)
        self.assertEqual((result.recommendations, result.stats.discarded), ((), 1))
