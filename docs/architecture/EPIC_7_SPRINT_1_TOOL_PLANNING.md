# Epic 7 - Sprint 1: Tool Planning Framework

`ToolPlanner` transforms a user query into immutable `ToolPlanDTO` data. `DeterministicToolPlanner` uses fixed keyword rules and validates selected names through `ToolRegistry`; it does not dispatch or execute a tool.

`PlannedToolCallDTO` records a stable step ID, `ToolCallDTO` and optional dependencies. `ToolPlanDTO` rejects duplicate IDs, self-dependencies and dependencies that do not point to an earlier step. This makes multi-tool order explicit while preserving a pure planning boundary.

The initial planner recognizes library, playlist and collection requests. Its output is not wired into execution; a future review stage will require separate approval.
