# Legacy Compatibility Policy

The sole recommended application entry point is `python -m app.main`. `app.gui`, `app.library` and `app.scanner` remain importable compatibility modules only. Their imports emit `DeprecationWarning` but do not start a UI, scan music or open a database until their explicit functions are called.

| Legacy surface | Canonical replacement | Policy |
| --- | --- | --- |
| `app.gui` / `launch_gui` | `app.main` / `MainWindow` | Preserve until external launcher use is audited. |
| `app.library` direct session helpers | `LibraryService` | Preserve function signatures; do not add features. |
| `app.scanner.scan_folder` | `ImportService` / `TrackImportService` | Preserve only as deprecated compatibility due to direct persistence risk. |
| provider `MusicAnalysisService` | `ProviderMusicAnalysisService` | Alias remains for published provider/mock callers. |
| local file `MusicAnalysisService` | `AudioFileMusicAnalysisService` | Alias remains for published local PCM callers; new canonical code uses explicit name. |
| assistant-facade tool aliases | `library_tools` + `ToolRegistry` | Keep aliases while compatibility tests remain. |

Warnings are emitted by explicit legacy module imports, not by normal canonical imports. Removal requires: documented replacement, an announced compatibility window, zero known external consumers, import/export coverage and a major-release approval. Historical release documents remain unchanged; current documentation must point to canonical APIs.
