# Music Analysis Engine Design — v0.7 Proposal

## Purpose

Provide an isolated, reproducible pipeline for extracting musical features without coupling analysis to import, Qt, a specific DSP library, or a vendor format.

## Boundaries

The analysis engine reads one track filepath and produces a typed result. It does not create tracks, edit user-owned data, modify playlists, or decide recommendations.

```text
Analysis request
      |
      v
AnalysisService -> AnalysisProvider -> AnalysisResult
      |                                  |
      +--- validation / persistence -----+
```

`AnalysisService` owns orchestration, retry policy, cancellation, status reporting, and future Unit of Work boundaries. `AnalysisProvider` is a replaceable adapter for a DSP implementation.

## Provider contract

```python
class AnalysisProvider:
    def analyze(self, filepath, requested_features) -> AnalysisResult:
        ...
```

`AnalysisResult` must be a data-only DTO with:

- `filepath` and stable track reference supplied by the service;
- provider name and algorithm version;
- analyzed-at timestamp and source snapshot (file size, modified time);
- requested and completed feature names;
- values, units, confidence, warnings, and user-safe error information.

The service rejects a result whose filepath or file snapshot no longer matches the request. This prevents stale analysis from silently attaching to a changed file.

## Feature groups

| Group | Proposed fields | Notes |
|---|---|---|
| Timing | BPM, beat positions, duration | BPM requires confidence and range validation; duration may verify import metadata |
| Harmony | musical key, key confidence | Store raw provider output plus normalized notation only after a chosen convention |
| Energy | energy score, loudness proxies, spectral features | A score must state its provider and scale; it is not a user rating |
| Waveform | derived asset reference, resolution, duration | Binary waveform data stays outside the main SQLite rows; SQLite holds metadata/reference only |
| Descriptors | danceability, onset density, timbre or embedding references | Optional, versioned, and provider-specific |

## Persistence proposal — not approved

No schema change is made by this design. Before implementation, select one of these options:

1. an append-only `track_analysis_runs` table plus a current-result pointer; or
2. one current-result table keyed by track and analysis profile.

Either option must record provenance, algorithm version, file snapshot, status, error summary, and timestamps. Waveform assets should use a cache directory keyed by track ID plus analysis version, with cleanup and invalidation rules. It is unsafe to store large waveform blobs in the library table by default.

Any result persistence must be additive, migrated from v0.6.1, and transactional per track. Failed analysis must preserve prior valid results until an explicit replacement policy is approved.

## Execution model

- A single analysis request processes one stable input and emits progress events equivalent in shape to import events.
- CPU/DSP work runs in a worker process or worker thread selected by the provider's thread-safety and GIL behavior; UI integration receives only signals/events.
- Cancellation is cooperative at provider-defined safe checkpoints.
- Requests are deduplicated by `(track, file snapshot, analysis profile, algorithm version)`, not content hash.
- Queue concurrency, resource limits, retry count, and waveform cache quota require benchmarks before approval.

## Quality and testing

- Fixture audio with expected approximate BPM/key ranges, not brittle exact values across providers.
- Snapshot mismatch, cancellation, provider crash, timeout, and stale-result tests.
- Benchmark wall time, CPU, memory, disk cache size, and database write time separately.
- Regression tests proving analysis does not change rating, favorites, collections, playlists, history, or imported metadata.

## Risks

- BPM and key can be ambiguous; confidence and provider provenance are mandatory.
- DSP packages may impose binary, licensing, or platform constraints.
- Waveforms and embeddings can dominate storage and invalidate frequently after file changes.
- Automatic overwrite of user corrections would be destructive; analysis values need separate ownership from user-facing edits.

## Deferred decisions

- First DSP provider and license.
- Key notation standard and harmonic compatibility model.
- Whether user overrides live beside or replace provider values.
- Waveform asset format, location, and cleanup policy.
