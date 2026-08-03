import inspect
import unittest

from app.services.assistant_facade import AssistantTool
from app.services.tool_dispatcher import ToolCallDTO, ToolRegistry
from app.services.tool_planner import DeterministicToolPlanner, PlannedToolCallDTO, ToolPlanDTO, ToolPlanner, ToolPlanningError


class _Tool(AssistantTool):
    input_schema = {"type": "object", "properties": {"query": {"type": "string"}}, "additionalProperties": False}

    def __init__(self, name):
        self.name = name
        self.description = name

    def execute(self, input_data):
        raise AssertionError("La planificación no debe ejecutar herramientas.")


class ToolPlannerTests(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry((_Tool("library_query"), _Tool("playlist"), _Tool("collection")))
        self.planner = DeterministicToolPlanner()

    def test_planner_is_abstract_and_creates_ordered_multiple_calls_without_execution(self):
        with self.assertRaises(TypeError):
            ToolPlanner()
        plan = self.planner.plan("Biblioteca BPM 128, playlists y colecciones", self.registry)
        self.assertIsInstance(plan, ToolPlanDTO)
        self.assertEqual([call.tool_call.tool_name for call in plan.planned_calls], ["library_query", "playlist", "collection"])

    def test_plan_validates_unique_ordered_dependencies(self):
        first = PlannedToolCallDTO("first", ToolCallDTO("library_query"))
        second = PlannedToolCallDTO("second", ToolCallDTO("playlist"), ("first",))
        self.assertEqual(ToolPlanDTO("consulta", (first, second)).planned_calls[1].depends_on, ("first",))
        with self.assertRaises(ToolPlanningError):
            ToolPlanDTO("consulta", (PlannedToolCallDTO("second", ToolCallDTO("playlist"), ("first",)), first))
        with self.assertRaises(ToolPlanningError):
            ToolPlanDTO("consulta", (first, PlannedToolCallDTO("first", ToolCallDTO("playlist"))))

    def test_unavailable_tools_and_invalid_inputs_are_rejected_without_dispatch(self):
        with self.assertRaises(Exception):
            self.planner.plan("playlists", ToolRegistry((_Tool("library_query"),)))
        with self.assertRaises(ToolPlanningError):
            self.planner.plan(" ", self.registry)
        source = inspect.getsource(__import__("app.services.tool_planner", fromlist=["*"]))
        for forbidden in (".dispatch(", ".execute(", "app.repository", "sqlite3"):
            self.assertNotIn(forbidden, source)
