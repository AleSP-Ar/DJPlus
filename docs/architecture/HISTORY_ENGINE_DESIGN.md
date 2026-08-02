# History Engine Design — Sprint 5.6

## Model

Favorites are current track state: `tracks.is_favorite` is a persistent boolean managed by `FavoriteService`. History is intentionally separate and append-only: `track_history` contains an `id`, a cascading `track_id`, an `event_type`, and `created_at`.

The supported event types are `selected`, `played`, `added`, and `playlist_used`. A check constraint rejects any other stored event type. Indexes on (`track_id`, `created_at`) and (`event_type`, `created_at`) support per-track timelines and event-based aggregate queries.

## Event flow and responsibilities

```text
LibraryView selection -> HistoryService -> HistoryRepository -> track_history
Scanner track creation -> HistoryService -> HistoryRepository -> track_history
PlaylistService add_track -> HistoryService -> HistoryRepository -> track_history
Future player -> HistoryService.record_track_played() -> track_history
```

UI code only invokes `HistoryService`; it does not know the schema or SQLite. The repository validates track existence and event type, persists events, and exposes filtered chronological queries. Favorites follow the same UI-to-service-to-repository boundary.

## Relationships and future use

Each event belongs to exactly one track. Deleting a track cascades its history, preventing orphan activity records. Favorites and history deliberately do not alter `LibraryService` query state in this sprint.

Smart Collections can later express conditions such as recently played, frequently selected, never played, or favorite tracks by querying this data through a dedicated criteria layer. IA features can use event sequences as behavioral signals, but no recommendation, profiling, or model logic is added here.

## Scalability

History writes are narrow append operations and filtered reads are index-backed. The repository supports track and event filters plus limits; future analytical features should aggregate in SQLite rather than materializing full history in Qt.
