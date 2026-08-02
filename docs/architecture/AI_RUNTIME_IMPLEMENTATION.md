# AI Runtime — Epic 1 Architecture

## Release status

Epic 1 AI Runtime Core is complete for DJPlus v0.8.0. It delivers a provider-neutral internal runtime only: no model provider is connected, no conversation or proposal is persisted, and no proposed action is executed. The release is prepared for commit and tag approval.

## Objective

Epic 1 provides a provider-neutral internal runtime for the assistant. `AssistantRuntime` owns request coordination while remaining independent from UI, persistence, repositories, ORM, filesystem access, concrete application services, and model providers.

```text
User
  |
AssistantFacade
  |
AssistantRuntime
  |-- ConversationSession (optional, live state)
  |-- PromptBuilder <---- AssistantContextDTO + ToolRegistry metadata
  |-- ToolDispatcher ----> ToolRegistry ----> registered AssistantTool
  |-- ActionPipeline <---- typed tool proposals
  |-- ConfirmationManager -> ConfirmationPolicy
  |
RuntimeResultDTO
```

## Contracts and flow

`RuntimeRequestDTO` is immutable and validates a non-empty user query, an `AssistantContextDTO`, a session identifier, an aware UTC timestamp, optional typed tool calls, and an optional confirmation request. `RuntimeResultDTO` is immutable and contains the generated prompt, calls, typed results, future response slot, proposed actions, and confirmation result.

`AssistantRuntime.process()` accepts only `RuntimeRequestDTO`. It validates the boundary and delegates every `ToolCallDTO` to its injected `ToolDispatcher`; the runtime never resolves or invokes an `AssistantTool` itself. The resulting typed outcomes are copied to `RuntimeResultDTO`. A generated prompt is included, while assistant response generation remains intentionally absent. Tool proposals are converted into immutable Action Pipeline records. An optional confirmation request is delegated to Confirmation Manager and returned as a decision DTO; the Runtime never executes an action.

ConversationSession records user messages only when explicitly injected and session IDs match. `PromptBuilder` builds `PromptDTO` from the validated request, Assistant Context, and Tool Registry metadata. ToolDispatcher is the allowlisted execution boundary for registered tools; ActionPipeline represents proposals only; ConfirmationManager makes policy decisions only. These collaborators remain separate and in-memory.

## Safety limits

- The runtime does not import or access repositories, SQLite, ORM, database sessions, filesystem, UI, or concrete services.
- It does not call a model, write data, create background jobs, or modify the supplied context. Tool invocation is delegated only to ToolDispatcher.
- It has no singleton, global state, cache, or persistent memory.
- The runtime accepts the bounded context DTO created by Assistant Context rather than acquiring data itself.

## Future extensions

A future provider adapter may serialize the provider-neutral `PromptDTO`. It must remain outside this core and apply explicit redaction, authorization, confirmation, auditing, and transport policies. Future extensions may add schema validation, tool budgets, audit persistence, controlled session ownership, and a dedicated write boundary after confirmation.

## Risks

This phase deliberately produces no response. Future phases must preserve the distinction between planned calls and executed calls, must not give providers direct service or persistence access, and must introduce size/redaction limits before any context can leave the local process.

## Release contents

- Assistant Runtime and immutable request/result DTOs.
- Prompt Builder with bounded context and registry metadata.
- Tool Registry and Tool Dispatcher allowlist boundary.
- Ephemeral Conversation Session lifecycle.
- Action Pipeline for explicit proposed actions.
- Confirmation Manager and policy contract without execution.
- Runtime architectural audit and ADR-001 through ADR-005.
