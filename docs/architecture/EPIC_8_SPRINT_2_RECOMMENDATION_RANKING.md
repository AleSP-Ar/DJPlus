# Epic 8 - Sprint 2: Recommendation Ranking Service

`RecommendationService` receives a current track and immutable candidate tuple through `RecommendationQueryDTO`. It excludes the current track, delegates each remaining candidate to `RecommendationScoringEngine`, sorts by score descending, then confidence descending, then candidate ID ascending, and applies the configured limit.

Each `RankedRecommendationDTO` contains a stable rank, score, confidence and the original explainable reasons. The service is in-memory only: it does not persist recommendations, access repositories, or use generative AI.
