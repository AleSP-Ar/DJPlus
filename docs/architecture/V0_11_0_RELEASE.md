# DJPlus v0.11.0 — DJ Recommendation Engine

## Release scope

- Recommendation Scoring Engine with deterministic BPM, key, energy and history contributions.
- Deterministic ranking by score, confidence and candidate ID.
- `RecommendationFacade` using only `LibraryService`, `HistoryService` and `RecommendationService`.
- Optional candidate filters for BPM, key, genre and favorite status.
- Exclusion of the current track and recently played tracks.
- Read-only `RecommendationTool` integration through `ToolRegistry` and visual rendering in `AssistantPanel`.

## Safety posture

Recommendations are in-memory DTOs. No repository, SQLite access, persistence, generative AI, network call or automatic playlist creation is performed by the recommendation stack.

## Current limitation

Ranking is calculated only for the candidate page returned by `LibraryService`. It is not a global ranking across every matching library track.

## Release checks

The candidate requires the full automated suite, `compileall`, `git diff --check`, a library benchmark and a headless `AssistantPanel` smoke test. Commit and tag require separate approval.
