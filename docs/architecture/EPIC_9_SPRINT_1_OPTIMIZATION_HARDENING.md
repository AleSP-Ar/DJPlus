# Epic 9 - Sprint 1: Core Optimization & Hardening

## Safe local caches

`LibraryQueryTool` caches only deterministic natural-language interpretation results. `ToolPlanExecutor` caches only immutable dependency topology. Both caches are bounded to 128 entries and clear atomically when full. No library rows, history, recommendation results or tool execution outcomes are cached, so live service state cannot become stale.

## Internal profiling

`OperationMetricsDTO` and `StageTimingDTO` retain the latest local timing snapshot for `LibraryQueryTool`, `RecommendationTool`, `RecommendationFacade` and `ToolPlanExecutor`. Their outputs and existing method signatures are unchanged.

## Benchmark

The automated large-library smoke benchmark evaluates a simulated 1,000-track candidate page, confirms filter re-query behavior and requires completion below two seconds. It measures in-memory service doubles only and is not a database benchmark.

No module accesses Repository directly or changes functional behavior, persisted data, tool actions or public DTO outputs.
