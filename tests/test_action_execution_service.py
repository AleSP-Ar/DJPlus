import inspect
import time
import unittest
from datetime import datetime, timezone

from app.services.action_execution_service import (
    ActionExecutionAuthorizationDTO,
    ActionExecutionService,
    ActionExecutionState,
)
from app.services.action_executor import MockActionExecutor
from app.services.action_pipeline import ActionPipeline, ActionType, ActionValidationDTO
from app.services.confirmation_manager import ConfirmationManager, ConfirmationRequestDTO


class ActionExecutionServiceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = ActionPipeline()
        self.executor = MockActionExecutor()
        self.service = ActionExecutionService(self.pipeline, ConfirmationManager(self.pipeline), self.executor)

    def _authorization(self, action_id, authorized=True):
        return ActionExecutionAuthorizationDTO(action_id, authorized, "test-operator", datetime.now(timezone.utc))

    def _proposal(self):
        return self.pipeline.create_proposal(ActionType.CREATE_PLAYLIST, "Sunset", "Test", {"name": "Sunset"})

    def test_confirmed_authorized_revalidated_proposal_reaches_only_mock_executor(self):
        proposal = self._proposal()

        result = self.service.execute(
            ConfirmationRequestDTO(proposal.action_id, datetime.now(timezone.utc)),
            self._authorization(proposal.action_id),
            execution_id="integrated-execution",
        )

        self.assertEqual(result.state, ActionExecutionState.EXECUTED)
        self.assertTrue(result.validation.valid)
        self.assertTrue(result.execution_result.simulated)
        self.assertEqual(len(self.executor.requests), 1)
        self.assertEqual(self.executor.audit_log.entries[0].outcome, "success")

    def test_authorization_rejection_never_calls_executor(self):
        proposal = self._proposal()

        result = self.service.execute(
            ConfirmationRequestDTO(proposal.action_id, datetime.now(timezone.utc)),
            self._authorization(proposal.action_id, authorized=False),
        )

        self.assertEqual(result.state, ActionExecutionState.AUTHORIZATION_REJECTED)
        self.assertEqual(self.executor.requests, [])
        self.assertEqual(self.executor.audit_log.entries, ())

    def test_confirmation_rejection_never_calls_executor(self):
        result = self.service.execute(
            ConfirmationRequestDTO("missing-action", datetime.now(timezone.utc)),
            self._authorization("missing-action"),
        )

        self.assertEqual(result.state, ActionExecutionState.CONFIRMATION_REJECTED)
        self.assertEqual(self.executor.requests, [])

    def test_executor_failure_is_a_typed_terminal_state(self):
        proposal = self._proposal()
        executor = MockActionExecutor({proposal.action_id: False})
        service = ActionExecutionService(self.pipeline, ConfirmationManager(self.pipeline), executor)

        result = service.execute(
            ConfirmationRequestDTO(proposal.action_id, datetime.now(timezone.utc)), self._authorization(proposal.action_id)
        )

        self.assertEqual(result.state, ActionExecutionState.EXECUTION_FAILED)
        self.assertFalse(result.execution_result.success)

    def test_revalidation_rejection_never_calls_executor(self):
        class InvalidRevalidationPipeline(ActionPipeline):
            def revalidate_registered_proposal(self, proposal):
                return ActionValidationDTO(False, errors=("La propuesta vencio.",))

        pipeline = InvalidRevalidationPipeline()
        executor = MockActionExecutor()
        service = ActionExecutionService(pipeline, ConfirmationManager(pipeline), executor)
        proposal = pipeline.create_proposal(ActionType.CUSTOM, "Vencida", "Test", {})

        result = service.execute(
            ConfirmationRequestDTO(proposal.action_id, datetime.now(timezone.utc)), self._authorization(proposal.action_id)
        )

        self.assertEqual(result.state, ActionExecutionState.VALIDATION_REJECTED)
        self.assertFalse(result.validation.valid)
        self.assertEqual(executor.requests, [])

    def test_lightweight_benchmark_runs_100_simulated_confirmed_executions(self):
        started = time.perf_counter()
        for index in range(100):
            proposal = self.pipeline.create_proposal(ActionType.CUSTOM, f"Benchmark {index}", "Test", {})
            result = self.service.execute(
                ConfirmationRequestDTO(proposal.action_id, datetime.now(timezone.utc)), self._authorization(proposal.action_id)
            )
            self.assertEqual(result.state, ActionExecutionState.EXECUTED)
        elapsed_seconds = time.perf_counter() - started

        self.assertLess(elapsed_seconds, 2.0)
        self.assertEqual(len(self.executor.requests), 100)

    def test_service_has_no_library_or_infrastructure_dependencies(self):
        source = inspect.getsource(__import__("app.services.action_execution_service", fromlist=["*"])).lower()
        for forbidden in ("app.repository", "sqlalchemy", "sqlite3", "libraryservice", "playlistservice"):
            self.assertNotIn(forbidden, source)
