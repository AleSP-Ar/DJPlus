# DJPlus v0.10.0 — Advanced Tool Calling

## Release scope

- Deterministic Tool Planner producing immutable, ordered `ToolPlanDTO` data.
- Tool Plan Executor using only `ToolDispatcher` and enforcing declared step dependencies.
- Typed step states: `success`, `failed` and `blocked`.
- Tool Result Composer producing deterministic structured summaries for complete, partial and failed plans.
- Optional `AssistantRuntime` integration which leaves direct tool calls unchanged when no plan is supplied.

## Safety posture

The planning stack does not execute actions, use `ActionExecutor`, access Services or persistence, or create network requests. Tools remain allowlisted through `ToolRegistry` and are invoked only by the dispatcher.

## Release checks

v0.10.0 requires the complete suite, `compileall`, `git diff --check`, a lightweight 100-plan benchmark and a headless `AssistantPanel` smoke test. Commit and tag creation require separate explicit approval.
