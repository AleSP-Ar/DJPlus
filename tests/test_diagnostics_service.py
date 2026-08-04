import time
import unittest

from qt_test_helpers import ensure_qapplication
from app.services.diagnostics_service import DiagnosticsService, HealthSnapshotDTO
from app.services.execution_hardening import ExecutionEventMetricsDTO
from app.services.library_tools import DiagnosticsTool, LibraryQueryTool
from app.services.local_assistant_mvp import LocalAssistantMVP
from app.services.optimization_metrics import OperationMetricsDTO, StageTimingDTO
from app.services.tool_dispatcher import ToolCallDTO, ToolDispatcher, ToolRegistry
from app.ui.assistant_panel import AssistantPanel


class _Component:
    def __init__(self):
        self._interpretation_cache = {"safe": object()}
        self._last_metrics = OperationMetricsDTO("safe", (StageTimingDTO("total", 1.25),))
        self._hardening_metrics = ExecutionEventMetricsDTO("safe", cancelled=1, timed_out=2, failed=3)
        self.is_running = False


class _Library:
    def count_tracks(self):
        return 0


class DiagnosticsServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = ensure_qapplication()

    def test_snapshot_is_immutable_aggregate_and_export_never_contains_component_data(self):
        snapshot = DiagnosticsService((("worker", _Component()),)).snapshot()

        self.assertIsInstance(snapshot, HealthSnapshotDTO)
        self.assertEqual(snapshot.cache_entries, (("worker.interpretation_cache", 1),))
        self.assertEqual((snapshot.errors, snapshot.cancellations, snapshot.timeouts), (3, 1, 2))
        text = snapshot.export_text()
        self.assertIn("worker=idle", text)
        self.assertNotIn("safe", text)

    def test_diagnostics_tool_is_allowlisted_read_only(self):
        diagnostics = DiagnosticsService((("library", _Component()),))
        registry = ToolRegistry.default(_Library(), object(), object(), diagnostics_service=diagnostics)
        result = ToolDispatcher(registry).dispatch(ToolCallDTO("diagnostics"))

        self.assertTrue(result.success)
        self.assertIn("health_snapshot", result.result.data_used)
        self.assertEqual(result.result.proposed_actions, ())

    def test_panel_renders_compact_optional_diagnostics(self):
        panel = AssistantPanel(LocalAssistantMVP(_Library()), diagnostics_service=DiagnosticsService((("worker", _Component()),)))
        self.assertIn("errores 3", panel.diagnostics_label.text())
        panel.close()

    def test_final_diagnostics_benchmark_scales_with_many_in_memory_components(self):
        diagnostics = DiagnosticsService(tuple((f"component_{index}", _Component()) for index in range(500)))
        started = time.perf_counter()
        snapshot = diagnostics.snapshot()

        self.assertEqual(len(snapshot.cache_entries), 500)
        self.assertLess(time.perf_counter() - started, 1.0)
