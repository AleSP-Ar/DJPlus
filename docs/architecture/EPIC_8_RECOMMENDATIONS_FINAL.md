# Epic 8 - Recommendation Engine: Final Architecture Audit

`RecommendationFacade` is a read-only composition of `LibraryService`, `HistoryService` and `RecommendationService`. It requests a candidate page through `LibraryService.query()` with optional BPM, key, genre and favorite filters; later pages use `LibraryService.load_more()` only.

Recently played IDs returned by `HistoryService.list_history()` and the current track are excluded before scoring. The facade returns `RecommendationPageDTO` with ordered explainable recommendations, count, page state, history exclusions and a deterministic explanation.

`RecommendationTool` exposes this output through `ToolRegistry` and returns no action proposals. `AssistantPanel` already renders successful tool responses and result data without adding any write path.

No module in the recommendation stack imports repositories, SQLite, provider clients or playlist creation. Recommendations are in-memory values only; no model generation or storage is used.

## Benchmark

The release benchmark should score 100 repeated in-memory facade pages using service doubles. It is a regression smoke check, not a database or UI performance claim.
