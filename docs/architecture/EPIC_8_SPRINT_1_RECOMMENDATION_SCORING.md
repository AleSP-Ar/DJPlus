# Epic 8 - Sprint 1: Recommendation Scoring Engine

`RecommendationScoringEngine` evaluates one candidate against one reference track. It uses `DJIntelligenceService` for read-only compatibility validation and `HistoryService.count_history()` for play history. It never accesses repositories or persistence directly.

The deterministic weights are BPM 35, key 25, energy 25 and history 15. `RecommendationScoreDTO` always includes four ordered `RecommendationReasonDTO` values, making missing data, compatibility and history contribution explicit.

The engine intentionally does not collect candidates or rank them. Ranking, presentation and generative AI are outside this sprint.
