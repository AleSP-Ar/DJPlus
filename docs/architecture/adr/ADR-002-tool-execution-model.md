# ADR-002: Tool Execution Model

## Context

Future assistant requests require controlled use of existing service capabilities.

## Decision

Tools are allowlisted in ToolRegistry and invoked only by ToolDispatcher from typed `ToolCallDTO` requests. The Runtime delegates; it never resolves or invokes an `AssistantTool` directly.

## Consequences

Tool selection is explicit, duplicate names are rejected, and outcomes are typed. Schema budgets and audit logs remain future work.

## Rejected alternatives

- Dynamic tool discovery.
- Calling service methods from prompts or UI.
- Executing arbitrary callbacks supplied by a model.
