# ADR-001: Runtime Boundaries

## Context

The assistant needs an internal coordinator without coupling UI, repositories, database, filesystem, or model providers.

## Decision

`AssistantRuntime` composes DTO-based collaborators: PromptBuilder, ToolDispatcher, ConversationSession, ActionPipeline, and ConfirmationManager. It receives bounded context and injected dependencies only.

## Consequences

The Runtime remains testable and provider-neutral. Integrations must enter through explicit adapters and cannot acquire infrastructure through the Runtime.

## Rejected alternatives

- Letting the Runtime query repositories directly.
- Giving UI or model adapters database access.
- A global singleton runtime.
