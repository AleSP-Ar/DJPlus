# Preview Player Visual Integration

Sprint 18.3 adds a functional control bar, not the final DJPlus visual redesign. `PreviewPlayerBar` receives an already composed `PreviewPlayerService`; it never creates `QMediaPlayer`, `QAudioOutput`, settings, repositories or database sessions.

## User flow

`LibraryView` exposes an explicit **Cargar en reproductor** action for the active model row. It emits that existing row and `MainWindow` adapts its ID, filepath, title, artist and known duration to `PreviewTrackDTO`. Loading never calls play. Multiple selected rows still use only the active row and no queue is created.

The persistent bottom bar displays safe title/artist fallbacks, play/pause, stop, seek, current/duration time, volume, output selector, state and short controlled errors. Paths and technical device IDs are never displayed. Seek is applied on slider release; inbound service updates do not feed slider callbacks back into the service. Volume is session-local while dragging and preferences are saved only on slider release. Device changes select the opaque ID through the service and explicitly save preferences.

## Lifecycle and accessibility

Public service callbacks are forwarded through a Qt signal before widgets are updated, so a non-UI callback thread does not touch widgets directly. The bar unsubscribes on close and does not close the service; `MainWindow` remains the lifecycle owner. Buttons, sliders and selector provide tooltips, accessible names and tab order. With focus in the bar, Space toggles play/pause and Escape stops.

When no backend or output exists, the bar remains visible with **Sin salida de audio** and disabled play. Library browsing remains available. There is no polling timer, automatic playback, waveform, artwork, pitch/tempo, mixer, decks, cue/loop, sync or global audio-device mutation.

`tools/manual_preview_player_check.py` is intentionally manual: it opens a file chooser and the same bar for audible local validation. Automated tests use the deterministic backend and never emit audio.

## Release status

Epic 18 closes in v0.20.0. Automated validation covers the service, devices, Settings schema 3, played history, visual bar and headless MainWindow. Audible checks remain operator-controlled because codec and device availability are local environment concerns.
