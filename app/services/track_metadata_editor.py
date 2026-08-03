"""Confirmed, reversible metadata edits through UnitOfWork, never audio files."""
from dataclasses import dataclass
from datetime import datetime, timezone
import json

from app.database.unit_of_work import UnitOfWork
from .action_pipeline import ActionPipeline, ActionType
from .confirmation_manager import ConfirmationManager, ConfirmationRequestDTO

FIELDS = ("title", "artist", "album", "genre", "rating", "bpm", "key", "energy")

class TrackMetadataEditError(ValueError): pass

@dataclass(frozen=True)
class TrackMetadataDTO:
    track_id: int; title: str; artist: str; album: str | None; genre: str | None; rating: int; bpm: float | None; key: str | None; energy: int

@dataclass(frozen=True)
class TrackMetadataPatchDTO:
    values: tuple[tuple[str, object], ...]
    def __post_init__(self):
        if not isinstance(self.values, tuple) or not self.values or len({key for key, _ in self.values}) != len(self.values): raise TrackMetadataEditError("El patch debe contener campos unicos.")
        for field, value in self.values:
            if field not in FIELDS: raise TrackMetadataEditError("Campo de metadata no permitido.")
            if field in {"title", "artist"} and (not isinstance(value, str) or not value.strip()): raise TrackMetadataEditError("title y artist no pueden vaciarse.")
            if field in {"album", "genre", "key"} and value is not None and not isinstance(value, str): raise TrackMetadataEditError("El campo textual debe ser texto o nulo.")
            if field == "rating" and (not isinstance(value, int) or not 0 <= value <= 5): raise TrackMetadataEditError("rating debe estar entre 0 y 5.")
            if field == "bpm" and value is not None and (not isinstance(value, (int,float)) or value <= 0): raise TrackMetadataEditError("bpm debe ser positivo o nulo.")
            if field == "energy" and (not isinstance(value, int) or not 0 <= value <= 100): raise TrackMetadataEditError("energy debe estar entre 0 y 100.")
    @classmethod
    def from_mapping(cls, values): return cls(tuple((key, value.strip() if isinstance(value, str) else value) for key, value in dict(values).items()))

@dataclass(frozen=True)
class TrackMetadataChangeDTO:
    field: str; previous_value: object; proposed_value: object; classification: str; explanation: str

@dataclass(frozen=True)
class BulkMetadataEditQueryDTO:
    track_ids: tuple[int, ...]; patch: TrackMetadataPatchDTO
    def __post_init__(self):
        if not self.track_ids or not all(isinstance(item,int) and item>0 for item in self.track_ids) or len(set(self.track_ids)) != len(self.track_ids): raise TrackMetadataEditError("track_ids debe contener ids positivos unicos.")
        if not isinstance(self.patch, TrackMetadataPatchDTO): raise TrackMetadataEditError("patch invalido.")

@dataclass(frozen=True)
class BulkMetadataEditResultDTO:
    query: BulkMetadataEditQueryDTO; changes: tuple[tuple[int, tuple[TrackMetadataChangeDTO,...]], ...]; success: bool; preview: str; backups: tuple[tuple[int, tuple[tuple[str,object],...]], ...] = (); error: str | None = None

class TrackMetadataEditorService:
    def __init__(self, action_pipeline, confirmation_manager, unit_of_work_factory=UnitOfWork):
        if not isinstance(action_pipeline, ActionPipeline) or not isinstance(confirmation_manager, ConfirmationManager): raise TypeError("Se requiere ActionPipeline y ConfirmationManager.")
        self._pipeline,self._confirmation,self._uow_factory=action_pipeline,confirmation_manager,unit_of_work_factory; self._backups={}
    def preview(self, query):
        if not isinstance(query,BulkMetadataEditQueryDTO): raise TypeError("query invalida.")
        groups=[]
        for track_id in query.track_ids:
            try:
                with self._uow_factory() as uow:
                    track=uow.tracks.get_by_id(track_id)
                    if track is None: raise TrackMetadataEditError("Pista inexistente.")
                    changes=tuple(TrackMetadataChangeDTO(field,getattr(track,field),value,"unchanged" if getattr(track,field)==value else ("cleared" if value is None else "new"),"Sin cambio." if getattr(track,field)==value else "Valor vaciado." if value is None else "Valor nuevo propuesto.") for field,value in query.patch.values)
                groups.append((track_id,changes))
            except Exception as error: groups.append((track_id,(TrackMetadataChangeDTO("title",None,None,"error",str(error)),)))
        preview=" | ".join(f"{track_id}:"+",".join(f"{c.field}={c.classification}" for c in changes) for track_id,changes in groups)
        return BulkMetadataEditResultDTO(query,tuple(groups),True,preview)
    def propose(self,result):
        if not isinstance(result,BulkMetadataEditResultDTO): raise TypeError("result invalido.")
        return self._pipeline.create_proposal(ActionType.CUSTOM,"Editar metadata de pistas",result.preview,{"kind":"track_metadata","track_ids":result.query.track_ids})
    def apply(self,result,proposal,request):
        if not isinstance(request,ConfirmationRequestDTO) or request.action_id!=proposal.action_id: raise TrackMetadataEditError("Confirmacion no corresponde.")
        if not self._pipeline.revalidate_registered_proposal(proposal).valid: return BulkMetadataEditResultDTO(result.query,result.changes,False,result.preview,error="Propuesta invalida.")
        if not self._confirmation.request_confirmation(request).allowed: return BulkMetadataEditResultDTO(result.query,result.changes,False,result.preview,error="Confirmacion rechazada.")
        backups=[]
        for track_id,changes in result.changes:
            values={c.field:c.proposed_value for c in changes if c.classification in {"new","cleared"}}
            if not values: continue
            try:
                with self._uow_factory() as uow:
                    track=uow.tracks.get_by_id(track_id)
                    if track is None: raise TrackMetadataEditError("Pista inexistente.")
                    backup=tuple((field,getattr(track,field)) for field in values); uow.tracks.update_track_metadata(track,values,commit=False)
                    if callable(getattr(uow.tracks,"record_metadata_edit",None)): uow.tracks.record_metadata_edit(track_id, tuple(values), dict(backup), values, "manual", "applied", commit=False)
                self._backups[track_id]=backup; backups.append((track_id,backup))
            except Exception: pass
        return BulkMetadataEditResultDTO(result.query,result.changes,True,result.preview,tuple(backups))
    def restore(self,track_id):
        backup=self._backups.get(track_id)
        if backup is None: return False
        with self._uow_factory() as uow:
            track=uow.tracks.get_by_id(track_id)
            if track is None: return False
            uow.tracks.update_track_metadata(track,dict(backup),commit=False)
        return True

    def restore_last_durable(self, track_id):
        try:
            with self._uow_factory() as uow:
                entry=uow.tracks.latest_metadata_edit(track_id); track=uow.tracks.get_by_id(track_id)
                if entry is None or track is None: return False
                previous=json.loads(entry.previous_json); uow.tracks.update_track_metadata(track,previous,commit=False)
                uow.tracks.record_metadata_edit(track_id, tuple(previous), json.loads(entry.new_json), previous, entry.origin, "restored", commit=False)
            return True
        except Exception: return False
