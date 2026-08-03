# v0.20.0 - Preview Player

## Scope

v0.20.0 closes Epic 18 with local preview playback. Publication is local only: one commit and an annotated tag, with no GitHub push, Git LFS or FFmpeg executable in Git.

## Delivered

- `AudioPlaybackBackendProtocol` separates the service from Qt Multimedia.
- `QtMultimediaPlaybackBackend` owns `QMediaPlayer` and its private `QAudioOutput`; `DeterministicPlaybackBackend` supports silent automated tests.
- `PreviewPlayerService` exposes immutable state snapshots for load, play/pause, stop, seek, volume, unload and idempotent close.
- Output devices use serializable `AudioOutputDeviceDTO`; restore falls back from configured ID to matching description, default output and controlled degraded state. Hot-plug is reevaluated only through explicit operations.
- Settings schema 3 stores private preview volume and optional serialized output preference. Migration is ordered `1 -> 2 -> 3` and writes remain explicit.
- `PlaybackHistoryPortProtocol` adapts the existing HistoryService. A `played` event is recorded once per loaded track only after backend-confirmed `PLAYING`; history failure cannot interrupt audio.
- Application composition injects settings, logger and history. `PreviewPlayerBar` is a persistent MainWindow control bar with explicit library loading, transport, seek, volume, output choice, state/errors and basic keyboard accessibility.

## Safety and degraded operation

The player never autoplays a selected row, mutates audio files, changes the Windows global output device, displays paths or logs title/artist/filepaths/device IDs. Without Qt Multimedia or an available output, DJPlus and library navigation remain usable with controlled unavailable status. The bar owns no multimedia object and unsubscribes safely; MainWindow owns service shutdown.

## Validation

Automated tests run headlessly against the deterministic backend and emit no audio. They cover the lifecycle states, format rejection, settings migration, device fallback, SQLite history, visual controls, callback teardown and degraded MainWindow. The manual helper is intentionally operator-driven and uses a file chooser for MP3, FLAC, AIFF/AIF or WAV.

## Limits and residual risks

Codec support and audible output depend on local Qt Multimedia/system capabilities. There is no device hot-plug watcher, waveform, artwork, pitch/tempo, cue/loop, mixer, dual decks, synchronization or final visual redesign. The next planned stage is Epic 19 — Global Ranking & DJ Integration; it is not part of this release.
