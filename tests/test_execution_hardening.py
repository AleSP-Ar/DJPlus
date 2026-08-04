import threading
import time
import unittest
from types import SimpleNamespace

from qt_test_helpers import ensure_qapplication
from app.services.assistant_facade import AssistantTool, AssistantToolResultDTO
from app.services.execution_hardening import ExecutionHardeningConfigDTO
from app.services.import_events import ImportEvent
from app.services.import_worker import ImportWorker
from app.services.local_assistant_mvp import LocalAssistantMVP
from app.services.provider_transport import MockProviderTransport
from app.services.tool_dispatcher import ToolCallDTO, ToolDispatcher, ToolRegistry
from app.services.tool_plan_executor import ToolPlanExecutionError, ToolPlanExecutor
from app.services.tool_planner import PlannedToolCallDTO, ToolPlanDTO
from app.ui.assistant_worker import AssistantWorker


class _ImportServiceDouble:
    def __init__(self, fail=False):
        self.fail = fail

    def run(self, root_path, cancel_requested=None, on_event=None):
        on_event(ImportEvent("started", job_id=1))
        for _ in range(20):
            time.sleep(0.003)
            on_event(ImportEvent("file_found", job_id=1))
            if cancel_requested():
                on_event(ImportEvent("cancelled", job_id=1))
                return SimpleNamespace(status="cancelled")
        if self.fail:
            raise RuntimeError("double failure")
        on_event(ImportEvent("completed", job_id=1))
        return SimpleNamespace(status="imported")


class _LibraryDouble:
    def count_tracks(self):
        return 1


class _SlowMVP(LocalAssistantMVP):
    def ask(self, user_query, cancellation_token=None):
        time.sleep(0.03)
        return super().ask(user_query, cancellation_token)


class _SlowTool(AssistantTool):
    name = "slow"
    description = "slow"
    input_schema = {"type": "object", "properties": {}, "additionalProperties": False}

    def __init__(self, entered=None):
        self.entered = entered

    def execute(self, input_data):
        if self.entered is not None:
            self.entered.set()
        time.sleep(0.02)
        return AssistantToolResultDTO("ok", {}, ())


class ExecutionHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = ensure_qapplication()

    def _mvp(self):
        return _SlowMVP(_LibraryDouble(), transport=MockProviderTransport(json_body={"message": {"content": "ok"}}))

    def _plan(self):
        return ToolPlanDTO("stress", (
            PlannedToolCallDTO("one", ToolCallDTO("slow")),
            PlannedToolCallDTO("two", ToolCallDTO("slow")),
        ))

    def test_import_timeout_is_cooperative_and_close_waits_safely(self):
        worker = ImportWorker(_ImportServiceDouble(), ExecutionHardeningConfigDTO(timeout_ms=1))
        worker.start("ignored")
        result = worker.wait(2)

        self.assertEqual(result.status, "cancelled")
        self.assertEqual(worker._hardening_metrics.timed_out, 1)
        self.assertTrue(worker.close(0.1))

    def test_import_failure_is_isolated_and_next_worker_runs(self):
        failed = ImportWorker(_ImportServiceDouble(fail=True))
        failed.start("ignored")
        failed.wait(2)
        healthy = ImportWorker(_ImportServiceDouble())
        healthy.start("ignored")

        self.assertIsNotNone(failed.error)
        self.assertEqual(failed._hardening_metrics.failed, 1)
        self.assertEqual(healthy.wait(2).status, "imported")

    def test_assistant_worker_enforces_timeout_and_shared_concurrency_limit(self):
        config = ExecutionHardeningConfigDTO(timeout_ms=1, max_concurrency=1)
        first = AssistantWorker(self._mvp(), "uno", config)
        second = AssistantWorker(self._mvp(), "dos", config)
        signals = []
        second.error.connect(signals.append)
        thread = threading.Thread(target=first.run)
        thread.start()
        time.sleep(0.005)
        second.run()
        thread.join(2)

        self.assertEqual(second._hardening_metrics.concurrency_rejected, 1)
        self.assertTrue(signals)
        self.assertEqual(first._hardening_metrics.timed_out, 1)

    def test_tool_plan_timeout_and_cancellation_block_only_pending_steps(self):
        executor = ToolPlanExecutor(
            ToolDispatcher(ToolRegistry((_SlowTool(),))),
            ExecutionHardeningConfigDTO(timeout_ms=1),
        )
        timed_out = executor.execute(self._plan())

        self.assertEqual([item.status for item in timed_out.step_results], ["success", "blocked"])
        self.assertEqual(executor._hardening_metrics.timed_out, 1)

        entered = threading.Event()
        executor = ToolPlanExecutor(ToolDispatcher(ToolRegistry((_SlowTool(entered),))))
        holder = []
        thread = threading.Thread(target=lambda: holder.append(executor.execute(self._plan())))
        thread.start()
        self.assertTrue(entered.wait(1))
        executor.cancel()
        thread.join(2)

        self.assertEqual([item.status for item in holder[0].step_results], ["success", "blocked"])
        self.assertEqual(executor._hardening_metrics.cancelled, 1)

    def test_tool_plan_rejects_parallel_execution_without_cross_task_failure(self):
        entered = threading.Event()
        executor = ToolPlanExecutor(ToolDispatcher(ToolRegistry((_SlowTool(entered),))))
        thread = threading.Thread(target=lambda: executor.execute(self._plan()))
        thread.start()
        self.assertTrue(entered.wait(1))
        with self.assertRaises(ToolPlanExecutionError):
            executor.execute(self._plan())
        thread.join(2)

        self.assertEqual(executor._hardening_metrics.concurrency_rejected, 1)
