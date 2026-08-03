# Epic 4 - Sprint 1: Execution Framework Foundation

`ActionExecutor` is a new abstract boundary for the future execution of confirmed `ActionProposalDTO` records. It does not receive services, repositories, sessions, callbacks, filesystem paths, or provider clients.

`ExecutionRequestDTO` requires an immutable proposal, explicit confirmation, an execution identifier, and an aware UTC timestamp. `ExecutionResultDTO` is immutable and always marks the outcome as simulated. `MockActionExecutor` is the only implementation; it records requests in memory and deterministically returns configured success or failure results.

No proposal is applied, no service method is invoked, and no library, SQLite database, repository, or external system changes. Connecting a real executor requires a later, separately approved authorization, idempotency, audit, rollback, and service-routing design.
