import inspect
import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

from app.services.action_pipeline import ActionPipeline, ActionType
from app.services.confirmation_manager import (
    ConfirmationManager,
    ConfirmationRequestDTO,
)


class ConfirmationManagerTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = ActionPipeline()
        self.manager = ConfirmationManager(self.pipeline)

    def _request(self, action_id):
        return ConfirmationRequestDTO(action_id, datetime.now(timezone.utc))

    def test_confirms_valid_proposal_once_and_keeps_request_immutable(self):
        proposal = self.pipeline.create_proposal(ActionType.CREATE_PLAYLIST, "Playlist", "Test", {})
        request = self._request(proposal.action_id)

        result = self.manager.request_confirmation(request)

        self.assertTrue(result.allowed)
        self.assertTrue(result.confirmed)
        self.assertIn("puede confirmarse", result.reason)
        with self.assertRaises(FrozenInstanceError):
            request.action_id = "other"

    def test_rejects_missing_discarded_and_duplicate_proposals(self):
        missing = self.manager.request_confirmation(self._request("missing"))
        proposal = self.pipeline.create_proposal(ActionType.CUSTOM, "Discard", "Test", {})
        self.pipeline.discard_proposal(proposal.action_id)
        discarded = self.manager.request_confirmation(self._request(proposal.action_id))
        duplicate_proposal = self.pipeline.create_proposal(ActionType.CUSTOM, "Duplicate", "Test", {})
        self.manager.request_confirmation(self._request(duplicate_proposal.action_id))
        duplicate = self.manager.request_confirmation(self._request(duplicate_proposal.action_id))

        self.assertFalse(missing.allowed)
        self.assertIn("no existe", missing.reason)
        self.assertFalse(discarded.allowed)
        self.assertIn("descartada", discarded.reason)
        self.assertFalse(duplicate.allowed)
        self.assertIn("ya fue confirmada", duplicate.reason)

    def test_confirmation_manager_has_no_execution_or_infrastructure_imports(self):
        source = inspect.getsource(__import__("app.services.confirmation_manager", fromlist=["*"]))

        self.assertNotIn("app.repository", source)
        self.assertNotIn("sqlalchemy", source.lower())
        self.assertNotIn("sqlite3", source.lower())
        self.assertNotIn(".execute(", source)
