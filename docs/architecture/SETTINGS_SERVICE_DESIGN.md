# Settings Service Design — Épica 17, Sprint 17.1

## Canonical boundary

`app.services.settings_service.SettingsService` is the single persistent-preferences API. `app.config` is only a small compatibility façade; it does not define a second settings model. The default Windows location is `%APPDATA%\DJPlus\config.json`. Callers and tests may inject `config_path` (or `appdata_path`), so the repository and a real user profile are never written during tests.

`AppSettingsDTO` is frozen and has `schema_version = 2`. Its sections are:

- General: locale, future theme and dangerous-action confirmation.
- Library: normalized music paths, scan-on-start, supported extensions, page size and result limit.
- Analysis: bounded concurrency, PCM block frames, timeout, automatic-analysis preference and the fixed MP3 → FLAC → AIFF/AIF → WAV priority.
- FFmpeg: optional configured executable, PATH/bundled policy, detection timeout and mandatory bundled-checksum validation.
- Assistant: selected provider, model, timeout, tool limit and non-secret options.
- Logging: level, future directory, max bytes, retention and redaction preference.
- Backup: future directory, retention, automatic-backup preference and checksum preference.

No API key, password, token, secret or credential field is accepted in normal settings. `export_sanitized()` recursively redacts sensitive-shaped names as defense in depth.

## Existing configuration audit

| Current value | Prior owner / consumer | Sprint 17.1 disposition |
|---|---|---|
| `app.config` | Compatibility import only | Becomes façade to the canonical service. |
| Scanner extensions | `ScannerService.DEFAULT_AUDIO_EXTENSIONS` | Duplicated concept with library formats; retained for compatibility, settings are prepared for explicit injection. |
| PCM block size | `PCMFeatureExtractor` and `PCMKeyAnalyzer` (`1024`) | Settings can construct a compatible analysis service with configured frames. |
| Analysis concurrency | `MusicAnalysisBatchQueryDTO` | Settings expose a bounded hardening adapter; no implicit behavior change. |
| FFmpeg path / timeout | `FFmpegDecoderConfigDTO` | Settings produces the DTO and an opt-in resolver. |
| FFmpeg PATH/bundled | `FFmpegResolver` hard-coded defaults | Resolver now accepts optional policy flags; defaults preserve all existing callers. |
| Assistant model / timeout | `LocalAssistantConfigDTO`, `ProviderConfigDTO` | Settings exposes non-secret request configuration only. |
| Logging and backup paths | No persistent operational service | Preferences are modeled but have no side effects yet. |
| Music roots | Scanner/import call arguments | Normalized and persisted for future composition; no automatic scans. |

## Persistence and migration

`load()` returns safe defaults for a missing file. JSON corruption is backed up as `config.json.corrupt.backup` and recovers to defaults unless strict loading is requested. Unknown or invalid fields raise typed validation errors. `save()` validates first, creates only the configured parent directory and writes a temporary file in that directory before atomic replacement.

Schema 1 is migrated to schema 2 through one ordered in-service migration. The original file is copied to `config.json.v1.backup`, then the migrated result is validated and atomically saved. A future schema version is rejected without mutation.

## Integration and limits

`ffmpeg_decoder_config()` and `create_ffmpeg_resolver()` preserve configured → PATH → bundled priority, the local checksum check and existing defaults. `analysis_hardening_config()` and `create_audio_analysis_service()` expose configured limits without changing existing services automatically. `assistant_provider_config()` exposes model/timeout only. No component reads settings implicitly, and no UI panel is part of this sprint.
