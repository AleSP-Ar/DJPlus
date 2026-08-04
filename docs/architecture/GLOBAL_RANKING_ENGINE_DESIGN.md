# Global Ranking Engine

Epic 19 Sprint 19.1 replaces page-bound recommendation ranking with `GlobalRankingService`. `LibraryService.iter_ranking_candidates` exposes only scalar score fields through batched repository reads, ordered by track ID; it does not alter the UI page or materialize ORM tracks.

The canonical composition is `create_global_recommendation_facade(library_service, history_service, dj_intelligence_service=None)`. `ToolRegistry.default()` uses it automatically when its library, history and DJ-intelligence dependencies are present; explicit manual `recommendation_facade` injection remains supported. The first recommendation request therefore has global scope by default, while the legacy `load_more` API remains compatible.

The service keeps a heap of K scored candidates. Time is O(N log K), extra memory is O(K + batch), and final ordering is score descending, confidence descending, then track ID ascending. SQL applies source exclusion and supported filters before scoring. Cancellation is cooperative between batches and candidates; a cancelled result publishes no partial ranking. Progress is emitted once per immutable batch summary, never with ORM entities.

The real SQLite integration uses scalar columns and `yield_per(batch_size)`, not a `Track` object per candidate. On SQLite it observes one candidate cursor query plus fixed setup queries (the portable formula is `fixed queries + streamed candidate query`; a driver that pages server-side may use `fixed + O(batches)`). It is deliberately not `O(candidates)` queries and is protected by an event-count regression test.

`GlobalRankingRequestDTO.require_existing_file` is an explicit availability policy. It is off by default for backward compatibility; when enabled, candidates with a known missing filepath are discarded before scoring. It never writes, moves or repairs media.

The 10,000-track benchmark uses batch size 250 and K=50 in a temporary SQLite database, repeats the ranking for determinism and reports `perf_counter`, `tracemalloc`, queries and batches. The source holds only the active scalar batch; the heap and returned result hold at most K candidates. No cache is added: the measured path is already bounded and a cache needs an invalidation contract before it can be justified.

`SetBuilderFacade` can consume this same bounded source. If it is cancelled it returns `SetBuilderCancelledResultDTO(status="CANCELLED", completed=False, partial=False)` and never publishes a final journey. It logs only counts/identifiers through named `djplus` loggers. Beam search is intentionally not implemented: deterministic greedy planning remains the established planning policy and no correctness measurement requires a broader search.

The existing recommendation scoring algorithm remains the source of BPM, harmonic, energy and history explanations. Missing metadata is counted rather than invented. `RecommendationFacade` can opt into the global service while keeping its legacy paged API compatible. Cache is intentionally deferred until query and top-K measurements justify it.
