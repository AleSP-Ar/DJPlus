# Epic 12 - Sprint 1: Analysis Change Planning

`AnalysisChangePlanner` is a pure read-only decision layer. It compares two
immutable `AnalysisMetadataDTO` values for the same track across BPM, key and
energy, then returns a stable `AnalysisChangeSetDTO` ordered as BPM, key and
energy. Each `AnalysisChangeDTO` retains previous/proposed values, both
confidences, a classification and an explanation.

Classifications are `new` (a safe proposal), `unchanged`, `conflict`, and
`skipped` (no analyzable value). `never_overwrite` leaves differing existing
metadata as a conflict. `overwrite_lower_confidence` proposes a replacement
only when both confidences are known and the analyzed value is higher. `force`
proposes a differing value regardless of confidence. The preview is a
deterministic field-ordered text summary.

The planner does not receive a Repository, SQLite session, ORM model, UI or
write service. It persists nothing and executes no action; a later explicit
confirmation/write phase must consume the proposal if such behavior is approved.
