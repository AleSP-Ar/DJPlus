# External Sync Foundation — v0.7.5

## Implemented contract

v0.7.5 introduces an in-memory, provider-neutral synchronization boundary:

```text
DJPlus state supplied by caller
        |
SyncService
        |
SyncAdapter
        |
External platform state
```

No adapter connects to Traktor, Rekordbox, Serato, a network API, files, SQLite, repositories, or the DJPlus library. `MockSyncAdapter` exists solely to exercise the contract deterministically in memory.

## Mandatory flow

```text
READ → PLAN → PREVIEW → APPLY
```

1. `read()` returns normalized external state.
2. `plan(local_state)` compares caller-provided DJPlus state with that snapshot and creates an immutable `SyncPlanDTO`.
3. `preview(plan)` groups additions, updates, deletions, conflicts, and warnings in `SyncPreviewDTO`.
4. `apply(plan, confirmed=True)` is permitted only after previewing the same in-memory plan, receiving explicit confirmation, and verifying it has no conflicts.

The service rejects automatic apply, apply without preview, apply without confirmation, and apply with unresolved conflicts.

## Plan and conflict policy

`SyncPlanDTO` contains proposed changes, conflicts, warnings, and affected identifiers. The mock plans additions for local-only identifiers, deletions for external-only identifiers, and updates for ordinary value differences. A mock external entry marked `conflict=True` produces a conflict rather than an update.

This is a contract fixture, not a product conflict policy. Real adapters must preserve source IDs, source revisions, ownership metadata, and platform-specific fields before a planner can decide whether a difference is safe to apply.

## Security boundaries

- Sync is opt-in and requires explicit preview plus confirmation per plan.
- The current service does not read database state itself; a future facade supplies bounded DTOs.
- No conflict is resolved automatically.
- Apply is adapter-local; this foundation has no DJPlus write path.
- Future adapters must support cancellation, audit logging, backups/export, and dry-run fixtures before production use.

## Future adapters

Traktor, Rekordbox, and Serato require separate adapters, format/licensing review, fixtures, and ownership rules. Their playlist order, cue points, beat grids, ratings, and file references must not be assumed equivalent. A real adapter must never be enabled solely by implementing this abstract contract.

## Deferred and risks

- Persistence of sync plans, confirmations, source revisions, and audit events needs an approved additive migration.
- In-memory preview authorization is intentionally process-local; durable approvals require product and security decisions.
- Deletes are preview-only proposals until a product-specific backup and conflict policy exists.
- No UI, automatic scheduling, external API, file parser, or library mutation is implemented.
