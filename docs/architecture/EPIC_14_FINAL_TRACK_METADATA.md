# Epic 14 - Final: Track Editor and Bulk Metadata

`TrackMetadataFacade` limits preview selection to `LibraryService` rows.
`TrackMetadataPreviewTool` is read-only; `TrackMetadataApplyTool` stores an
explicit pending proposal and rejects unknown confirmation IDs before invoking
the editor confirmation boundary. `TrackMetadataPanel` is a compact PySide6
form for comma-separated track IDs and title editing, preview and confirmed
apply; it deliberately does not redesign the main application or edit audio
tags. Durable `track_metadata_history` records applied/restored edits with old
and new JSON values, origin and status through migration `0005`.

`MainWindow` composes the panel beside existing navigation panels and reuses the
same `LibraryView.library_service`; construction is optional and does not alter
library, collection, playlist, import or assistant flows. Remaining risk: the
form intentionally supports only a minimal title patch and comma-separated IDs;
the full field set is available in the backend DTO/service but needs incremental
UI controls and production UX review.
