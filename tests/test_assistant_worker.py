import time
import unittest

from PySide6.QtWidgets import QApplication

from app.services.local_assistant_mvp import LocalAssistantMVP
from app.services.provider_transport import MockProviderTransport
from app.ui.assistant_panel import AssistantPanel
from app.ui.assistant_worker import AssistantWorker


class _LibraryServiceDouble:
    def count_tracks(self):
        return 3


def _mvp(transport=None):
    return LocalAssistantMVP(
        _LibraryServiceDouble(),
        transport=transport or MockProviderTransport(json_body={"message": {"content": "Respuesta local"}}),
    )


class AssistantWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def _run_worker(self, worker):
        signals = []
        worker.started.connect(lambda: signals.append("started"))
        worker.result.connect(lambda result: signals.append(("result", result)))
        worker.error.connect(lambda message: signals.append(("error", message)))
        worker.cancelled.connect(lambda: signals.append("cancelled"))
        worker.finished.connect(lambda: signals.append("finished"))
        worker.run()
        return signals

    def test_worker_emits_started_result_and_finished_for_mocked_read_only_query(self):
        signals = self._run_worker(AssistantWorker(_mvp(), "consultar biblioteca"))

        self.assertEqual(signals[0], "started")
        self.assertEqual(signals[-1], "finished")
        result = next(value for value in signals if isinstance(value, tuple) and value[0] == "result")[1]
        self.assertEqual(result.assistant_response.content, "Respuesta local")

    def test_worker_emits_cancelled_and_finished_without_contacting_provider(self):
        worker = AssistantWorker(_mvp(), "cancelar")
        worker.cancel()

        signals = self._run_worker(worker)

        self.assertEqual(signals, ["started", "cancelled", "finished"])

    def test_worker_emits_typed_provider_error_and_finished(self):
        worker = AssistantWorker(_mvp(MockProviderTransport(scenario="unavailable")), "fallar")

        signals = self._run_worker(worker)

        self.assertEqual(signals[0], "started")
        self.assertEqual(signals[-1], "finished")
        self.assertTrue(any(isinstance(value, tuple) and value[0] == "error" for value in signals))

    def test_panel_exposes_non_blocking_controls_before_a_query_starts(self):
        panel = AssistantPanel(_mvp())
        self.assertTrue(panel.send_button.isEnabled())
        self.assertFalse(panel.cancel_button.isEnabled())
        self.assertEqual(panel.status_label.text(), "Listo")
        panel.close()

    def test_worker_benchmark_processes_50_mocked_queries_without_ui_thread_wait(self):
        started = time.perf_counter()
        completed = []
        for _ in range(50):
            worker = AssistantWorker(_mvp(), "benchmark")
            worker.result.connect(lambda result: completed.append(result))
            worker.run()

        self.assertEqual(len(completed), 50)
        self.assertLess(time.perf_counter() - started, 2.0)
