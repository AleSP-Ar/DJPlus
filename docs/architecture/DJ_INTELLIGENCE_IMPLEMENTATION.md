# DJ Intelligence Foundation — v0.7.4

## Implemented boundary

v0.7.4 adds a read-only deterministic compatibility layer:

```text
Track-compatible objects
        |
DJIntelligenceService
        |
ScoringEngine
        |
CompatibilityResultDTO
```

The service has no repository, SQLite, UI, import, analysis-provider, playlist, or write dependency. It reads only `id`, `bpm`, `key`, and `energy` attributes available on the caller-provided track-compatible objects.

## Scoring rules

The score is an integer from 0 to 100 and is normalized over the available inputs. Confidence expresses how much of the 100-point rule set was available.

| Signal | Weight | Deterministic rule |
|---|---:|---|
| BPM | 50 | Δ ≤ 2: full; Δ ≤ 6: 60%; otherwise 0 |
| Key | 30 | exact case-insensitive string match: full; otherwise 0 |
| Energy | 20 | Δ ≤ 10: full; Δ ≤ 30: 50%; otherwise 0 |

No harmonic-wheel theory, genre inference, tempo stretching, history weighting, or learned model is used. `history_context` is accepted only as a future extension point and does not change the score in this version.

Each result contains both track IDs, the score, immutable human-readable reasons, and confidence. Missing BPM, key, or energy produces a specific reason and reduces confidence rather than inventing data.

## Extensibility

Future rules must be pure, documented components with explicit weight and reasons. History can become a separately versioned scoring component only after a stable read API and privacy policy are approved. Music analysis DTOs may provide BPM/key/energy inputs later, but this service does not fetch, persist, or trigger analysis.

## Future AI integration

An AI assistant may consume `CompatibilityResultDTO` as an explanation-safe input, but may not replace its deterministic score silently. Any AI suggestion must distinguish deterministic compatibility reasons from generated narrative and remains draft-only until separately approved.

## Deferred and risks

- The current energy scale is assumed to be a comparable 0–100-style value supplied by callers; no analysis scale is yet approved.
- Exact key matching is intentionally conservative and not a harmonic compatibility model.
- Missing data can yield a normalized score based on limited signals; consumers must display confidence beside score.
- No persistence, recommendations, playlist changes, migrations, or automatic actions are implemented.
