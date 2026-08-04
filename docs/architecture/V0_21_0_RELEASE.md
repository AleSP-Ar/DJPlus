# v0.21.0 - Global Ranking

v0.21.0 closes Epic 19 with a local-only, read-only global ranking path. Publication is one local commit and annotated tag; it does not use GitHub, push, Git LFS or `ffmpeg.exe` in Git.

## Scope

`GlobalRankingService` is the canonical service. `TrackRepository` selects explicit score columns, `LibraryService` exposes immutable lightweight DTO batches, and the service maintains a bounded top-K heap. SQL filters BPM, key, genre, favorite and source exclusions. Ordering is score descending, confidence descending, then ascending `track_id`; incomplete metadata is counted instead of invented. `require_existing_file=True` excludes known missing paths before scoring and remains off by default for compatibility.

`create_global_recommendation_facade(...)` is the canonical composition. `ToolRegistry.default()` creates it automatically when Library, History and DJ Intelligence are supplied, with no QTableView, visible-page or visual-order dependency. Explicit facade injection remains supported. `SetBuilderFacade` can use the same top-K source; cancellation yields `CANCELLED`, `completed=False`, `partial=False` and no final set.

## Reliability and validation

The source streams batches and never materializes the whole library as ORM objects. Progress is emitted once per immutable batch. Ranking cancellation closes the iterator; errors are typed and do not corrupt a completed ranking. Structured events are limited to operational counts/statuses: no titles, artists, filenames, paths, prompts, playlists or ORM objects.

The real SQLite integration validates a winner beyond the first page and first batch, page-size independence, deterministic ties, availability-policy compatibility and an SQLAlchemy anti-N+1 guard. The observed SQLite formula is fixed setup cost plus one streaming candidate cursor query; it is not one query per candidate.

`tools/benchmark_global_ranking.py` creates and cleans a temporary SQLite database with 10,000 deterministic tracks, K=50 and batch size 250. It reports setup and ranking time, processed count, queries, batches, Python peak memory, winner and repeated-run equality. Reference validation measured 9,999 candidates, 40 batches, 2 queries, bounded ~293 KB Python peak and deterministic winner `track_id=10000`.

## Residual risks

Cancellation is cooperative, so an active database batch may complete before the next observation. The current deterministic greedy set planner deliberately does not use beam search. Caching is deferred until a measured invalidation contract exists. Traktor, Rekordbox and other DJ databases, external metadata APIs, Gemini and ChatGPT/OpenAI remain backlog and are not included.
