# Collection Engine Design — Sprint 5.4

## Scope

The Collection Engine manages named, manual groupings of existing tracks. It does not scan folders, edit tracks, infer rules, synchronize data, or expose repository details to the UI. Smart Collections are intentionally deferred; the shared collection record makes their future introduction additive.

## Data model

`collections` stores the identity and presentation metadata of a collection: an integer primary key, a required case-insensitively unique `name`, optional `description`, `color`, and `icon`, a `type`, plus audit timestamps. The type is constrained to `manual` or `smart`; this sprint only creates `manual` collections.

`collection_tracks` is a many-to-many junction table. Its composite primary key (`collection_id`, `track_id`) prevents duplicate membership. Both foreign keys cascade on deletion. The primary-key order serves lookup by collection and `ix_collection_tracks_track_id` supports reverse lookup by track.

## Flow and responsibilities

```text
CollectionPanel
  -> CollectionService
    -> CollectionRepository
      -> SQLite collections / collection_tracks / tracks
```

- `CollectionPanel` presents collections and invokes service operations only.
- `CollectionService` is the application boundary and guarantees UI-created collections are manual.
- `CollectionRepository` validates persistence-level invariants, maintains membership, and returns ORM entities.
- SQLite enforces foreign keys, the collection type check, and unique collection names.

`LibraryService` remains independent. Collection selection does not yet alter the library query; a subsequent integration can translate a selected collection into a library filter through `LibraryService`, without allowing the UI to query SQLite.

## Scalability

Collection lists are ordered by name. Membership is duplicate-proof and counting occurs in SQLite. The current `list_tracks()` is deliberately a simple manual-collection API. When collection views need the same behavior as the full library, they can adopt the existing paged `LibraryService` query contract rather than materializing every track. Smart Collections can reuse `collections` with `type = smart` and attach a separately versioned rule definition, leaving manual membership intact.
