# Prompt Builder — Phase C

## Objective

`PromptBuilder` constructs a deterministic, provider-neutral `PromptDTO` for a future model adapter. It builds data only: it does not invoke a model, generate an assistant response, execute tools, access persistence, read files, or know the UI.

```text
RuntimeRequestDTO + ToolRegistry
             |
        PromptBuilder
             |
          PromptDTO
```

## Components

`PromptDTO` is immutable and contains five immutable fields: `system_prompt`, `context_block`, `user_prompt`, `available_tools`, and `metadata`. `ContextBlockDTO` preserves Assistant Context sources, timestamp, version, and a recursively frozen data snapshot. `PromptMetadataDTO` records runtime version, UTC generation time, and prompt version. Tool metadata is exposed as immutable `ToolDefinitionDTO` values from `ToolRegistry`; no implementation objects are included.

## Construction rules

- The system prompt is deterministic and contains only assistant identity, runtime restrictions, safety limits, and runtime version.
- The context block reads only `RuntimeRequestDTO.assistant_context`; it never acquires data from services or other sources.
- The user prompt is the unmodified `user_query`.
- Available tools come only from the composed `ToolRegistry` and contain name, description, and input schema.

## Runtime and dispatcher relationship

`AssistantRuntime` composes a `PromptBuilder` with the same registry used by its `ToolDispatcher`. It calls `build()` before dispatching requested calls and returns the resulting `PromptDTO` inside `RuntimeResultDTO`. Prompt construction does not select, dispatch, or execute tools.

## Security and versioning

The builder imports only DTO/context and registry metadata boundaries. It has no repository, SQLite, ORM, filesystem, UI, concrete-service, or provider dependency. Prompt and runtime versions are explicit. Generated timestamps are UTC and are metadata only, so they do not affect deterministic system instructions.

## Future extensions and risks

A provider adapter may serialize `PromptDTO` only after approved size limits, field-level redaction, transport controls, and audit policies exist. Tool schemas remain descriptive metadata; provider output must be validated through the runtime and dispatcher rather than trusted as executable instructions.
