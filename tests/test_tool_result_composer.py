import inspect
import unittest

from app.services.assistant_facade import AssistantToolResultDTO
from app.services.tool_dispatcher import ToolCallDTO, ToolResultDTO
from app.services.tool_plan_executor import PlannedStepResultDTO, ToolPlanExecutionDTO
from app.services.tool_planner import PlannedToolCallDTO, ToolPlanDTO
from app.services.tool_result_composer import ComposedToolResponseDTO, ToolResultComposer


class ToolResultComposerTests(unittest.TestCase):
    def _execution(self, statuses):
        calls = tuple(PlannedToolCallDTO(f"step-{index}", ToolCallDTO(f"tool-{index}")) for index in range(len(statuses)))
        plan = ToolPlanDTO("consulta", calls)
        results = []
        for index, status in enumerate(statuses):
            call = calls[index]
            if status == "success":
                results.append(PlannedStepResultDTO(call.call_id, call.tool_call.tool_name, status, ToolResultDTO(
                    call.tool_call.tool_name, True, AssistantToolResultDTO(f"respuesta {index}", {}, ())
                )))
            elif status == "failed":
                results.append(PlannedStepResultDTO(call.call_id, call.tool_call.tool_name, status, ToolResultDTO(
                    call.tool_call.tool_name, False, error=f"error {index}"
                )))
            else:
                results.append(PlannedStepResultDTO(call.call_id, call.tool_call.tool_name, status, reason=f"dependencia {index}"))
        return ToolPlanExecutionDTO(plan, tuple(results))

    def test_composes_complete_success_in_plan_order(self):
        composed = ToolResultComposer().compose(self._execution(("success", "success")))

        self.assertIsInstance(composed, ComposedToolResponseDTO)
        self.assertEqual(composed.summary, "Plan completado: 2 pasos exitosos.")
        self.assertEqual(composed.successful_responses, ("step-0 (tool-0): respuesta 0", "step-1 (tool-1): respuesta 1"))
        self.assertEqual(composed.issues, ())

    def test_composes_partial_result_with_failure_and_blocked_explanation(self):
        composed = ToolResultComposer().compose(self._execution(("success", "failed", "blocked")))

        self.assertEqual(composed.summary, "Plan parcial: 1 pasos exitosos, 1 fallidos y 1 bloqueados.")
        self.assertEqual([step.status for step in composed.ordered_steps], ["success", "failed", "blocked"])
        self.assertIn("falló", composed.issues[0])
        self.assertIn("bloqueado", composed.issues[1])

    def test_composes_failed_plan_and_has_no_execution_dependencies(self):
        composed = ToolResultComposer().compose(self._execution(("failed", "blocked")))

        self.assertEqual(composed.summary, "Plan fallido: 0 pasos exitosos, 1 fallidos y 1 bloqueados.")
        source = inspect.getsource(__import__("app.services.tool_result_composer", fromlist=["*"]))
        for forbidden in ("ToolDispatcher", "ActionExecutor", "app.repository", "sqlite3", ".execute("):
            self.assertNotIn(forbidden, source)
