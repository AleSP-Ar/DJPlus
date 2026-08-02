# Unit of Work Design — Sprint 6.1.4A

## Problem

DJPlus repositories create their own SQLAlchemy session by default and historically commit each write independently. That is convenient for isolated operations, but it cannot guarantee consistency when one application action touches multiple aggregates.

The upcoming track-import flow must create or update a track, optionally append its `added` history event, and update the import item state as one all-or-nothing action. Independent commits could leave a track without history, or an imported item whose track write failed.

## Solution

`app.database.unit_of_work.UnitOfWork` is a context manager that:

1. creates one SQLAlchemy session;
2. exposes `TrackRepository`, `HistoryRepository`, and `ImportRepository` sharing that exact session;
3. commits once on successful context exit;
4. rolls back on an exception; and
5. closes the session in all cases.

```python
with UnitOfWork() as unit_of_work:
    # All repositories use unit_of_work.session.
    unit_of_work.imports.create_job(commit=False)
    unit_of_work.history.record_event(track_id, "added", commit=False)
    # Context exit commits once.
```

The context manager re-raises exceptions after rollback. It does not swallow failures or convert them to item states; the future application service owns that policy.

## Repository compatibility

Repositories continue to accept an optional external session, as they did before. Existing callers preserve current behavior because mutation methods still commit by default.

`ImportRepository` now accepts `commit=False` on its mutation methods. In that mode it flushes so generated IDs and foreign-key validation are available, but leaves the final commit to the Unit of Work. `HistoryRepository.record_event()` already supports this convention. `TrackRepository` is read-only at this stage and already accepts an external session.

No model, migration, table, or legacy scanner behavior changed in this sprint.

## Transaction flow

```text
Application service
        |
        v
with UnitOfWork() as uow
        |
        +--> TrackRepository(session=uow.session)
        +--> HistoryRepository(session=uow.session, commit=False)
        +--> ImportRepository(session=uow.session, commit=False)
        |
        v
single commit on success / rollback on exception
        |
        v
session close
```

The Unit of Work is intentionally synchronous and independent of PySide. A future worker can invoke a service that creates a Unit of Work without moving transaction decisions into the UI thread.

## Use in Import Engine

Track integration uses one Unit of Work per import item:

1. resolve filepath and snapshot;
2. create or update the `Track` through a repository method with caller-controlled commit;
3. append `added` history only for a new track;
4. set the import item terminal state and counters;
5. commit all changes once.

If any operation fails, the database work rolls back together. `ImportService` then attempts to mark the item failed in a separate recovery transaction.

## Boundaries and risks

- Repositories must not call their default `commit=True` methods inside a Unit of Work; future service code must pass `commit=False` explicitly.
- A long-running import must keep one Unit of Work per item, not one per full folder, to minimize SQLite write locks and make cancellation/recovery predictable.
- Existing services retain their current single-repository transaction behavior; migrating them is separate approved work.
- Nested Unit of Work behavior is intentionally out of scope. Callers should pass the existing session rather than create nested transaction owners.
