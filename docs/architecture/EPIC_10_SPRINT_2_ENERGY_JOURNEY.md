# Epic 10 - Sprint 2: Energy Journey Planning

`EnergyJourneyPlanner` divides a set into warm-up, build, peak and cooldown. It creates deterministic energy targets for ascending, descending and arc curves, then delegates each accepted transition to `SetPlanningEngine` and its `RecommendationService` boundary.

Candidates outside the target tolerance are not selected. When no suitable candidate remains, the engine returns the valid prefix as a partial plan and explains the unavailable energy target. The module is in-memory only: it creates neither playlists nor persistence, UI, Repository, SQLite or generative-AI dependencies.
