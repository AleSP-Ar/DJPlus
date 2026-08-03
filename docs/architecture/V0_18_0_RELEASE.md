# DJPlus v0.18.0 - Multi-format Audio Analysis

## Scope

This release candidate introduces a bounded local decoding boundary. The public format order is fixed: MP3, FLAC, AIFF/AIF, WAV, with MP3 as the default format. `AudioDecoderProtocol` defines decoder contracts and `AudioDecoderRegistry` detects file content before its extension, exports supported formats and routes block-wise PCM reads to `WAVPCMDecoder`, `AIFFPCMDecoder` or optional `FFmpegAudioDecoder`.

WAV and AIFF/AIF use only the Python standard library. FFmpeg decodes MP3 and FLAC to normalized PCM over stdout, has bounded process timeouts, cooperative cancellation, safe process closure and typed errors. It creates no temporary audio files and uses no Python SDK, network connection, repository or SQLite access.

`FFmpegResolver` uses the mandatory priority configured executable, system PATH, bundled `runtime/ffmpeg/ffmpeg.exe`. A bundled executable is selected only after its SHA-256 matches `runtime/ffmpeg/CHECKSUM.sha256`. `FFmpegCapabilityProbe` obtains the local version and validates MP3 and FLAC decoder availability. `MultiFormatAudioAnalysisFacade` keeps the existing read-only `MusicAnalysisFacade` boundary while adding per-item format, decoder, analyzer version, duration, sample rate-derived analysis, peak, RMS, energy, BPM, key and confidence fields. Text export includes diagnostics and provenance. `MainWindow` composes the facade only when dependencies are available and never starts a scan automatically.

## Bundled runtime, source and license

The development runtime is Windows x64 `ffmpeg.exe` from BtbN/FFmpeg-Builds release `autobuild-2026-08-02-13-17`, artifact `ffmpeg-N-125907-ga7e72069f1-win64-lgpl.zip` (LGPL, non-shared). The verified artifact SHA-256 is `a74ad9068f12355118111a57111d548882c0a59f2520ad3e65188aa52a02ff9c`; the extracted executable SHA-256 is `499e983f598162cde152e8a411fb0f4baf51e7d59f7c0a9a8c65bf313017be4e`. The executable is 114,863,104 bytes (approximately 114.9 MB) and its artifact source, version, build configuration, LGPL v3 license and notice are retained beside it.

The executable exceeds GitHub's regular-Git limit and is intentionally excluded from repository history through `.gitignore`. Each developer who needs MP3/FLAC analysis must place the approved executable in `runtime/ffmpeg/ffmpeg.exe`; the versioned manifests fix its source, license, version and checksum. The final Windows installer must copy the binary into its payload only after validating `CHECKSUM.sha256`. DJPlus never downloads FFmpeg at runtime, never installs it globally and never changes PATH.

## Validation

The candidate passes the complete unittest suite with real bundled MP3/FLAC fixtures, corrupt MP3/FLAC handling, checksum-valid and checksum-invalid resolution, configured/PATH/bundled priority, and capability absence coverage. It also includes a deterministic multiformat benchmark and headless MainWindow smoke test. `compileall` and `git diff --check` are release gates.

## Limits

The included runtime supports Windows x64 only. Initial analysis remains CPU and I/O bound; cancellation is cooperative between PCM blocks and cannot forcibly interrupt an individual decode operation. BPM and key may be `None` when evidence is insufficient. Modulation, complex mixes and enharmonic normalization are outside this release.
