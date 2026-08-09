"""Fill missing external classification fields after the user enables automation."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from app.database.unit_of_work import UnitOfWork

from .metadata_proposal_orchestrator import CombinedMetadataProposalService
from .settings_service import SettingsService
from .track_metadata_editor import TrackMetadataDTO


@dataclass(frozen=True)
class AutomaticMetadataResultDTO:
    inspected: int
    updated: int
    skipped_low_confidence: int
    errors: int


class AutomaticMetadataService:
    """Uses the existing providers but never overwrites a populated user field."""

    def __init__(self, settings_service, proposal_service=None, unit_of_work_factory=UnitOfWork, logger=None):
        if not isinstance(settings_service, SettingsService):
            raise TypeError("AutomaticMetadataService requiere SettingsService.")
        self._settings = settings_service
        self._proposal_service = proposal_service or CombinedMetadataProposalService()
        self._uow_factory = unit_of_work_factory
        self._logger = logger or logging.getLogger("djplus.automation")

    def run(self, limit=100):
        configuration = self._settings.get().library
        if not configuration.auto_external_metadata_enabled:
            return AutomaticMetadataResultDTO(0, 0, 0, 0)
        with self._uow_factory() as uow:
            tracks = tuple(uow.tracks.get_tracks(limit=limit))
        inspected = updated = skipped_low_confidence = errors = 0
        for track in tracks:
            if all(getattr(track, field, None) for field in ("genre", "label", "secondary_genres_json", "styles_json")):
                continue
            inspected += 1
            try:
                proposal = self._proposal_service.create_metadata_proposal(self._to_dto(track))
                values = self._empty_field_values(track, proposal, configuration.external_metadata_confidence_threshold)
                if not values:
                    skipped_low_confidence += 1
                    continue
                with self._uow_factory() as uow:
                    current = uow.tracks.get_by_id(track.id)
                    if current is None:
                        continue
                    values = self._empty_field_values(current, proposal, configuration.external_metadata_confidence_threshold)
                    if not values:
                        continue
                    previous = {field: getattr(current, field, None) for field in values}
                    uow.tracks.update_track_metadata(current, values, commit=False)
                    uow.tracks.record_metadata_edit(track.id, tuple(values), previous, values, "automatic_external", "applied", commit=False)
                updated += 1
            except Exception as error:
                errors += 1
                self._logger.warning("Automatic external metadata failed", exc_info=True, extra={"event_name": "automatic_metadata_failed", "component": "automation", "context": {"track_id": getattr(track, "id", None), "exception_type": type(error).__name__}})
        return AutomaticMetadataResultDTO(inspected, updated, skipped_low_confidence, errors)

    @staticmethod
    def _to_dto(track):
        return TrackMetadataDTO(track.id, track.title, track.artist, track.album, track.genre, track.rating or 0, track.bpm, track.key, track.energy or 0)

    @staticmethod
    def _empty_field_values(track, proposal, threshold):
        values = {}
        genre_is_confident = proposal.proposed_primary_confidence * 100 >= threshold
        label_is_confident = proposal.proposed_label_confidence * 100 >= threshold
        if genre_is_confident and not getattr(track, "genre", None) and proposal.proposed_primary_genre_label:
            values["genre"] = proposal.proposed_primary_genre_label
            values["primary_genre_confidence"] = proposal.proposed_primary_confidence
        if genre_is_confident and not getattr(track, "secondary_genres_json", None) and proposal.proposed_secondary_genres:
            values["secondary_genres_json"] = json.dumps(proposal.proposed_secondary_genres)
        if genre_is_confident and not getattr(track, "styles_json", None) and proposal.proposed_styles:
            values["styles_json"] = json.dumps(proposal.proposed_styles)
        if label_is_confident and not getattr(track, "label", None) and proposal.proposed_label:
            values["label"] = proposal.proposed_label
        return values
