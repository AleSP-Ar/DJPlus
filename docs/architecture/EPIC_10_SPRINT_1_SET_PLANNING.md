# Epic 10 - Sprint 1: Set Planning Core

`SetPlanningEngine` builds a deterministic, in-memory sequence from an initial track and candidate tracks. For every transition it calls `RecommendationService`, preserves the returned reasons, rejects duplicate IDs and enforces maximum BPM and energy jumps through `SetPlanningPolicyDTO`.

The result is a `SetPlanDTO`. When no remaining candidate satisfies the transition policy, it returns the valid prefix as an explicitly partial plan. The core does not persist plans, create playlists, access UI, Repository or SQLite, and does not use generative AI.
