"""Safely fill missing local audio-analysis fields after explicit opt-in."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from app.database.unit_of_work import UnitOfWork

from .audio_analysis_service import AudioAnalysisQueryDTO
from .settings_service import SettingsService


@dataclass(frozen=True)
class AutomaticAnalysisResultDTO:
    inspected: int
    updated: int
    errors: int


class AutomaticAnalysisService:
    """Runs local analysis; it does not alter audio files or overwrite metadata."""

    ANALYZER_VERSION = "automatic-local-v1"

    def __init__(self, settings_service, analysis_service=None, unit_of_work_factory=UnitOfWork, logger=None):
        if not isinstance(settings_service, SettingsService):
            raise TypeError("AutomaticAnalysisService requiere SettingsService.")
        self._settings = settings_service
        self._analysis = analysis_service or settings_service.create_audio_analysis_service()
        self._uow_factory = unit_of_work_factory
        self._logger = logger or logging.getLogger("djplus.automation")

    def run(self, limit=100):
        if not self._settings.get().analysis.auto_analysis_enabled:
            return AutomaticAnalysisResultDTO(0, 0, 0)
        with self._uow_factory() as uow:
            tracks = tuple(uow.tracks.get_tracks(limit=limit))
        inspected = updated = errors = 0
        for track in tracks:
            if all(getattr(track, field, None) is not None for field in ("bpm", "key", "energy")):
                continue
            inspected += 1
            try:
                result = self._analysis.analyze(AudioAnalysisQueryDTO(track.filepath))
                if result.status != "completed":
                    continue
                values = self._missing_values(track, result)
                if not values:
                    continue
                with self._uow_factory() as uow:
                    current = uow.tracks.get_by_id(track.id)
                    if current is None:
                        continue
                    values = self._missing_values(current, result)
                    if not values:
                        continue
                    previous = {field: getattr(current, field, None) for field in values}
                    confidences = {"bpm_confidence": result.tempo_analysis.confidence, "key_confidence": result.key_analysis.confidence, "energy_confidence": None}
                    provenance = {"analyzed_at": datetime.now(timezone.utc), "analyzer_version": self.ANALYZER_VERSION}
                    provenance.update({f"{field}_confidence": confidences[f"{field}_confidence"] for field in values})
                    uow.tracks.update_analysis_metadata(current, values, provenance, commit=False)
                    uow.tracks.record_metadata_edit(track.id, tuple(values), previous, values, "automatic_analysis", "applied", commit=False)
                updated += 1
            except Exception as error:
                errors += 1
                self._logger.warning("Automatic analysis failed", exc_info=True, extra={"event_name": "automatic_analysis_failed", "component": "automation", "context": {"track_id": getattr(track, "id", None), "exception_type": type(error).__name__}})
        return AutomaticAnalysisResultDTO(inspected, updated, errors)

    @staticmethod
    def _missing_values(track, result):
        values = {}
        if getattr(track, "bpm", None) is None and result.features.bpm is not None:
            values["bpm"] = result.features.bpm
        if getattr(track, "key", None) is None and result.features.key:
            values["key"] = result.features.key
        if getattr(track, "energy", None) is None and result.features.energy is not None:
            values["energy"] = result.features.energy
        return values
