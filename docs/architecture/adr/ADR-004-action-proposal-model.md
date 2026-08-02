# ADR-004: Action Proposal Model

## Context

Assistant tools can suggest writes, but suggestions must never become implicit execution.

## Decision

ActionPipeline converts suggestions into immutable `ActionProposalDTO` records with UTC IDs, basic-value payloads, and mandatory confirmation. It only manages proposal lifecycle in memory.

## Consequences

Proposals are explicit and inspectable but remain ephemeral. No callback, arbitrary object, or execution path is admitted.

## Rejected alternatives

- Executing actions immediately from a tool result.
- Storing executable callbacks in proposal payloads.
- Treating a text suggestion as an action record.
