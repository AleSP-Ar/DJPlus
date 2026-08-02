# Playlist Engine Design — Sprint 5.5

## Collection versus Playlist

A Collection is an unordered manual grouping used to classify tracks. A Playlist is an ordered, intentional sequence used for playback planning. Collections model membership; playlists model both membership and sequence. They therefore have separate tables, repositories, services, and UI panels.

## Data model and ordering

`playlists` stores a case-insensitively unique `name`, optional `description`, and creation/update timestamps.

`playlist_tracks` stores one row per playlist-track relationship:

- `id` identifies the entry.
- `playlist_id` and `track_id` are cascading foreign keys.
- `position` is a zero-based, manual order.
- `added_at` records when the entry was inserted.

Two unique constraints enforce the engine invariants: (`playlist_id`, `track_id`) prevents duplicates and (`playlist_id`, `position`) prevents two entries sharing an order slot. Positions are compacted after removal and reordered atomically by temporarily shifting them before their final assignment. The reverse index `ix_playlist_tracks_track_id` supports future track-to-playlist lookup.

## Responsibilities

```text
PlaylistPanel
  -> PlaylistService
    -> PlaylistRepository
      -> SQLite playlists / playlist_tracks / tracks
```

- `PlaylistPanel` provides basic create, rename, delete, and select interactions.
- `PlaylistService` is the only API exposed to UI code.
- `PlaylistRepository` validates names and membership, performs ordered persistence, and maintains contiguous positions.
- SQLite enforces relationship, uniqueness, and non-negative-position constraints.

This sprint deliberately excludes drag and drop, playback, Set Builder, and Smart Collections.

## Future Set Builder integration

Set Builder can use `PlaylistService.list_tracks()` as the ordered source of a planned set and `move_track()` as the persistence operation for its rearrangements. Any future richer playlist metadata or set transitions can extend the playlist aggregate without coupling it to Collections or to the library UI.

## Scalability

Playlists are listed by name and entries are queried by indexed playlist relation and position. Reordering writes only the selected playlist and does not affect the global library. Very large playlists can later expose paged ordered entries through a dedicated service contract; that is not necessary for this basic administration panel.
