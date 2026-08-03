# Epic 11 - Sprint 1: Music Analysis Core

`audio_analysis_service.py` supplies a new file-analysis boundary distinct from the pre-existing track-feature provider service. It currently supports local WAV PCM through the Python standard library `wave` module and returns deterministic duration, sample rate, channel count and normalized peak.

`AudioFeaturesDTO` reserves BPM, key and energy fields for a future analyzer. The service stores nothing, handles missing/corrupt files with typed errors, and checks an injected cancellation token before and during frame reads. It has no UI, Repository, SQLite or external dependency.

## Sprint 2 — PCM feature extraction

`PCMFeatureExtractor` processes WAV PCM in fixed blocks, downmixes mono or stereo samples, calculates RMS and normalized energy, and estimates tempo from RMS-envelope peaks. BPM remains `None` when silence, short duration or peak regularity yields insufficient confidence. `EnergyAnalysisDTO` and `TempoAnalysisDTO` retain confidence and explanation. Key analysis is supplied by Sprint 3.
