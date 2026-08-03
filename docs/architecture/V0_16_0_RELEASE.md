# DJPlus v0.16.0 — Track Metadata Editing

Includes Backend Boundary Cleanup, TrackMetadataEditorService, individual and bulk patches, deterministic preview, ActionPipeline confirmation, durable history/restore, migration `0005_track_metadata_history`, facade, preview/apply tools and the optional TrackMetadataPanel in MainWindow.

The UI is deliberately minimal: it edits title for comma-separated IDs. Other backend-supported fields require future controls; selection is not yet synchronized with the library table and per-track progress/error display is basic. No audio tags are modified.

Release checks: full unittest suite, migrations 0004/0005, headless UI, compileall, diff check and file audit. Commit/tag require separate approval.
