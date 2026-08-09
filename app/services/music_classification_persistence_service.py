from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from app.database.unit_of_work import UnitOfWork
from app.repository.track_repository import TrackRepository
from app.services.metadata_candidate_proposal import MetadataProposalDTO
from app.services.track_metadata_editor import TrackMetadataDTO


class _SessionUnitAdapter:
    def __init__(self, session):
        self.session = session
        self.tracks = TrackRepository(session=session)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.session.close()
        return False


class MusicClassificationPersistenceError(ValueError):
    pass


@dataclass(frozen=True)
class ClassificationSelectionDTO:
    genre: bool = True
    secondary_genres: bool = True
    styles: bool = True
    label: bool = True


class MusicClassificationPersistenceService:
    def __init__(self, unit_of_work_factory=UnitOfWork, repository: TrackRepository | None = None):
        self._uow_factory = unit_of_work_factory
        self._repository = repository or TrackRepository()

    def apply_confirmed_proposal(
        self,
        proposal: MetadataProposalDTO,
        confirmation: bool,
        selection: ClassificationSelectionDTO | None = None,
    ) -> dict[str, Any]:
        if not isinstance(proposal, MetadataProposalDTO):
            raise TypeError("proposal must be MetadataProposalDTO")
        if not isinstance(confirmation, bool):
            raise TypeError("confirmation must be bool")
        if not confirmation:
            raise MusicClassificationPersistenceError("Confirmation required")

        selection = selection or ClassificationSelectionDTO()
        values: dict[str, Any] = {}
        if selection.genre and proposal.proposed_primary_genre_label:
            values["genre"] = proposal.proposed_primary_genre_label
            values["primary_genre_confidence"] = self._confidence_value(proposal.proposed_primary_confidence)
        if selection.secondary_genres:
            values["secondary_genres_json"] = self._serialize_secondary_genres(proposal.proposed_secondary_genres)
        if selection.styles:
            values["styles_json"] = self._serialize_styles(proposal.proposed_styles)
        if selection.label and proposal.proposed_label:
            values["label"] = proposal.proposed_label

        with self._open_unit() as uow:
            track = uow.tracks.get_by_id(proposal.current_metadata.track_id)
            if track is None:
                raise MusicClassificationPersistenceError("Track not found")

            previous = self._snapshot(track)
            uow.tracks.update_track_metadata(track, values, commit=False)
            uow.tracks.record_metadata_edit(
                proposal.current_metadata.track_id,
                tuple(values.keys()),
                previous,
                values,
                "classification",
                "applied",
                commit=False,
            )
            self._commit_unit(uow)

        return {"applied": True, "values": values, "track_id": proposal.current_metadata.track_id}

    def read_classification(self, track_id: int) -> dict[str, Any]:
        if not isinstance(track_id, int) or track_id <= 0:
            raise ValueError("track_id must be a positive integer")
        with self._open_unit() as uow:
            track = uow.tracks.get_by_id(track_id)
            if track is None:
                raise MusicClassificationPersistenceError("Track not found")
            return {
                "primary_genre": getattr(track, "genre", None),
                "primary_genre_confidence": getattr(track, "primary_genre_confidence", None),
                "secondary_genres": self._parse_json(getattr(track, "secondary_genres_json", None)),
                "styles": self._parse_json(getattr(track, "styles_json", None)),
            }

    def undo_last_classification(self, track_id: int) -> bool:
        if not isinstance(track_id, int) or track_id <= 0:
            raise ValueError("track_id must be a positive integer")
        with self._open_unit() as uow:
            entry = uow.tracks.latest_metadata_edit(track_id)
            track = uow.tracks.get_by_id(track_id)
            if entry is None or track is None:
                return False
            previous = json.loads(entry.previous_json)
            uow.tracks.update_track_metadata(track, previous, commit=False)
            uow.tracks.record_metadata_edit(
                track_id,
                tuple(previous.keys()),
                json.loads(entry.new_json),
                previous,
                entry.origin,
                "restored",
                commit=False,
            )
            self._commit_unit(uow)
        return True

    def _open_unit(self):
        unit = self._uow_factory()
        if hasattr(unit, "tracks") and hasattr(unit, "session"):
            return unit
        return _SessionUnitAdapter(unit)

    @staticmethod
    def _commit_unit(uow: Any) -> None:
        commit_method = getattr(uow, "commit", None)
        if callable(commit_method):
            commit_method()
            return
        session = getattr(uow, "session", None)
        if session is not None and hasattr(session, "commit"):
            session.commit()

    def _snapshot(self, track: Any) -> dict[str, Any]:
        return {
            field: getattr(track, field)
            for field in ("genre", "primary_genre_confidence", "secondary_genres_json", "styles_json", "label")
            if hasattr(track, field)
        }

    @staticmethod
    def _confidence_value(value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _serialize_secondary_genres(values: Iterable[tuple[str, Optional[str], float]]) -> str:
        return json.dumps(list(values))

    @staticmethod
    def _serialize_styles(values: Iterable[tuple[str, Optional[str], float]]) -> str:
        return json.dumps(list(values))

    @staticmethod
    def _parse_json(value: Any) -> Any:
        if value in (None, ""):
            return None
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return None
