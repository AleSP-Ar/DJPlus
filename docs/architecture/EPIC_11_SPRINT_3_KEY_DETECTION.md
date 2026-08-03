# Epic 11 - Sprint 3: Key Detection

`PCMKeyAnalyzer` is a deterministic local tonal-analysis component for PCM WAV.
It reads the audio in fixed blocks, downmixes mono or stereo frames, measures
the energy around equal-tempered notes, and combines those measurements into a
12-value chromatic profile ordered C through B.

`ChromaAnalysisDTO` exposes that normalized profile and its evidence.
`KeyAnalysisDTO` compares it against rotated major and minor templates and
returns a normalized root (`C`, `C#`, ... `B`), mode (`major` or `minor`), and
the resulting key string (for example, `C major`). Its confidence combines
template separation and chroma concentration.

Silence, audio below two seconds, an insufficiently distinctive chroma profile,
and cooperative cancellation deliberately do not publish a key: `key`, root,
and mode are `None` with an explanation. `MusicAnalysisService` attaches both
DTOs to its immutable result and copies the normalized key to
`AudioFeaturesDTO.key`.

The implementation is Python standard library only. It has no persistence,
network, UI, Repository, SQLite, or external dependency. It is intended as a
deterministic baseline; complex mixes, modulation, noisy recordings, and
enharmonic naming are not yet modeled. Synthetic WAV tests cover C-major and
A-minor triads, mono/stereo input, silence, short input, and cancellation.
