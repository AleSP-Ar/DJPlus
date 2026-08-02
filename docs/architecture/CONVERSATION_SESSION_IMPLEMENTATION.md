# Conversation Session — Phase D

## Objective

`ConversationSession` owns the live, in-memory state of one assistant conversation. It is deliberately not memory: it does not summarize, tokenize, truncate, persist, retrieve, or automatically delete messages.

## Lifecycle

A caller creates a session with an optional identifier and metadata. The session exposes immutable `ConversationSessionDTO` snapshots containing its identifier, creation time, last activity, conversation version, and immutable metadata. `close()` marks the session closed while preserving readable history; no messages may be added or cleared after closure.

There is no global registry, singleton, lock, cache, or background worker. Each instance is isolated and can later be owned by a worker without sharing state across sessions.

## Messages and roles

`ConversationMessageDTO` is immutable and uses `MessageRole`: `SYSTEM`, `USER`, `ASSISTANT`, or `TOOL`. Messages are append-only; `history()`/`get_history()` return an immutable chronological tuple. `message_count()`/`get_message_count()` expose the count without mutable state. Manual `clear_history()` and explicit `update_last_activity()` update activity. Existing messages are never modified.

## Runtime relationship

`AssistantRuntime` may receive an injected `ConversationSession`. For each matching `RuntimeRequestDTO.session_id`, it records the unchanged user query as a `USER` message before prompt construction. No assistant message is recorded in this phase because the runtime does not yet generate assistant responses. A future response-producing phase must append an `ASSISTANT` message only after producing a validated response.

## Limits and future integrations

The module has no dependency on PromptBuilder, ToolDispatcher, SQLite, repositories, ORM, filesystem, UI, networking, model providers, persistence, embeddings, vector databases, or long-term memory. Future phases may add explicitly approved session ownership, bounded retention, persistence, and safe tool-message recording without altering the append-only message contract.

## Risks

History is intentionally unbounded for the life of a session. Long-lived sessions can grow in memory, so future limits must be explicit policy decisions rather than automatic behavior hidden in this foundation.
