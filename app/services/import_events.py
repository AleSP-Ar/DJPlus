"""Data-only progress events for import execution."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ImportEvent:
    event_type: str
    job_id: int | None = None
    item_id: int | None = None
    filepath: str | None = None
    progress: dict | None = None
    error_message: str | None = None
