"""Transactional library integration for one metadata-validated import item."""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.database.unit_of_work import UnitOfWork
from app.services.filepath_normalization import normalize_filepath


@dataclass(frozen=True)
class TrackImportResult:
    action: str
    track_id: int


class TrackImportService:
    """Create, skip, or refresh one track inside a single Unit of Work."""

    def __init__(self, unit_of_work_factory=UnitOfWork):
        self.unit_of_work_factory = unit_of_work_factory

    def process(self, item_id, metadata):
        with self.unit_of_work_factory() as unit_of_work:
            item = unit_of_work.imports.get_item(item_id)
            filepath = normalize_filepath(item.filepath)
            file_size, modified_at = self._file_snapshot(filepath)
            track = unit_of_work.tracks.get_by_filepath(filepath)
            if track is None:
                track = unit_of_work.tracks.create_from_import(
                    filepath,
                    metadata,
                    file_size,
                    modified_at,
                    commit=False,
                )
                unit_of_work.history.record_event(track.id, "added", commit=False)
                action = "created"
            elif self._is_unchanged(track, file_size, modified_at):
                action = "skipped"
            else:
                unit_of_work.tracks.update_from_import(
                    track,
                    metadata,
                    file_size,
                    modified_at,
                    commit=False,
                )
                action = "updated"
            unit_of_work.imports.update_item_status(
                item.id,
                "skipped" if action == "skipped" else "imported",
                commit=False,
            )
            return TrackImportResult(action=action, track_id=track.id)

    def _file_snapshot(self, filepath):
        stat_result = Path(filepath).stat()
        modified_at = datetime.fromtimestamp(stat_result.st_mtime, timezone.utc).replace(tzinfo=None)
        return stat_result.st_size, modified_at

    def _is_unchanged(self, track, file_size, modified_at):
        return (
            track.import_file_size == file_size
            and track.import_file_modified_at == modified_at
        )
