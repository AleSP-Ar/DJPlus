# Epic 19 - Global Ranking Checklist

## Closed in v0.21.0

- [x] Lightweight candidate DTO and batch source protocol.
- [x] Stable SQL scalar iteration through LibraryService boundary.
- [x] Bounded deterministic top-K and cooperative cancellation.
- [x] Canonical factory and automatic global `ToolRegistry.default()` composition, with manual injection compatibility.
- [x] Global `RecommendationFacade` integration and `RecommendationTool` regression coverage.
- [x] Real SQLite source test: best candidate beyond first page/lot, stable page-size result and SQLAlchemy N+1 guard.
- [x] Bounded heap memory and immutable batch progress/cancellation coverage.
- [x] Typed Set Builder cancellation without a published journey; explicit sanitized ranking/set-builder events.
- [x] Reproducible 10,000-track temporary-SQLite benchmark with time, memory, query, batch and determinism metrics.
- [x] Epic 19 closed: no additional ranking algorithm or UI work is included here.
- [ ] Next stage: backend freeze and final cleanup. External DJ databases, metadata APIs and generative-AI integrations remain backlog.
