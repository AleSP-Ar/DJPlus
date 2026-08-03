# Epic 11 - Final: Music Analysis Integration

`MusicAnalysisFacade` is the read-only boundary from `LibraryService` rows to
the local WAV analyzer. `MusicAnalysisBatchQueryDTO` selects up to 100 track
ids and bounds file analysis to one through four workers. No result is written
back to a track: metadata remains untouched and the batch result exists only in
memory.

Each `MusicAnalysisItemResultDTO` contains duration, peak, RMS, normalized
energy, BPM, key, tempo confidence, key confidence, and a typed per-file status.
Unreadable, unsupported, or corrupt files become `error` items instead of
failing the remaining batch. `MusicAnalysisBatchResultDTO.export_text()` creates
a local text report without secrets or persistence.

`MusicAnalysisWorker` runs a batch in a daemon thread, forwards `progress`,
`error`, and `finished` callbacks, provides cancellation, and closes by waiting
for the existing cooperative block boundaries. The facade also bounds its own
file-analysis executor. Cancellation is cooperative, so a file already inside a
PCM block may finish that block before its item is marked cancelled.

`MusicAnalysisBatchTool` is registered optionally by `ToolRegistry.default`
when a `MusicAnalysisFacade` is supplied. It only returns transient analysis and
the report text; it creates no actions. `AssistantPanel` renders batch rows if
the tool result is present.

The feature uses only application services and the Python standard library. It
does not access Repository, SQLite, UI state, network, external SDKs, or
generative AI. Integration tests exercise success, isolated file failure,
progress, worker lifecycle, registry dispatch, export, and a small concurrent
batch benchmark.
