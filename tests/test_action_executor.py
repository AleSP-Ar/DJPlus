import inspect
import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

from app.services.action_executor import (
    ActionExecutionError,
    ActionExecutor,
    ExecutionAuditEntryDTO,
    ExecutionAuditLog,
    ExecutionRequestDTO,
    ExecutionResultDTO,
    IdempotencyRegistry,
    MockActionExecutor,
    RollbackResultDTO,
)
from app.services.action_pipeline import ActionPipeline, ActionType


class ActionExecutorTests(unittest.TestCase):
    def setUp(self):
        self.proposal = ActionPipeline().create_proposal(
            ActionType.CREATE_PLAYLIST, "Crear Sunset", "Prueba", {"name": "Sunset"}
        )

    def test_executor_is_abstract_and_mock_simulates_typed_success(self):
        request = ExecutionRequestDTO(self.proposal, True, "execution-1", datetime.now(timezone.utc))
        executor = MockActionExecutor()

        with self.assertRaises(TypeError):
            ActionExecutor()
        result = executor.execute(request)

        self.assertIsInstance(result, ExecutionResultDTO)
        self.assertTrue(result.success)
        self.assertTrue(result.simulated)
        self.assertEqual(result.action_id, self.proposal.action_id)
        self.assertEqual(executor.requests, [request])

    def test_contract_requires_proposal_confirmation_utc_and_immutable_result(self):
        with self.assertRaises(ActionExecutionError):
            ExecutionRequestDTO(self.proposal, False)
        with self.assertRaises(ActionExecutionError):
            ExecutionRequestDTO(self.proposal, True, requested_at_utc=datetime.now())
        result = MockActionExecutor().execute(ExecutionRequestDTO(self.proposal, True))

        with self.assertRaises(FrozenInstanceError):
            result.success = False
        with self.assertRaises(TypeError):
            result.details["action_type"] = "custom"

    def test_mock_simulates_deterministic_failure_without_any_service_execution(self):
        executor = MockActionExecutor({self.proposal.action_id: False})

        result = executor.execute(ExecutionRequestDTO(self.proposal, True))

        self.assertFalse(result.success)
        self.assertTrue(result.simulated)
        source = inspect.getsource(__import__("app.services.action_executor", fromlist=["*"]))
        for forbidden in ("app.repository", "sqlalchemy", "sqlite3", "subprocess", "Service"):
            self.assertNotIn(forbidden, source)

    def test_rejects_invalid_requests_and_results(self):
        with self.assertRaises(TypeError):
            MockActionExecutor().execute(object())
        with self.assertRaises(ActionExecutionError):
            ExecutionResultDTO("id", "action", True, False, "invalid")

    def test_execution_id_is_consumed_once_and_both_attempts_are_audited(self):
        audit_log = ExecutionAuditLog()
        registry = IdempotencyRegistry()
        executor = MockActionExecutor(audit_log=audit_log, idempotency_registry=registry)
        request = ExecutionRequestDTO(self.proposal, True, "one-time-id")

        first = executor.execute(request)
        duplicate = executor.execute(request)

        self.assertTrue(first.success)
        self.assertFalse(duplicate.success)
        self.assertEqual(duplicate.details["reason"], "duplicate_execution_id")
        self.assertTrue(registry.contains("one-time-id"))
        self.assertEqual([entry.outcome for entry in audit_log.entries], ["success", "rejected"])
        self.assertTrue(all(entry.operation == "execute" for entry in audit_log.entries))

    def test_success_failure_and_rollback_are_typed_and_audited(self):
        failure = MockActionExecutor({self.proposal.action_id: False})
        request = ExecutionRequestDTO(self.proposal, True, "failed-execution")

        execution = failure.execute(request)
        rollback = failure.rollback(request)

        self.assertIsInstance(execution, ExecutionResultDTO)
        self.assertFalse(execution.success)
        self.assertIsInstance(rollback, RollbackResultDTO)
        self.assertTrue(rollback.success)
        self.assertTrue(rollback.simulated)
        self.assertEqual(
            [(entry.operation, entry.outcome) for entry in failure.audit_log.entries],
            [("execute", "failure"), ("rollback", "success")],
        )

    def test_rollback_of_unknown_execution_is_typed_rejected_and_audited(self):
        executor = MockActionExecutor()
        request = ExecutionRequestDTO(self.proposal, True, "unknown-execution")

        rollback = executor.rollback(request)

        self.assertFalse(rollback.success)
        self.assertEqual(rollback.details["reason"], "execution_not_found")
        self.assertEqual(executor.audit_log.entries[0].outcome, "rejected")

    def test_audit_and_rollback_contracts_are_immutable_and_validated(self):
        entry = ExecutionAuditEntryDTO("id", "action", "execute", "success", "ok")
        rollback = RollbackResultDTO("id", "action", True, True, "ok")

        with self.assertRaises(TypeError):
            entry.details["x"] = "y"
        with self.assertRaises(FrozenInstanceError):
            rollback.success = False
        with self.assertRaises(ActionExecutionError):
            ExecutionAuditEntryDTO("id", "action", "invalid", "success", "ok")
        with self.assertRaises(TypeError):
            ExecutionAuditLog().record(object())
