# Epic 11 - Sprint 2: Audio Feature Extraction

`PCMFeatureExtractor` is the local, deterministic extraction boundary used by
`MusicAnalysisService` for WAV PCM files. It reads fixed-size frame blocks,
checks the optional cancellation token before every block, and does not retain
audio or analysis output.

## Extracted features

- `EnergyAnalysisDTO` reports RMS, normalized energy (0-100), confidence and
  its calculation reason. RMS is calculated over downmixed mono values; stereo
  channels are averaged only for energy and envelope analysis. Peak remains the
  maximum absolute value observed on any original PCM channel.
- `TempoAnalysisDTO` derives an RMS envelope per block, identifies separated
  envelope peaks, and estimates BPM from their median interval. It exposes BPM
  only at sufficient confidence; short audio, silence, irregular peaks, and an
  insufficient number of peaks produce an explanatory `None` BPM instead.

## Scope and limits

The implementation uses only the Python standard library and supports PCM WAV
sample widths from 8 to 32 bits, in mono or stereo. Tonal/key analysis is not
implemented. The extractor has no persistence, UI, repository, SQLite, network
or external dependency. Cooperative cancellation depends on the caller's token
being checked between blocks, so a single oversized block is not pre-empted.

Synthetic WAV tests cover stereo pulse tempo, RMS/energy, silence, short audio,
invalid input, corrupt files, and mid-stream cancellation.
