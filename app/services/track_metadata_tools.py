from .assistant_facade import AssistantTool, AssistantToolResultDTO, AssistantError
from .track_metadata_editor import TrackMetadataPatchDTO, BulkMetadataEditQueryDTO
from .confirmation_manager import ConfirmationRequestDTO
from datetime import datetime, timezone

class TrackMetadataPreviewTool(AssistantTool):
 name="track_metadata_preview"; description="Previsualiza edicion de metadata sin escribir."; input_schema={"type":"object","required":["track_ids","patch"],"properties":{"track_ids":{"type":"array"},"patch":{"type":"object"}},"additionalProperties":False}
 def __init__(self,facade): self.facade=facade
 def execute(self,data):
  try: r=self.facade.preview(BulkMetadataEditQueryDTO(tuple(data["track_ids"]),TrackMetadataPatchDTO.from_mapping(data["patch"])))
  except Exception as e: raise AssistantError(str(e))
  return AssistantToolResultDTO(r.preview,{"metadata_preview":r,"text":self.facade.export_preview(r)})
class TrackMetadataApplyTool(AssistantTool):
 name="track_metadata_apply"; description="Aplica metadata solo con confirmacion valida."; input_schema={"type":"object","required":["confirmation_id"],"properties":{"confirmation_id":{"type":"string"}},"additionalProperties":False}
 def __init__(self,facade): self.facade=facade; self._pending={}
 def prepare(self,data):
  preview=TrackMetadataPreviewTool(self.facade).execute(data).data_used["metadata_preview"]; proposal=self.facade.editor.propose(preview); self._pending[proposal.action_id]=(preview,proposal)
  return AssistantToolResultDTO("Propuesta de edicion preparada; requiere confirmacion.",{"metadata_preview":preview,"confirmation_id":proposal.action_id})
 def execute(self,data):
  token=dict(data or {}).get("confirmation_id"); pending=self._pending.get(token)
  if not isinstance(token,str) or pending is None: raise AssistantError("confirmation_id valido requerido para aplicar metadata.")
  preview,proposal=pending; result=self.facade.editor.apply(preview,proposal,ConfirmationRequestDTO(token,datetime.now(timezone.utc)))
  if not result.success: raise AssistantError(result.error or "La aplicacion fue rechazada.")
  self._pending.pop(token,None); return AssistantToolResultDTO("Metadata aplicada.",{"metadata_result":result,"text":self.facade.export_result(result)})
