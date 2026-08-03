"""Confirmed, reversible application of analysis plans through UnitOfWork only."""

from dataclasses import dataclass
from datetime import datetime, timezone

from app.database.unit_of_work import UnitOfWork
from .action_pipeline import ActionPipeline, ActionType
from .analysis_change_planner import AnalysisChangeSetDTO
from .confirmation_manager import ConfirmationManager, ConfirmationRequestDTO


class AnalysisPersistenceError(ValueError):
    pass


@dataclass(frozen=True)
class AnalysisMetadataBackupDTO:
    track_id: int
    previous_values: tuple[tuple[str, object], ...]
    analyzer_version: str
    applied_at_utc: datetime
    confidences: tuple[tuple[str, float | None], ...]
    previous_provenance: tuple[tuple[str, object], ...]


@dataclass(frozen=True)
class AnalysisApplyResultDTO:
    track_id: int
    success: bool
    applied_fields: tuple[str, ...]
    backup: AnalysisMetadataBackupDTO | None
    message: str
    error: str | None = None


@dataclass(frozen=True)
class AnalysisRestoreResultDTO:
    track_id: int
    success: bool
    restored_fields: tuple[str, ...]
    message: str
    error: str | None = None


class AnalysisPersistenceService:
    """Requires an ActionPipeline confirmation; owns no SQL/session directly."""

    ANALYZER_VERSION = "pcm-local-v1"

    def __init__(self, action_pipeline, confirmation_manager, unit_of_work_factory=UnitOfWork):
        if not isinstance(action_pipeline, ActionPipeline) or not isinstance(confirmation_manager, ConfirmationManager):
            raise TypeError("AnalysisPersistenceService requiere ActionPipeline y ConfirmationManager.")
        self._pipeline, self._confirmation_manager, self._uow_factory = action_pipeline, confirmation_manager, unit_of_work_factory
        self._backups = {}

    def propose(self, changeset, authorized_conflict_fields=()):
        self._validate_changeset(changeset)
        fields = tuple(authorized_conflict_fields)
        conflicts = {change.field for change in changeset.changes if change.classification == "conflict"}
        if not set(fields).issubset(conflicts):
            raise AnalysisPersistenceError("Solo pueden autorizarse conflictos presentes.")
        return self._pipeline.create_proposal(ActionType.CUSTOM, "Aplicar analisis musical", changeset.preview, {
            "kind": "analysis_metadata", "track_id": changeset.track_id, "authorized_conflicts": fields,
        })

    def apply(self, changeset, proposal, confirmation_request):
        self._validate_changeset(changeset)
        if not isinstance(confirmation_request, ConfirmationRequestDTO) or confirmation_request.action_id != proposal.action_id:
            raise AnalysisPersistenceError("La confirmacion debe corresponder a la propuesta.")
        valid = self._pipeline.revalidate_registered_proposal(proposal)
        if not valid.valid:
            return AnalysisApplyResultDTO(changeset.track_id, False, (), None, "La propuesta no es valida.", " ".join(valid.errors))
        confirmation = self._confirmation_manager.request_confirmation(confirmation_request)
        if not confirmation.allowed:
            return AnalysisApplyResultDTO(changeset.track_id, False, (), None, "La escritura no fue confirmada.", confirmation.reason)
        payload = proposal.payload
        if payload.get("kind") != "analysis_metadata" or payload.get("track_id") != changeset.track_id:
            return AnalysisApplyResultDTO(changeset.track_id, False, (), None, "La propuesta no corresponde al plan.", "payload invalido")
        authorized = set(payload.get("authorized_conflicts", ()))
        selected = tuple(change for change in changeset.changes if change.classification == "new" or (change.classification == "conflict" and change.field in authorized))
        if not selected:
            return AnalysisApplyResultDTO(changeset.track_id, True, (), None, "No hay cambios autorizados para aplicar.")
        previous = tuple((change.field, change.previous_value) for change in selected)
        confidences = tuple((change.field, change.proposed_confidence) for change in selected)
        applied_at = datetime.now(timezone.utc)
        try:
            with self._uow_factory() as uow:
                track = uow.tracks.get_by_id(changeset.track_id)
                if track is None:
                    raise AnalysisPersistenceError("La pista no existe.")
                previous_provenance = tuple((field, getattr(track, field, None)) for field in ("analyzed_at", "analyzer_version", "bpm_confidence", "key_confidence", "energy_confidence"))
                backup = AnalysisMetadataBackupDTO(changeset.track_id, previous, self.ANALYZER_VERSION, applied_at, confidences, previous_provenance)
                provenance = {"analyzed_at": applied_at, "analyzer_version": self.ANALYZER_VERSION}
                provenance.update({f"{change.field}_confidence": change.proposed_confidence for change in selected})
                uow.tracks.update_analysis_metadata(track, dict((change.field, change.proposed_value) for change in selected), provenance, commit=False)
            self._backups[changeset.track_id] = backup
            return AnalysisApplyResultDTO(changeset.track_id, True, tuple(change.field for change in selected), backup, "Cambios de analisis aplicados atomicamente.")
        except Exception as error:
            return AnalysisApplyResultDTO(changeset.track_id, False, (), None, "No se pudieron aplicar cambios.", str(error))

    def apply_many(self, entries):
        return tuple(self.apply(changeset, proposal, request) for changeset, proposal, request in entries)

    def restore(self, track_id):
        backup = self._backups.get(track_id)
        if backup is None:
            return AnalysisRestoreResultDTO(track_id, False, (), "No existe respaldo transitorio.", "respaldo no encontrado")
        try:
            with self._uow_factory() as uow:
                track = uow.tracks.get_by_id(track_id)
                if track is None:
                    raise AnalysisPersistenceError("La pista no existe.")
                uow.tracks.update_analysis_metadata(track, dict(backup.previous_values), dict(backup.previous_provenance), commit=False)
            return AnalysisRestoreResultDTO(track_id, True, tuple(field for field, _ in backup.previous_values), "Valores anteriores restaurados.")
        except Exception as error:
            return AnalysisRestoreResultDTO(track_id, False, (), "No se pudieron restaurar valores.", str(error))

    @staticmethod
    def _validate_changeset(changeset):
        if not isinstance(changeset, AnalysisChangeSetDTO):
            raise TypeError("Se requiere AnalysisChangeSetDTO aprobado.")
