# Smart Collections Design — Sprint 5.7

## Manual versus smart collections

Manual collections use `collection_tracks` to store membership explicitly. Smart collections use the existing `collections` record with `type = smart` and derive membership at evaluation time; they do not write rows to `collection_tracks`. This preserves all existing manual collections without changing their behavior.

## Rule model and evaluation

`collection_rules` stores multiple rules for one smart collection: `id`, `collection_id`, `field`, `operator`, `value`, and `created_at`. Rules are evaluated with AND semantics. The first supported rules map directly to the existing `FilterEngine` contract:

- `bpm`: `>=`, `<=`, `=`.
- `rating`: `>=`, `<=`, `=`.
- `key`: `=`, `contains`.
- `favorite`: `=` with a boolean value.

The example `genre = Progressive` is intentionally not accepted yet because the current track schema has no genre column; it requires an approved schema migration before the rule engine can expose it.

```text
CollectionPanel
  -> SmartCollectionService
    -> CollectionRuleRepository -> collection_rules
    -> SmartRuleEngine -> FilterEngine -> FilterCriteria
    -> LibraryService -> TrackRepository -> SQLite tracks
```

`SmartRuleEngine` independently validates and translates rules. `SmartCollectionService` owns rule lifecycle and delegates track evaluation to `LibraryService`, preserving its SQLite ordering, counting, and incremental-load contract. The UI only creates a basic smart collection and renders its persisted rules.

## Updates and scalability

Results are dynamic: changing track metadata, favorite state, or a rule is reflected on the next evaluation; there is no materialized membership to synchronize. Rules are indexed by `collection_id`. Track evaluation remains in SQLite and returns the same first page plus `has_more` and total count used by the Virtual Library.

Future history-based Smart Collection rules can be added as explicit rule-engine mappings backed by indexed history queries. This sprint contains no IA, recommendations, musical analysis, Set Builder, plugin, or cloud behavior.
