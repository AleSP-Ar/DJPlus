# Epic 4 - Sprint 2: Operational Safety

The execution foundation remains a fully simulated boundary. It introduces no service invocation, repository access, SQLite access, or library mutation.

## Idempotency

`IdempotencyRegistry` is an in-memory, process-local registry. `MockActionExecutor.execute()` claims an `execution_id` before simulating its configured outcome. A second attempt with that same identifier is rejected through a typed `ExecutionResultDTO`; it does not run the simulation again.

## Audit

`ExecutionAuditLog` is append-only in memory. Every valid execution and rollback attempt receives an immutable `ExecutionAuditEntryDTO`, including simulated success, configured failure, duplicate rejection, and rollback rejection. Audit metadata is read-only to consumers.

## Rollback

`ActionExecutor` now declares `rollback(request)`. `MockActionExecutor.rollback()` only returns a typed, deterministic `RollbackResultDTO`; it never reverses a real service operation. It rejects unknown execution IDs as a typed simulated result and audits that attempt.

This is deliberately process-local test infrastructure. A real implementation needs durable atomic idempotency storage, authenticated audit retention, authorization, concurrency control, and domain-specific compensating transactions before it can perform any write.
