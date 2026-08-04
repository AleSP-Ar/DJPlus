"""Canonical composition for global recommendation and set-planning boundaries."""

from .dj_intelligence_service import DJIntelligenceService
from .global_ranking_service import GlobalRankingService
from .recommendation_facade import RecommendationFacade
from .recommendation_scoring import RecommendationScoringEngine
from .recommendation_service import RecommendationService


def create_global_recommendation_facade(library_service, history_service, dj_intelligence_service=None):
    """Compose the global path explicitly; callers may still inject facades."""
    intelligence = dj_intelligence_service or DJIntelligenceService()
    recommendation = RecommendationService(RecommendationScoringEngine(intelligence, history_service))
    ranking = GlobalRankingService(library_service, recommendation)
    return RecommendationFacade(library_service, history_service, recommendation, global_ranking_service=ranking)
