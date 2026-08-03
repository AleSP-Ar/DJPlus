import inspect
import unittest
from datetime import datetime, timezone

from app.services.assistant_context import AssistantContextDTO
from app.services.assistant_facade import AssistantTool, AssistantToolResultDTO
from app.services.assistant_runtime import AssistantRuntime, RuntimeRequestDTO
from app.services.tool_dispatcher import ToolCallDTO, ToolDispatcher, ToolRegistry
from app.services.tool_plan_executor import PlannedStepResultDTO, ToolPlanExecutionDTO, ToolPlanExecutor
from app.services.tool_planner import PlannedToolCallDTO, ToolPlanDTO


class _Tool(AssistantTool):
    input_schema = {"type": "object", "properties": {}, "additionalProperties": False}

    def __init__(self, name, should_fail=False):
        self.name = name
        self.description = name
        self.should_fail = should_fail
        self.calls = 0

    def execute(self, input_data):
        self.calls += 1
        if self.should_fail:
            raise ValueError("fallo simulado")
        return AssistantToolResultDTO(f"{self.name} ok", {}, ())


class ToolPlanExecutorTests(unittest.TestCase):
    def setUp(self):
        self.first = _Tool("first")
        self.second = _Tool("second")
        self.executor = ToolPlanExecutor(ToolDispatcher(ToolRegistry((self.first, self.second))))

    def test_executes_successful_steps_in_plan_order(self):
        plan = ToolPlanDTO("consulta", (
            PlannedToolCallDTO("one", ToolCallDTO("first")),
            PlannedToolCallDTO("two", ToolCallDTO("second"), ("one",)),
        ))

        execution = self.executor.execute(plan)

        self.assertIsInstance(execution, ToolPlanExecutionDTO)
        self.assertTrue(execution.successful)
        self.assertEqual([result.status for result in execution.step_results], ["success", "success"])
        self.assertEqual((self.first.calls, self.second.calls), (1, 1))

    def test_failure_is_typed_and_blocks_dependent_step(self):
        failing = _Tool("failing", should_fail=True)
        dependent = _Tool("dependent")
        executor = ToolPlanExecutor(ToolDispatcher(ToolRegistry((failing, dependent))))
        plan = ToolPlanDTO("consulta", (
            PlannedToolCallDTO("fail", ToolCallDTO("failing")),
            PlannedToolCallDTO("after", ToolCallDTO("dependent"), ("fail",)),
        ))

        execution = executor.execute(plan)

        self.assertEqual([result.status for result in execution.step_results], ["failed", "blocked"])
        self.assertFalse(execution.successful)
        self.assertEqual(dependent.calls, 0)
        self.assertIn("fail", execution.step_results[1].reason)

    def test_result_contract_and_executor_have_no_write_collaborators(self):
        with self.assertRaises(TypeError):
            ToolPlanExecutor(object())
        with self.assertRaises(Exception):
            PlannedStepResultDTO("step", "tool", "blocked")
        source = inspect.getsource(__import__("app.services.tool_plan_executor", fromlist=["*"]))
        for forbidden in ("ActionExecutor", "LibraryService", "app.repository", "sqlite3"):
            self.assertNotIn(forbidden, source)

    def test_runtime_optionally_returns_typed_plan_execution(self):
        runtime = AssistantRuntime(tool_registry=ToolRegistry((self.first, self.second)))
        plan = ToolPlanDTO("consulta", (
            PlannedToolCallDTO("one", ToolCallDTO("first")),
            PlannedToolCallDTO("two", ToolCallDTO("second"), ("one",)),
        ))

        result = runtime.process(RuntimeRequestDTO(
            "consulta",
            AssistantContextDTO({}, ("library",)),
            "session",
            datetime.now(timezone.utc),
            tool_plan=plan,
        ))

        self.assertTrue(result.tool_plan_execution.successful)
        self.assertEqual([item.tool_name for item in result.tool_results], ["first", "second"])
        self.assertEqual(result.composed_tool_response.summary, "Plan completado: 2 pasos exitosos.")
