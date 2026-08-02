# Music Analysis Foundation — v0.7.3

## Implemented contract

v0.7.3 introduces a provider-neutral, in-memory analysis contract only:

```text
Track-compatible object
        |
MusicAnalysisService
        |
AnalyzerProvider
        |
AnalysisResultDTO
```

`MusicAnalysisService` validates the track identifier, requested features, provider support, result ownership, provider provenance, and one-result-per-feature completeness. It has no repository, SQLite, UI, worker, or persistence dependency.

`AnalyzerProvider` declares `supported_features()` and `analyze(track, features)`. `MockAnalyzerProvider` returns only caller-configured deterministic values and performs no DSP, file access, waveform generation, BPM detection, or key detection.

## Supported feature contracts

| Feature | Value contract in this foundation | Future provider responsibility |
|---|---|---|
| BPM | numeric value | algorithm, units, confidence, range validation |
| KEY | provider string | normalized key convention and harmonic model |
| ENERGY | provider-defined numeric score | declared scale and feature provenance |
| DURATION | numeric seconds | source verification against file snapshot |
| WAVEFORM | opaque reference/value | asset format, resolution, cache lifecycle |

Each `AnalysisResultDTO` includes `track_id`, `feature_type`, `value`, provider name, provider version, confidence, and UTC creation time. Results are immutable DTOs and cannot update a `Track`.

## Versioning and provider policy

Provider name and version are mandatory. A future provider change must never silently replace an earlier result: the persistence design must retain enough provenance to compare algorithm, input snapshot, feature profile, confidence, and timestamp.

Provider errors are normalized as controlled analysis errors. A provider may support only a subset of features; the service rejects unsupported requests before invoking it.

## Future persistence — not implemented

No tables, models, migrations, cache files, or writes are added in this sprint. The approved persistence increment should use additive migrations from v0.6.1 and store analysis results separately from user-owned track fields.

The minimum future record requires:

- track reference and normalized input file snapshot;
- feature type and serialized value with unit/schema version;
- provider name, provider version, analysis profile, confidence, and created timestamp;
- result status and concise error information.

Waveform binary assets must remain outside `tracks`; SQLite should hold a metadata/reference record only. A failed re-analysis must not erase a prior valid result without an explicitly approved replacement policy.

## Deferred

- DSP libraries, machine-learning models, waveform generation, queues, workers, retries, and persistence.
- User overrides and a key-notation standard.
- Integration with Import Manager, DJ Intelligence, sync, or AI.
