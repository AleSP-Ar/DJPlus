# ADR-003: Conversation Lifecycle

## Context

The Runtime needs local conversational continuity without introducing persistent memory.

## Decision

ConversationSession owns one in-memory append-only ordered history. Sessions are explicitly created, cleared, and closed; snapshots and messages are immutable DTOs.

## Consequences

There is no global session state, persistence, summarization, retrieval, or automatic retention. Long-running sessions remain an explicit memory-risk tradeoff.

## Rejected alternatives

- SQLite-backed conversations.
- Global session registries.
- Automatic summaries or token trimming.
