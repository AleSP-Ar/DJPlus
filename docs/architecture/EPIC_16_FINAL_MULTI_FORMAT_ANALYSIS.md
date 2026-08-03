# Epic 16 Final - Multi-format Audio Analysis

## Read-only boundary

`MultiFormatAudioAnalysisFacade` is the batch boundary from `LibraryService` to the registered audio decoders and `AudioFileMusicAnalysisService`. It keeps the existing query, worker and `MusicAnalysisBatchTool` contracts compatible while returning immutable multiformat items with format, decoder, analyzer version, features and safe per-file errors. Its text export includes the official MP3, FLAC, AIFF/AIF, WAV order, registry diagnostics, FFmpeg availability/origin/version/capabilities and complete provenance for each result.

Native `WAVPCMDecoder` and `AIFFPCMDecoder` detect content before extension and stream normalized PCM blocks. `FFmpegAudioDecoder` is optional for MP3/FLAC: it resolves a configured executable or PATH, probes locally, produces PCM only over stdout, has a one-block queue, timeout, cooperative cancellation, safe process closure and truncated/redacted stderr. No decoder uses temporary files, network, downloads, automatic installation, Repository or SQLite.

## Availability and UI

The facade diagnostics identify registered decoders, extensions and typed FFmpeg availability. `FFmpegResolver` checks configuration, PATH, then `runtime/ffmpeg/ffmpeg.exe`; `FFmpegCapabilityProbe` confirms MP3/FLAC support before use. An explicit `FFmpegDecoderConfigDTO(executable_path=...)` supports Windows deployments where `ffmpeg.exe` is not in PATH. Documentation for installation and licensing responsibilities is in `EPIC_16_SPRINT_2_FFMPEG_DECODING.md` and `FFMPEG_DISTRIBUTION_AND_LICENSES.md`; DJPlus does not modify PATH or download FFmpeg.

`MusicAnalysisBatchTool` accepts the facade because it remains a compatible `MusicAnalysisFacade` subtype. `MainWindow` exposes `multi_format_audio_analysis_facade` only when composition succeeds; it does not scan automatically and still has no dedicated multiformat visual panel.

## Validation and limits

Tests cover WAV/AIFF end-to-end, content-over-extension detection, corrupt inputs, cancellation, mixed native/FFmpeg batches, unavailable FFmpeg, timeout/stderr simulation, textual provenance, tool integration, a 30-item mixed benchmark and a headless MainWindow smoke test. The bundled development runtime runs real MP3 and FLAC decode tests without a PATH installation, confirms the full item contract and rejects corrupt MP3/FLAC files. Bundled resolution verifies `CHECKSUM.sha256`; an invalid checksum is rejected before process creation.

PCM analysis remains mono/stereo and block-cooperative. FFmpeg metadata parsing relies on its standard banner; unexpected output returns a typed error. Initial scans remain I/O-bound, and features plus key analysis make bounded separate passes over the source.
