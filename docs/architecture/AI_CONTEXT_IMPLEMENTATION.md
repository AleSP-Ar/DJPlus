# AI Assistant Context Foundation — v0.8.1

## Implemented boundary

v0.8.1 adds a bounded context assembly layer for a future assistant:

```text
Allowed ContextProvider instances
        |
AssistantContextBuilder
        |
AssistantContextDTO
        |
Future AssistantFacade integration
```

No model, network, database, repository, ORM object, filesystem access, session, persistence, or long-term memory is added.

## Context contract

`AssistantContextDTO` contains namespaced `available_data`, declared `data_sources`, a timezone-aware timestamp, and `context_version`. The builder accepts only `ContextProvider` instances and requires every provider to return this DTO.

`LibraryContextProvider` exposes only aggregate track count through an injected library service. `DJContextProvider` exposes that deterministic compatibility is available, the score range, and scoring metric names; it does not expose tracks, raw history, analysis files, or provider internals.

## Filtering and auditability

Each provider's data is namespaced by source. The builder drops sensitive keys such as path, filepath, file, SQL, SQLite, session, ORM, and repository. It preserves only recursively safe primitive values, lists/tuples, and dictionaries. Unknown objects are dropped.

Context is explicit and process-local: every build is a new timestamped DTO. There is no cache, conversation memory, database record, or hidden provider discovery.

## Future assistant connection

A future adapter may provide a built context to `AssistantFacade` as an allowlisted input only after deciding field-level redaction, size limits, remote-provider opt-in, audit logging, and retention policy. Context data must remain separate from tool instructions and untrusted metadata.

## Deferred and risks

- No model invocation, prompt construction, conversation state, or remote transmission.
- Current filtering is a baseline denylist plus primitive-value policy; a remote integration needs a reviewed allowlist per tool/provider.
- Aggregate counts can become stale immediately after creation; consumers must treat timestamp and context version as part of provenance.
