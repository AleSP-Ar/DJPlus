# Tool Registry and Dispatcher — Phase B

## Objective

Phase B establishes the official execution boundary for assistant tools:

```text
AssistantRuntime
      |
ToolDispatcher
      |
ToolRegistry
      |
AssistantTool
```

Only registered `AssistantTool` instances can be resolved by the dispatcher. The dispatcher is independent from UI, repositories, SQLite, ORM, filesystem, model providers, and concrete application services.

## Contracts

`ToolCallDTO` is an immutable request with a tool name and dictionary arguments. `ToolResultDTO` is an immutable execution outcome. A successful outcome contains an `AssistantToolResultDTO`; a failed outcome contains a safe error string and no result.

`ToolRegistry` accepts only `AssistantTool` instances, rejects blank or duplicate names, resolves names, and exposes registered names without returning its internal mapping. Unknown names are rejected with `UnknownToolError`.

`ToolDispatcher.dispatch()` validates the call, resolves it through the registry, and invokes the registered tool. Tool execution and result-contract failures are converted into typed failed results. An unknown tool is rejected before any execution occurs.

## Runtime relationship

`AssistantRuntime` holds a dispatcher dependency and passes every request call through it. The runtime has no tool registry and never calls `AssistantTool.execute()` directly. When a request contains no calls, the runtime uses an empty registry and preserves the no-effect behavior from Phase A.

## Safety limits

- Registry construction is an explicit allowlist; there is no dynamic discovery.
- Tools cannot be selected by arbitrary code outside the registered name set.
- The dispatcher does not create write actions, access persistence, read files, or communicate with models.
- This layer returns typed data only; confirmation and any future write path remain separate.

## Future extensions and risks

Future phases may add request-schema validation, rate limits, call budgets, audit events, and confirmation-aware write tools. Error strings are currently local typed outcomes; a provider adapter must redact and classify them before exposing them outside the process.
