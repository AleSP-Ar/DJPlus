"""Pure composition of typed tool-plan outcomes; it never dispatches or executes."""

from dataclasses import dataclass

from .tool_plan_executor import PlannedStepResultDTO, ToolPlanExecutionDTO


class ToolResultCompositionError(ValueError):
    """Raised when a composed response does not preserve an execution contract."""


@dataclass(frozen=True)
class ComposedToolResponseDTO:
    """Structured, ordered and deterministic explanation of one tool-plan execution."""

    execution: ToolPlanExecutionDTO
    summary: str
    ordered_steps: tuple[PlannedStepResultDTO, ...]
    successful_responses: tuple[str, ...]
    issues: tuple[str, ...]

    def __post_init__(self):
        if not isinstance(self.execution, ToolPlanExecutionDTO):
            raise ToolResultCompositionError("La composicion requiere ToolPlanExecutionDTO.")
        if not isinstance(self.summary, str) or not self.summary.strip():
            raise ToolResultCompositionError("El resumen compuesto es obligatorio.")
        if self.ordered_steps != self.execution.step_results:
            raise ToolResultCompositionError("La composicion debe preservar el orden completo del plan.")
        if not all(isinstance(value, str) and value.strip() for value in self.successful_responses + self.issues):
            raise ToolResultCompositionError("Las respuestas compuestas deben ser textos no vacios.")


class ToolResultComposer:
    """Convert a completed plan into an ordered data-only response."""

    def compose(self, execution):
        if not isinstance(execution, ToolPlanExecutionDTO):
            raise TypeError("ToolResultComposer.compose requiere ToolPlanExecutionDTO.")
        successful = []
        issues = []
        failed = 0
        blocked = 0
        for step in execution.step_results:
            label = f"{step.call_id} ({step.tool_name})"
            if step.status == "success":
                successful.append(f"{label}: {step.tool_result.result.response}")
            elif step.status == "failed":
                failed += 1
                issues.append(f"{label} falló: {step.tool_result.error}")
            else:
                blocked += 1
                issues.append(f"{label} bloqueado: {step.reason}")
        succeeded = len(successful)
        if succeeded == len(execution.step_results):
            summary = f"Plan completado: {succeeded} pasos exitosos."
        elif succeeded == 0:
            summary = f"Plan fallido: 0 pasos exitosos, {failed} fallidos y {blocked} bloqueados."
        else:
            summary = f"Plan parcial: {succeeded} pasos exitosos, {failed} fallidos y {blocked} bloqueados."
        return ComposedToolResponseDTO(execution, summary, execution.step_results, tuple(successful), tuple(issues))
