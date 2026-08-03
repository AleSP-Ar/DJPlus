# Epic 3 - Tool Calling Framework Completion

Epic 3 completes the bounded tool allowlist for library operations, favorites, history, import jobs, DJ compatibility, and music analysis.

## Validation boundary

`ToolSchemaValidator` validates each tool schema when it is registered and validates every `ToolCallDTO` immediately before dispatch. The validator supports bounded object properties, required fields, additional-property policy, enums, primitives, arrays, and the legacy track marker. Invalid calls return a typed failed `ToolResultDTO`; the target tool is not executed.

## Final tools

`DJCompatibilityTool` converts two JSON-like track payloads to immutable DTOs and invokes only `DJIntelligenceService`. `MusicAnalysisTool` converts a track identifier and requested feature names to immutable DTOs and invokes only `MusicAnalysisService`. Both return immutable public data and no proposed or executed actions.

The earlier library, playlist, collection, favorite, history, and import tools retain their service-only boundaries. All potential writes remain Action Pipeline proposals. No tool imports repositories, ORM, SQLite, filesystem APIs, or provider infrastructure.

## Runtime integration

`AssistantRuntime` accepts an optional injected `ToolRegistry` when no dispatcher is supplied. This is the minimal composition boundary: runtime generates the prompt and delegates calls to `ToolDispatcher`, which performs schema validation and invokes only registered tools. Runtime never resolves services, executes an action itself, or bypasses the dispatcher.
