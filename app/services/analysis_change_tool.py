"""Read-only preview tool for analysis metadata changes."""

from .assistant_facade import AssistantError, AssistantTool, AssistantToolResultDTO
from .analysis_change_planner import AnalysisChangePlanner, AnalysisMetadataDTO, AnalysisWritePolicyDTO


class AnalysisChangePreviewTool(AssistantTool):
    name = "analysis_change_preview"
    description = "Muestra cambios propuestos de BPM, key y energia sin escribirlos."
    input_schema = {"type": "object", "required": ["existing", "analyzed"], "properties": {"existing": {"type": "object"}, "analyzed": {"type": "object"}, "policy": {"type": "string"}}, "additionalProperties": False}

    def __init__(self, planner=None):
        self._planner = planner or AnalysisChangePlanner()
        if not isinstance(self._planner, AnalysisChangePlanner):
            raise TypeError("AnalysisChangePreviewTool requiere AnalysisChangePlanner.")

    def execute(self, input_data):
        payload = dict(input_data or {})
        try:
            result = self._planner.plan(AnalysisMetadataDTO(**payload["existing"]), AnalysisMetadataDTO(**payload["analyzed"]), AnalysisWritePolicyDTO(payload.get("policy", "never_overwrite")))
        except (KeyError, TypeError, ValueError) as error:
            raise AssistantError(str(error)) from error
        return AssistantToolResultDTO(result.preview, {"analysis_change_set": result})
