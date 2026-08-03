# Epic 16 Sprint 2 - FFmpeg Audio Decoder

`FFmpegAudioDecoder` is an optional `AudioDecoderRegistry` adapter for MP3 and FLAC. The official format order is MP3, FLAC, AIFF/AIF, WAV. `FFmpegResolver` resolves an executable in this order: explicit `FFmpegDecoderConfigDTO`, existing process `PATH`, then `runtime/ffmpeg/ffmpeg.exe` included by a distribution. It never changes PATH, downloads, installs or bundles a binary at runtime. If no candidate succeeds, it returns typed `FFmpegProcessError` with `FFmpegAvailabilityDTO` explaining the absence.

`FFmpegCapabilityProbe` runs local `-version` and `-decoders` commands with timeout to record executable origin/version and verify MP3 and FLAC decoder support before audio decoding. A binary that is present but lacks a requested decoder remains unavailable for that format with a typed error.

The decoder first requests stream metadata from FFmpeg and then sends signed 16-bit PCM through stdout. It yields bounded normalized `AudioPCMBlockDTO` values, never uses temporary files, applies a configured timeout, observes cooperative cancellation between blocks, terminates/kills a process safely when necessary, and truncates/redacts stderr before exposing it. It is registered only when callers pass it to `AudioDecoderRegistry.default(ffmpeg_decoder=...)` or register it explicitly; WAV and AIFF remain available without FFmpeg.

## Windows installation and distribution

Install FFmpeg using the team's approved distribution channel, then either add its `bin` directory to the process `PATH`, configure the absolute path to `ffmpeg.exe` in `FFmpegDecoderConfigDTO(executable_path=...)`, or distribute an approved binary at `runtime/ffmpeg/ffmpeg.exe`. The resolver only reads these locations and never alters PATH. Distribution must follow `FFMPEG_DISTRIBUTION_AND_LICENSES.md`; DJPlus does not download binaries or make network calls. A missing executable leaves WAV/AIFF analysis operational and MP3/FLAC unavailable with a typed local error.

Process-simulated tests cover unavailable executables, content/extension detection, stdout blocks, AudioFileMusicAnalysisService integration, cancellation, timeout, process closure and stderr redaction. Optional real MP3/FLAC fixtures may be added only where FFmpeg is already installed; no test requires it.
