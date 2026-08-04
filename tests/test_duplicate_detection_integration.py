import os
import time
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qt_test_helpers import ensure_qapplication
from app.database import init_database
from app.services.duplicate_detection_facade import (
    DuplicateDetectionFacade,
    DuplicateDetectionWorker,
    DuplicateProgressDTO,
)
from app.services.duplicate_detection_service import (
    DuplicateDetectionResultDTO,
    DuplicateFingerprintDTO,
    DuplicateGroupDTO,
    DuplicateScanQueryDTO,
)
from app.services.duplicate_detection_tool import DuplicateDetectionTool
from app.services.tool_dispatcher import ToolRegistry
from app.ui.main_window import MainWindow


class _Rows:
    def __init__(self, rows=()):
        self.rows = tuple(rows)

    def query(self, text=""):
        return self.rows, False


class _Facade:
    def __init__(self, result):
        self.result = result

    def scan(self, query, on_progress=None):
        if query.cancellation_token is not None and query.cancellation_token.is_cancelled():
            return DuplicateDetectionResultDTO((), (), True)
        if on_progress is not None:
            on_progress(DuplicateProgressDTO(1, 1, 7, "completed"))
        return self.result

    def export_text(self, result):
        return "\n".join(
            [f"cancelled={result.cancelled}; fingerprints={len(result.fingerprints)}"]
            + [
                f"hash={group.content_hash}; tracks={group.track_ids}; files={group.filepaths}; recoverable={group.recoverable_bytes}"
                for group in result.groups
            ]
        )


class DuplicateDetectionIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = ensure_qapplication()

    def _result(self):
        fingerprints = (
            DuplicateFingerprintDTO(7, "one.wav", "a" * 64, 10),
            DuplicateFingerprintDTO(8, "two.wav", "a" * 64, 10),
        )
        return DuplicateDetectionResultDTO(
            fingerprints,
            (DuplicateGroupDTO("a" * 64, (7, 8), ("one.wav", "two.wav"), 10),),
            False,
        )

    def test_tool_registry_registers_duplicate_tool_only_when_facade_is_supplied(self):
        from app.services import DuplicateDetectionTool as PublicDuplicateDetectionTool

        base = ToolRegistry.default(object(), object(), object())
        registry = ToolRegistry.default(
            object(), object(), object(), duplicate_detection_facade=_Facade(self._result())
        )

        self.assertNotIn("duplicate_detection", base.registered_tool_names())
        self.assertEqual(registry.registered_tool_names()[-1], "duplicate_detection")
        self.assertIs(PublicDuplicateDetectionTool, DuplicateDetectionTool)
        self.assertIsInstance(registry.resolve("duplicate_detection"), DuplicateDetectionTool)

    def test_headless_main_window_worker_result_export_and_cancellation_flow(self):
        init_database()
        window = MainWindow()
        self.assertTrue(hasattr(window, "duplicate_detection_facade"))

        facade = _Facade(self._result())
        worker = DuplicateDetectionWorker(facade)
        worker.start(DuplicateScanQueryDTO())
        result = worker.wait(2)
        report = DuplicateDetectionTool(facade).execute({}).data_used["duplicate_report"]

        self.assertFalse(result.cancelled)
        self.assertEqual(worker.events[0].status, "completed")
        self.assertIn("recoverable=10", report)
        self.assertEqual(DuplicateDetectionTool(facade).execute({}).proposed_actions, ())

        cancelled_worker = DuplicateDetectionWorker(facade)
        cancelled_worker.cancel()
        cancelled_worker.start(DuplicateScanQueryDTO())
        self.assertTrue(cancelled_worker.wait(2).cancelled)
        window.close()

    def test_benchmark_handles_1000_simulated_entries_deterministically(self):
        rows = tuple(SimpleNamespace(id=index, filepath=f"simulated/{index}.wav") for index in range(1000))
        fingerprints = tuple(
            DuplicateFingerprintDTO(row.id, row.filepath, f"{row.id % 10:064x}", 4096)
            for row in rows
        )
        groups = tuple(
            DuplicateGroupDTO(f"{index:064x}", tuple(range(index, 1000, 10)), tuple(f"simulated/{track}.wav" for track in range(index, 1000, 10)), 4096 * 99)
            for index in range(10)
        )
        expected = DuplicateDetectionResultDTO(fingerprints, groups, False)

        class _Service:
            def scan(self, query):
                return expected

        facade = DuplicateDetectionFacade(_Rows(rows), _Service())
        started = time.perf_counter()
        first = facade.scan(DuplicateScanQueryDTO())
        second = facade.scan(DuplicateScanQueryDTO())
        elapsed = time.perf_counter() - started

        self.assertEqual(first, second)
        self.assertEqual(len(first.fingerprints), 1000)
        self.assertEqual(tuple(group.content_hash for group in first.groups), tuple(f"{index:064x}" for index in range(10)))
        self.assertLess(elapsed, 2.0)
