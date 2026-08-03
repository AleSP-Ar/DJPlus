# Epic 13 - Backend Boundary Cleanup

## Canonical public boundaries

- File DSP uses `AudioFileMusicAnalysisService` from `app.services`; the former
  provider/mock contract is now named `ProviderMusicAnalysisService`. Its
  `MusicAnalysisService` name remains a compatibility alias.
- Tool registration is canonical in `library_tools.py` plus `ToolRegistry`.
  The similarly named tools in `assistant_facade.py` are compatibility aliases
  for its older facade tests and must not be used for new registry work.
- `LibraryService`, `ImportService` and `app.main` are the current application
  paths for library queries, import and UI startup.

## Legacy isolation

`app.gui`, `app.library` and `app.scanner` have no internal consumers other
than their legacy chain. They remain import-compatible and emit a
`DeprecationWarning`; no deletion was performed because external consumers
cannot be proven absent. `app.config` was empty and now documents that validated
service DTOs are the only active configuration boundary.

## Removed code

None. The audit found no safely removable module with proof that external
consumers do not exist. This sprint intentionally isolates rather than deletes.

## Roadmap

The historical roadmap now points to the functional inventory for forward v1.0
prioritization. Milestones mark v0.15 as published.
