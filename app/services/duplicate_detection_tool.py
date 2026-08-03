"""Read-only duplicate report tool."""
from .assistant_facade import AssistantTool, AssistantToolResultDTO
from .duplicate_detection_service import DuplicateScanQueryDTO
class DuplicateDetectionTool(AssistantTool):
 name="duplicate_detection";description="Detecta duplicados sin modificar archivos.";input_schema={"type":"object","properties":{"track_ids":{"type":"array"}},"additionalProperties":False}
 def __init__(self,facade): self.facade=facade
 def execute(self,data):
  result=self.facade.scan(DuplicateScanQueryDTO(tuple(dict(data or {}).get("track_ids",()))))
  return AssistantToolResultDTO("Informe de duplicados disponible.",{"duplicate_result":result,"duplicate_report":self.facade.export_text(result)})
