# Backend Freeze Checklist

## A. Safe removal

- [ ] Verify external consumers of `app.gui`, `app.library` and `app.scanner` before removal.
- [ ] Verify direct and transitive use of `python-dotenv` and `typing_extensions`.
- [ ] Remove only generated artifacts with a reproducible source.

## B. API consolidation

- [x] Publish explicit provider-analysis and file-analysis names; retain both historical `MusicAnalysisService` aliases.
- [ ] Map assistant-facade tool aliases to `library_tools` with a release-window deprecation plan.
- [ ] Review public DTO exports before changing `app.services.__all__`.

## C. Dependency cleanup

- [ ] Compare declared dependencies to imports and packaging requirements.
- [ ] Keep PySide6, SQLAlchemy and mutagen until supported paths are independently removed.
- [ ] Keep FFmpeg optional, local and out of Git.

## D. Migrations and compatibility

- [x] Test each published database origin through 0005 without editing historical migrations.
- [ ] Preserve nullable provenance fields and durable metadata history compatibility.
- [ ] Exercise Settings 1→2→3 migration from fixture snapshots.

## E. Documentation

- [ ] Establish a current-architecture index and mark releases/sprints historical.
- [ ] Normalize stale current-version headers without deleting release records.
- [ ] Keep deferred integrations explicitly backlog-only.

## F. Final hardening

- [ ] Audit session ownership and explicit closure in all repositories/workers.
- [x] Reject future, unknown and inconsistent migration history without silent repair.
- [x] Require verified pre-action backup before startup migration of an existing historical database.
- [x] Migrate historical restore only on a second temporary copy before atomic replacement.
- [x] Audit canonical and legacy import side effects in an isolated subprocess.
- [ ] Audit logging handlers, Qt lifecycle, subprocess closure, temporary files and secret redaction.
- [x] Complete an isolated clean-install `MainWindow` lifecycle through optional widget composition, without changing visual composition.
- [ ] Keep full headless, real FFmpeg, backup/restore and migration validation green.

## G. Frozen-backend release

- [ ] Confirm only approved cleanup changes in worktree.
- [ ] Run full suite, compileall, benchmarks, migration matrix and architecture audit.
- [ ] Create a dedicated frozen-backend release only after compatibility review.
