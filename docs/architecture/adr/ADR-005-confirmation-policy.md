# ADR-005: Confirmation Policy

## Context

Proposals require a decision boundary before any future write integration.

## Decision

ConfirmationManager applies a pure `ConfirmationPolicy`. The initial policy confirms a proposal once only if it exists, remains active, and explicitly requires confirmation. It returns a DTO and never executes.

## Consequences

Confirmation is distinguishable from authorization and execution. Duplicate detection is local and temporary; a future write service must revalidate state and permissions.

## Rejected alternatives

- Treating confirmation as execution approval.
- Calling write services from confirmation policies.
- Persisting authorization state prematurely.
