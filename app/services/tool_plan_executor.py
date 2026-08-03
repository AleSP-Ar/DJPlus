"""Ordered execution of pure tool plans through the dispatcher boundary only."""

from dataclasses import dataclass

from .tool_dispatcher import ToolDispatcher, ToolResultDTO
from .tool_planner import ToolPlanDTO


class ToolPlanExecutionError(ValueError):
    """Raised when a typed tool-plan execution contract is invalid."""


@dataclass(frozen=True)
class PlannedStepResultDTO:
    call_id: str
    tool_name: str
    status: str
    tool_result: ToolResultDTO | None = None
    reason: str | None = None

    def __post_init__(self):
        if not isinstance(self.call_id, str) or not self.call_id.strip():
            raise ToolPlanExecutionError("El resultado debe identificar el paso.")
        if not isinstance(self.tool_name, str) or not self.tool_name.strip():
            raise ToolPlanExecutionError("El resultado debe identificar la herramienta.")
        if self.status not in {"success", "failed", "blocked"}:
            raise ToolPlanExecutionError("El estado del paso no es valido.")
        if self.status == "success" and (not isinstance(self.tool_result, ToolResultDTO) or not self.tool_result.success or self.reason is not None):
            raise ToolPlanExecutionError("Un paso exitoso requiere ToolResultDTO exitoso.")
        if self.status == "failed" and (not isinstance(self.tool_result, ToolResultDTO) or self.tool_result.success or self.reason is not None):
            raise ToolPlanExecutionError("Un paso fallido requiere ToolResultDTO fallido.")
        if self.status == "blocked" and (self.tool_result is not None or not isinstance(self.reason, str) or not self.reason.strip()):
            raise ToolPlanExecutionError("Un paso bloqueado requiere un motivo seguro.")


@dataclass(frozen=True)
class ToolPlanExecutionDTO:
    plan: ToolPlanDTO
    step_results: tuple[PlannedStepResultDTO, ...]

    def __post_init__(self):
        if not isinstance(self.plan, ToolPlanDTO):
            raise ToolPlanExecutionError("La ejecucion requiere ToolPlanDTO.")
        if not isinstance(self.step_results, tuple) or not all(isinstance(item, PlannedStepResultDTO) for item in self.step_results):
            raise ToolPlanExecutionError("La ejecucion requiere resultados tipados por paso.")
        expected_ids = tuple(call.call_id for call in self.plan.planned_calls)
        if tuple(item.call_id for item in self.step_results) != expected_ids:
            raise ToolPlanExecutionError("Los resultados deben conservar el orden completo del plan.")

    @property
    def successful(self):
        return all(result.status == "success" for result in self.step_results)


class ToolPlanExecutor:
    """Execute approved read-only tool calls only via an injected ToolDispatcher."""

    def __init__(self, dispatcher):
        if not isinstance(dispatcher, ToolDispatcher):
            raise TypeError("ToolPlanExecutor requiere ToolDispatcher.")
        self._dispatcher = dispatcher

    def execute(self, plan):
        if not isinstance(plan, ToolPlanDTO):
            raise TypeError("ToolPlanExecutor.execute requiere ToolPlanDTO.")
        results = []
        completed = {}
        for step in plan.planned_calls:
            failed_dependencies = [dependency for dependency in step.depends_on if completed[dependency].status != "success"]
            if failed_dependencies:
                result = PlannedStepResultDTO(
                    step.call_id,
                    step.tool_call.tool_name,
                    "blocked",
                    reason="Dependencia no completada: " + ", ".join(failed_dependencies),
                )
            else:
                try:
                    tool_result = self._dispatcher.dispatch(step.tool_call)
                except Exception as error:
                    tool_result = ToolResultDTO(step.tool_call.tool_name, False, error=str(error) or "Error de dispatcher.")
                status = "success" if tool_result.success else "failed"
                result = PlannedStepResultDTO(step.call_id, step.tool_call.tool_name, status, tool_result=tool_result)
            completed[step.call_id] = result
            results.append(result)
        return ToolPlanExecutionDTO(plan, tuple(results))
