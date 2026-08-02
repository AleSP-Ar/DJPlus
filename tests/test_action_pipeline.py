import inspect
import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

from app.services.action_pipeline import (
    ActionPipeline,
    ActionPipelineError,
    ActionProposalDTO,
    ActionType,
)


class ActionPipelineTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = ActionPipeline()

    def test_creates_valid_immutable_confirmed_proposal(self):
        proposal = self.pipeline.create_proposal(
            ActionType.CREATE_PLAYLIST,
            "Crear playlist Sunset",
            "Propuesta de prueba.",
            {"name": "Sunset", "tracks": [1, 2]},
        )

        self.assertEqual(proposal.action_type, ActionType.CREATE_PLAYLIST)
        self.assertTrue(proposal.requires_confirmation)
        self.assertEqual(proposal.payload["tracks"], (1, 2))
        with self.assertRaises(FrozenInstanceError):
            proposal.title = "changed"
        with self.assertRaises(TypeError):
            proposal.payload["name"] = "changed"

    def test_validates_and_rejects_duplicate_identifiers(self):
        proposal = self.pipeline.create_proposal(
            ActionType.CUSTOM, "Custom", "Test", {}
        )

        validation = self.pipeline.validate_proposal(proposal)
        self.assertFalse(validation.valid)
        self.assertIn("ya existe", validation.errors[0])
        with self.assertRaises(ActionPipelineError):
            self.pipeline.register_proposal(proposal)

    def test_rejects_invalid_payloads_and_confirmation_contract(self):
        with self.assertRaises(ActionPipelineError):
            self.pipeline.create_proposal(ActionType.CUSTOM, "Invalid", "Test", {"bad": object()})
        with self.assertRaises(ActionPipelineError):
            ActionProposalDTO(
                "action-1", ActionType.CUSTOM, "Invalid", "Test", {}, False, datetime.now(timezone.utc)
            )

    def test_lists_gets_discards_and_clears_proposals(self):
        first = self.pipeline.create_proposal(ActionType.CREATE_PLAYLIST, "First", "Test", {})
        second = self.pipeline.create_proposal(ActionType.CREATE_COLLECTION, "Second", "Test", {})

        self.assertEqual(self.pipeline.list_proposals(), (first, second))
        self.assertEqual(self.pipeline.get_proposal(first.action_id), first)
        self.assertEqual(self.pipeline.discard_proposal(first.action_id), first)
        self.assertIsNone(self.pipeline.get_proposal(first.action_id))
        self.pipeline.clear()
        self.assertEqual(self.pipeline.list_proposals(), ())

    def test_pipeline_has_no_infrastructure_or_execution_imports(self):
        source = inspect.getsource(__import__("app.services.action_pipeline", fromlist=["*"]))

        self.assertNotIn("app.repository", source)
        self.assertNotIn("sqlalchemy", source.lower())
        self.assertNotIn("sqlite3", source.lower())
        self.assertNotIn("subprocess", source.lower())
        self.assertNotIn(".execute(", source)
