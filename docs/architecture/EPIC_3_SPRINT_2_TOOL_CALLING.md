# Epic 3 - Sprint 2: Favorites, History, and Imports

Sprint 2 extends the standard library tool allowlist with `FavoriteTool`, `HistoryTool`, and `ImportTool`.

- `FavoriteTool` reads favorite counts and state through `FavoriteService`. Marking or removing a favorite produces an immutable proposal only.
- `HistoryTool` reads filtered entries and aggregate counts through `HistoryService`. It never invokes a `record_*` method.
- `ImportTool` reads durable job summaries and details through `ImportManagerFacade`. Recovering incomplete jobs produces an immutable proposal and never calls recovery.

All raw call data is converted to immutable DTOs and bounded to allowed actions and arguments. `ToolRegistry.default(...)` registers these tools together with the Sprint 1 library, playlist, and collection tools when the three additional service dependencies are supplied. No tool imports repositories, ORM, SQLite, or filesystem APIs. `AssistantRuntime` remains unchanged.
