import inspect
import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

from app.services.assistant_context import AssistantContextDTO
from app.services.assistant_facade import AssistantTool
from app.services.assistant_runtime import RuntimeRequestDTO
from app.services.prompt_builder import PromptBuilder, PromptDTO
from app.services.tool_dispatcher import ToolRegistry


class SearchTool(AssistantTool):
    name = "library_search"
    description = "Searches approved library data."
    input_schema = {"type": "object", "properties": {"query": {"type": "string"}}}

    def execute(self, input_data):
        raise AssertionError("PromptBuilder must never execute tools")


class PromptBuilderTests(unittest.TestCase):
    def setUp(self):
        self.context = AssistantContextDTO(
            available_data={"library": {"track_count": 42}},
            data_sources=("library",),
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            context_version="1.0",
        )
        self.request = RuntimeRequestDTO(
            user_query="Conserva este texto exactamente.",
            assistant_context=self.context,
            session_id="session-1",
            timestamp_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        self.builder = PromptBuilder(ToolRegistry([SearchTool()]), runtime_version="1.0")

    def test_prompt_dto_and_nested_fields_are_immutable(self):
        prompt = self.builder.build(self.request)

        self.assertIsInstance(prompt, PromptDTO)
        with self.assertRaises(FrozenInstanceError):
            prompt.user_prompt = "changed"
        with self.assertRaises(FrozenInstanceError):
            prompt.metadata.runtime_version = "changed"

    def test_system_prompt_is_deterministic_and_contains_no_user_data(self):
        first = self.builder.build(self.request)
        second = self.builder.build(self.request)

        self.assertEqual(first.system_prompt, second.system_prompt)
        self.assertIn("Runtime version: 1.0", first.system_prompt)
        self.assertNotIn(self.request.user_query, first.system_prompt)

    def test_context_block_uses_only_the_supplied_assistant_context(self):
        prompt = self.builder.build(self.request)

        self.assertEqual(prompt.context_block.data_sources, ("library",))
        self.assertEqual(prompt.context_block.timestamp, self.context.timestamp)
        self.assertEqual(prompt.context_block.context_version, "1.0")
        self.assertEqual(prompt.context_block.available_data, (("library", (("track_count", 42),)),))

    def test_user_prompt_and_tool_block_preserve_only_approved_data(self):
        prompt = self.builder.build(self.request)

        self.assertEqual(prompt.user_prompt, self.request.user_query)
        self.assertEqual(len(prompt.available_tools), 1)
        tool = prompt.available_tools[0]
        self.assertEqual(tool.name, "library_search")
        self.assertEqual(tool.description, "Searches approved library data.")
        self.assertEqual(tool.input_schema, (("type", "object"), ("properties", (("query", (("type", "string"),)),))))

    def test_builder_has_no_infrastructure_imports(self):
        source = inspect.getsource(__import__("app.services.prompt_builder", fromlist=["*"]))

        self.assertNotIn("app.repository", source)
        self.assertNotIn("sqlalchemy", source.lower())
        self.assertNotIn("sqlite3", source.lower())
        self.assertNotIn(".execute(", source)
