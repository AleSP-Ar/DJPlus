import unittest

from app.services.sync_service import (
    MockSyncAdapter,
    SyncAction,
    SyncConfirmationRequiredError,
    SyncConflictError,
    SyncService,
)


class SyncServiceTests(unittest.TestCase):
    def setUp(self):
        self.adapter = MockSyncAdapter(
            {
                "keep": "same",
                "update": "old",
                "delete": "stale",
                "conflict": {"value": "external", "conflict": True},
            }
        )
        self.service = SyncService(self.adapter)
        self.local_state = {
            "keep": "same",
            "update": "new",
            "add": "fresh",
            "conflict": "local",
        }

    def test_mock_adapter_reads_and_builds_reproducible_plan(self):
        first = self.service.plan(self.local_state)
        second = self.service.plan(self.local_state)

        self.assertEqual(first, second)
        self.assertEqual(
            [(change.action, change.external_id) for change in first.changes],
            [(SyncAction.ADD, "add"), (SyncAction.DELETE, "delete"), (SyncAction.UPDATE, "update")],
        )
        self.assertEqual(first.affected_items, ("add", "conflict", "delete", "update"))

    def test_preview_groups_add_update_delete_and_conflicts(self):
        preview = self.service.preview(self.service.plan(self.local_state))

        self.assertEqual([change.external_id for change in preview.additions], ["add"])
        self.assertEqual([change.external_id for change in preview.updates], ["update"])
        self.assertEqual([change.external_id for change in preview.deletions], ["delete"])
        self.assertEqual(preview.conflicts[0].external_id, "conflict")

    def test_apply_requires_preview_confirmation_and_no_conflicts(self):
        safe_plan = self.service.plan({"keep": "same", "update": "new", "add": "fresh"})
        with self.assertRaises(SyncConfirmationRequiredError):
            self.service.apply(safe_plan, confirmed=True)
        self.service.preview(safe_plan)
        with self.assertRaises(SyncConfirmationRequiredError):
            self.service.apply(safe_plan, confirmed=False)

        applied = self.service.apply(safe_plan, confirmed=True)

        self.assertEqual(applied, ("add", "conflict", "delete", "update"))
        self.assertEqual(self.adapter.read_external_state(), {"keep": "same", "update": "new", "add": "fresh"})
        self.assertEqual(len(self.adapter.applied_plans), 1)

    def test_conflicts_are_detected_and_block_apply(self):
        plan = self.service.plan(self.local_state)
        self.service.preview(plan)

        with self.assertRaises(SyncConflictError):
            self.service.apply(plan, confirmed=True)

        self.assertEqual(self.adapter.applied_plans, [])
