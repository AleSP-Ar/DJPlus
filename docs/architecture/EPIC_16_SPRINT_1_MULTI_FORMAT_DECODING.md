# Epic 16 Sprint 1 - Multi-format Audio Decoding Core

`audio_decoder.py` introduces a read-only, standard-library PCM boundary. `AudioFormatDTO`, `DecodedAudioInfoDTO` and `AudioPCMBlockDTO` describe immutable container metadata and normalized interleaved samples. Blocks are bounded by requested frame count, so decoders do not materialize an entire audio file in memory.

`AudioDecoderRegistry` detects WAV and AIFF/AIF by content signature first and extension second. `WAVPCMDecoder` handles RIFF/WAVE PCM with little-endian samples; `AIFFPCMDecoder` handles uncompressed FORM/AIFF PCM with big-endian samples. Both support 8/16/24/32-bit PCM, mono or stereo, arbitrary positive sample rates, typed corruption/incompatibility errors, and cooperative cancellation between blocks.

The local `AudioFileMusicAnalysisService` now creates `WaveAudioAnalyzer` with the registry. Features and tonal analysis consume normalized decoder blocks in bounded passes, keeping the prior read-only behavior and WAV compatibility while adding AIFF/AIF. There is no persistence, UI, Repository, SQLite, network, MP3, FLAC or external dependency.

Synthetic tests cover content-versus-extension detection, decoder uniqueness, WAV and AIFF layouts, mono/stereo, sample rates, normalized blocks, injected registries, corrupt and unsupported files, cooperative cancellation, and the existing analysis/facade behavior.
