# Epic 3 - Sprint 1: Tool Calling Framework

This sprint introduces the library-facing tool allowlist for the assistant.

## Tools

- `LibraryQueryTool` reads the total track count through `LibraryService`.
- `PlaylistTool` reads playlist and membership counts through `PlaylistService`; it can only propose `create_playlist`.
- `CollectionTool` reads collection and membership counts through `CollectionService`; it can only propose `create_collection` for manual or smart collections.

Each tool converts raw call arguments into an immutable input DTO before calling a Service. Results expose immutable public data. Proposed actions are immutable records only: the tools do not call `create_playlist`, `create_collection`, repositories, ORM, SQLite, or filesystem APIs.

## Registry integration

`ToolRegistry.default(library_service, playlist_service, collection_service)` creates the standard allowlist with `library_query`, `playlist`, and `collection`. Callers supply existing Services, preserving dependency ownership and preventing the registry from constructing repositories or persistence sessions.

## Safety

The dispatcher remains the only execution boundary. `AssistantRuntime` was not modified; it receives tool calls only through its existing `ToolDispatcher` collaboration. Confirmation and Action Pipeline remain responsible for any later execution of proposed actions.
