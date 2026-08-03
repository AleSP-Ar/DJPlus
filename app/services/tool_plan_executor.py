"""Ordered execution of pure tool plans through the dispatcher boundary only."""

from dataclasses import dataclass
import time
from threading import Event

from .tool_dispatcher import ToolDispatcher, ToolResultDTO
from .tool_planner import ToolPlanDTO
from .optimization_metrics import OperationMetricsDTO, StageTimingDTO
from .execution_hardening import ExecutionConcurrencyLimiter, ExecutionEventMetricsDTO, ExecutionHardeningConfigDTO


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

    def __init__(self, dispatcher, hardening_config=None):
        if not isinstance(dispatcher, ToolDispatcher):
            raise TypeError("ToolPlanExecutor requiere ToolDispatcher.")
        if hardening_config is not None and not isinstance(hardening_config, ExecutionHardeningConfigDTO):
            raise TypeError("hardening_config debe ser ExecutionHardeningConfigDTO o nulo.")
        self._dispatcher = dispatcher
        self._hardening_config = hardening_config or ExecutionHardeningConfigDTO()
        self._limiter = ExecutionConcurrencyLimiter(self._hardening_config.max_concurrency)
        self._dependency_cache = {}
        self._last_metrics = OperationMetricsDTO("tool_plan_execution", ())
        self._hardening_metrics = ExecutionEventMetricsDTO("tool_plan_execution")
        self._cancel_requested = Event()

    def cancel(self):
        """Request cooperative cancellation before the next plan step."""
        self._cancel_requested.set()

    def execute(self, plan):
        if not isinstance(plan, ToolPlanDTO):
            raise TypeError("ToolPlanExecutor.execute requiere ToolPlanDTO.")
        if not self._limiter.try_acquire():
            self._hardening_metrics = ExecutionEventMetricsDTO(
                "tool_plan_execution",
                concurrency_rejected=self._hardening_metrics.concurrency_rejected + 1,
            )
            raise ToolPlanExecutionError("Se alcanzo el limite de concurrencia del plan.")
        started = time.perf_counter()
        self._cancel_requested.clear()
        timed_out = cancelled = failed = 0
        try:
            dependency_started = time.perf_counter()
            cache_key = tuple((step.call_id, step.depends_on) for step in plan.planned_calls)
            dependencies = self._dependency_cache.get(cache_key)
            if dependencies is None:
                dependencies = {step.call_id: step.depends_on for step in plan.planned_calls}
                if len(self._dependency_cache) >= 128:
                    self._dependency_cache.clear()
                self._dependency_cache[cache_key] = dependencies
            dependency_ms = (time.perf_counter() - dependency_started) * 1000
            results = []
            completed = {}
            dispatch_ms = 0.0
            for step in plan.planned_calls:
                if self._is_cancelled():
                    cancelled = 1
                    result = PlannedStepResultDTO(step.call_id, step.tool_call.tool_name, "blocked", reason="Ejecucion cancelada cooperativamente.")
                    completed[step.call_id] = result
                    results.append(result)
                    continue
                if self._is_timed_out(started):
                    timed_out = 1
                    result = PlannedStepResultDTO(step.call_id, step.tool_call.tool_name, "blocked", reason="Ejecucion supero el timeout configurado.")
                    completed[step.call_id] = result
                    results.append(result)
                    continue
                failed_dependencies = [dependency for dependency in dependencies[step.call_id] if completed[dependency].status != "success"]
                if failed_dependencies:
                    result = PlannedStepResultDTO(
                        step.call_id,
                        step.tool_call.tool_name,
                        "blocked",
                        reason="Dependencia no completada: " + ", ".join(failed_dependencies),
                    )
                else:
                    dispatch_started = time.perf_counter()
                    try:
                        tool_result = self._dispatcher.dispatch(step.tool_call)
                    except Exception as error:
                        tool_result = ToolResultDTO(step.tool_call.tool_name, False, error=str(error) or "Error de dispatcher.")
                    status = "success" if tool_result.success else "failed"
                    result = PlannedStepResultDTO(step.call_id, step.tool_call.tool_name, status, tool_result=tool_result)
                    dispatch_ms += (time.perf_counter() - dispatch_started) * 1000
                    if status == "failed":
                        failed += 1
                completed[step.call_id] = result
                results.append(result)
            execution = ToolPlanExecutionDTO(plan, tuple(results))
            self._last_metrics = OperationMetricsDTO("tool_plan_execution", (
                StageTimingDTO("dependency_resolution", dependency_ms),
                StageTimingDTO("dispatch", dispatch_ms),
                StageTimingDTO("total", (time.perf_counter() - started) * 1000),
            ))
            self._hardening_metrics = ExecutionEventMetricsDTO(
                "tool_plan_execution",
                cancelled,
                timed_out,
                failed,
                self._hardening_metrics.concurrency_rejected,
            )
            return execution
        finally:
            self._limiter.release()

    def _is_cancelled(self):
        return self._cancel_requested.is_set()

    def _is_timed_out(self, started):
        return self._hardening_config.timeout_ms is not None and (time.perf_counter() - started) * 1000 >= self._hardening_config.timeout_ms
