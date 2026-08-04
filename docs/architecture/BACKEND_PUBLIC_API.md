# Backend Public API — v0.22.0

Entry point supported: `python -m app.main`.

Canonical boundaries: `SettingsService`, `AppLoggingService`, `BackupRestoreService`, `DatabaseMigrationCoordinator`, `LibraryService`, `PreviewPlayerService`, `GlobalRankingService`, `RecommendationFacade`, `SetBuilderFacade`, `ToolRegistry`, and `MainWindowDependencies` (optional composition seam).

Public repositories remain under `app.repository`; public immutable DTOs and factories are exported from `app.services`. `AudioFileMusicAnalysisService` is local PCM/DSP analysis; `ProviderMusicAnalysisService` is provider/mock analysis. Each module preserves its historical `MusicAnalysisService` alias.

Deprecated compatible modules: `app.gui`, `app.library`, `app.scanner`; they are importable and warn without startup side effects. Public aliases are frozen for this release. Future changes require a documented compatibility window, import/export coverage and a major-release approval.

`MainWindowDependencies` accepts already-composed widgets only for isolated composition. Default `MainWindow()` retains production construction. MainWindow owns closure of its LibraryView and optional PreviewPlayer once; callers must not duplicate ownership.
