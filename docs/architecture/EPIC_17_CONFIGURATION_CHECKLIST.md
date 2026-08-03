# Épica 17 — Configuration, Logging & Diagnostics Checklist

Estado: cerrada en v0.19.0. Próximo hito: Épica 18 — Preview Player.

- [x] Commit/tag baseline v0.18.0 verified before implementation.
- [x] Typed immutable configuration with schema version 2.
- [x] Defaults, validation, atomic JSON write, injected test path and controlled corruption recovery.
- [x] Ordered migration 1 → 2 with backup and future-version rejection.
- [x] No secrets accepted or exported.
- [x] Optional FFmpeg, analysis and assistant adapters; no MainWindow coupling.
- [x] Focal tests for persistence, migration, safety, concurrency and FFmpeg policy.
- [ ] Settings UI.
- [x] `AppLoggingService` consumes `LoggingSettingsDTO` explicitly: local rotating JSONL, safe reconfiguration and idempotent lifecycle.
- [x] Redaction, explicit exception hooks, bounded atomic diagnostic export and high-value integration points.
- [x] Verified local ZIP backup: SQLite backup API, integrity check, strict manifest and SHA-256 inventory.
- [x] Safe listing/retention plus explicit restore plan, confirmation token and mandatory pre-action backup.
- [ ] Settings UI.
- [ ] Remote backup, scheduler and visual restore flow (explicitly out of scope).
- [ ] External telemetry (explicitly out of scope).
