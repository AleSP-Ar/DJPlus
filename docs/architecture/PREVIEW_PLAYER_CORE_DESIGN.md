# Preview Player Core Design

## Boundary

Epic 18 uses a backend-only preview player. `PreviewPlayerService` depends on `AudioPlaybackBackendProtocol`; no consumer receives `QMediaPlayer`, `QAudioOutput` or a Qt device object. `QtMultimediaPlaybackBackend` is the production adapter and `DeterministicPlaybackBackend` is the no-audio test double.

## State and operations

The immutable snapshot exposes `EMPTY`, `LOADING`, `READY`, `PLAYING`, `PAUSED`, `STOPPED`, `ENDED`, `ERROR` and `CLOSED`. The normal path is `EMPTY -> LOADING -> READY -> PLAYING`, then pause/resume, stop or end. Invalid operations return typed controlled errors; operations after `close()` raise `PlaybackClosedError`. Close is idempotent and clears callbacks before backend resources are released.

`PreviewTrackDTO` accepts only existing local MP3, FLAC, AIFF/AIF or WAV files in the public order MP3, FLAC, AIFF/AIF, WAV. The core never reads full media into memory or changes it. Seek is milliseconds, clamps negative values to zero and limits to known duration. Volume is private to the preview output and uses `0.0..1.0`; it survives a track change within the session.

## Qt and headless behaviour

The Qt backend creates `QMediaPlayer` and its own `QAudioOutput`, connects position/duration/state/error signals and disconnects them safely on close. It never creates a QApplication during import and never calls `play()` while loading. If `PySide6.QtMultimedia` is unavailable, factory composition returns a controlled degraded backend so the rest of DJPlus can remain available. Windows format support ultimately depends on Qt Multimedia and installed system codecs. FFmpeg remains analysis-only in this sprint.

Tests use the deterministic backend and temporary placeholder audio files, so the automatic suite emits no sound or accesses an audio device. A real audible test remains manual/conditional for a future operational validation.

`tools/manual_preview_player_check.py` is the explicit manual smoke check. It opens a file chooser for a local MP3, FLAC, AIFF/AIF or WAV and exposes the same controls; it is not imported by automatic tests.

## Devices, preferences and played history

Sprint 18.2 persists only `PreviewPlayerSettingsDTO` in Settings schema 3: private preview volume (`0.0..1.0`, default `.70`), serialized output-device ID and descriptive fallback text. The migration chain is `1 -> 2 -> 3`; a schema-2 file gets safe preview defaults. Persistence is explicit through `save_preferences()`; changing volume or output in the session never writes a timer-driven setting.

`AudioOutputDeviceDTO` contains an opaque serializable ID, description, default/availability flags and backend name. Qt derives IDs from the binary device identifier and does not expose `QAudioDevice` outside its adapter. Restoration attempts configured ID, then the stored description as a non-identity fallback, then the current default output, and finally remains degraded with a controlled reason. Switching an output preserves volume and does not reload or restart media. There is no global Windows audio-device change or device polling.

`PlaybackHistoryPortProtocol` is an explicit port. `HistoryPlaybackPortAdapter` delegates to existing `HistoryService.record_track_played`; it writes once only after the backend confirms `PLAYING` for each load session. Seeking, volume, pause/resume and repeated play do not duplicate the event; a new load resets the gate. A history failure is logged safely and never interrupts playback.

## Events and logging

Consumers can subscribe to track/state/position/duration/volume/end/error events without widget coupling. Event callbacks stop after close. Structured logs use an injected `djplus.preview` logger and contain only track ID where known, extension and a short one-way reference; no full path, title, artist, audio content or credentials are logged.

The factory accepts injectable backend, Settings and history port. If Qt multimedia or an output device is unavailable, composition returns a degraded no-audio service so the application can still open. MainWindow receives this service optionally, owns its safe close and hosts `PreviewPlayerBar`; the window itself contains no direct Qt Multimedia access.

## Current limits

Sprint 18.3 provides a small functional control bar only. There is still no waveform, artwork, hotkey, playlist automation, pitch, tempo, sync, mixing or crossfade. Device availability can change outside the application and is only reevaluated on explicit operations. Qt media callbacks must occur on the owning Qt thread; callers must not invoke the Qt backend from workers.
