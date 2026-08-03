# Structured Logging and Diagnostics Design

## Purpose and boundary

`AppLoggingService` is the only component that configures DJPlus log handlers. It consumes the immutable `LoggingSettingsDTO` explicitly, owns one rotating handler for the `djplus` hierarchy and is composed by `app.main`. Services use named child loggers only; they never configure handlers.

The default production directory is `%APPDATA%\\DJPlus\\logs`. `SettingsService` injects that directory into `LoggingSettingsDTO`; tests inject a temporary directory and never write to the repository or real AppData.

## JSON Lines contract

Each line is one UTF-8 JSON object with `timestamp_utc` (ISO-8601 UTC), `level`, `logger`, `message`, `version`, `process_id` and `thread_name`. Optional fields are `event_name`, `component`, `operation_id`, `exception_type`, sanitized `context` and, for handled exceptions, a bounded traceback. Callers provide only small explicit context; complete DTOs, prompts, environment mappings and audio content are not serialised automatically.

Logs rotate by configured byte size (default 5 MiB) and retain the configured number of DJPlus files (default five). Reconfiguration closes the old handler before installing the new one. `flush()` and `shutdown()` are idempotent, and the standard logging lock handles concurrent writers.

## Privacy and diagnostics

`StructuredLogSanitizer` recursively redacts case-insensitive key variants containing API-key, token, authorization, password, secret, cookie, session or credential markers. File, library, music, configured-executable and executable-path fields are also redacted. It limits nesting, collection size and string length; unknown objects are represented only by their type and never through arbitrary `repr`.

`export_diagnostics()` creates an injected, atomic, bounded JSON support file and returns `DiagnosticsExportResultDTO` with SHA-256 and a manifest. It includes application/Python/platform versions, sanitized settings, sanitized FFmpeg diagnostics, minimal database status and bounded recent JSON log entries. It excludes database contents, the music library, full music paths, prompts, secrets, audio, `ffmpeg.exe` and binaries.

## Initial integration

The initial high-value events are application lifecycle (`djplus.ui`), settings load/save/recovery (`djplus.settings`), FFmpeg resolution (`djplus.ffmpeg`), analysis and worker failures (`djplus.analysis`), safe assistant operation/error metadata (`djplus.assistant`) and database migration lifecycle (`djplus.database`). Legacy `print()` in compatibility modules and benchmark scripts remains temporarily: it is not application logging and will be handled by the final backend cleanup.

`install_exception_hooks()` is explicit in `app.main`, preserves the previous `sys.excepthook` and `threading.excepthook`, records tracebacks and has a thread-local recursion guard. Importing logging modules never changes global exception hooks.

## Audit classification

| Area | Finding | Disposition |
| --- | --- | --- |
| `app/main.py` | Application lifecycle had no structured record. | Migrated. |
| Settings, FFmpeg, multi-format analysis, assistant worker | Boundary failures had no shared rotating sink. | Migrated at high-value points. |
| Database migrations | Canonical initialization point exists. | Migrated with event-only records. |
| `DiagnosticsService` / `DiagnosticsTool` | Read-only operational metrics, not a file logger. | Maintain; complement diagnostics export. |
| `app/library.py`, `app/scanner.py` | Legacy console compatibility paths. | Temporary compatibility; final backend cleanup candidate. |
| `tools/benchmarks/*` | Developer-facing command output. | Maintain outside application logging. |
| Provider transports and request DTOs | May carry prompt/credential context. | Do not log payloads; only safe boundary metadata. |

## Operational limits

The system is local only, has no external telemetry and does not guarantee durability beyond `flush()`. Cooperative workers can still finish a current unit after cancellation. Diagnostics are a bounded snapshot, not historical telemetry. A future Settings UI may change `LoggingSettingsDTO`; it must reconfigure the existing `AppLoggingService` rather than add handlers.
