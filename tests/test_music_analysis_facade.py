import math
import tempfile
import time
import unittest
import wave
from dataclasses import dataclass
from pathlib import Path

from app.services.library_tools import MusicAnalysisBatchTool
from app.services.music_analysis_facade import MusicAnalysisBatchQueryDTO, MusicAnalysisFacade, MusicAnalysisWorker
from app.services.tool_dispatcher import ToolCallDTO, ToolDispatcher, ToolRegistry


@dataclass(frozen=True)
class _Track:
    id: int
    filepath: str


class _Library:
    def __init__(self, rows): self.rows, self.calls = tuple(rows), 0
    def query(self, text=""):
        self.calls += 1
        return self.rows, False


class MusicAnalysisFacadeTests(unittest.TestCase):
    def _wav(self, path, seconds=3):
        rate = 8000
        data = bytearray()
        for index in range(rate * seconds):
            value = int(7000 * (math.sin(2 * math.pi * 261.63 * index / rate) + math.sin(2 * math.pi * 329.63 * index / rate)))
            data.extend(max(-32768, min(32767, value)).to_bytes(2, "little", signed=True))
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1); output.setsampwidth(2); output.setframerate(rate); output.writeframes(data)

    def test_batch_reads_library_isolates_file_errors_and_exports_report(self):
        with tempfile.TemporaryDirectory() as directory:
            good = Path(directory) / "good.wav"; self._wav(good)
            library = _Library((_Track(1, str(good)), _Track(2, str(Path(directory) / "missing.wav"))))
            progress = []
            result = MusicAnalysisFacade(library).analyze(MusicAnalysisBatchQueryDTO(max_concurrency=2), lambda *event: progress.append(event))
        self.assertEqual(library.calls, 1)
        self.assertEqual(tuple(item.status for item in result.items), ("completed", "error"))
        self.assertGreater(result.items[0].rms, 0)
        self.assertIn("pista=1", result.export_text())
        self.assertEqual(len(progress), 2)

    def test_worker_progress_cancellation_and_read_only_tool_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            good = Path(directory) / "good.wav"; self._wav(good, 4)
            facade = MusicAnalysisFacade(_Library((_Track(1, str(good)),)))
            worker, events = MusicAnalysisWorker(facade), []
            worker.subscribe(lambda *event: events.append(event))
            worker.start(MusicAnalysisBatchQueryDTO())
            result = worker.wait(5)
            tool_result = ToolDispatcher(ToolRegistry((MusicAnalysisBatchTool(facade),))).dispatch(ToolCallDTO("music_analysis_batch", {"track_ids": [1]}))
            worker.cancel()
        self.assertIsNotNone(result)
        self.assertTrue(any(event[0] == "progress" for event in events))
        self.assertTrue(any(event[0] == "finished" for event in events))
        self.assertTrue(tool_result.success)
        self.assertEqual(tool_result.result.proposed_actions, ())
        self.assertIn("music_analysis_report", tool_result.result.data_used)

    def test_default_registry_optionally_registers_batch_analysis_tool(self):
        with tempfile.TemporaryDirectory() as directory:
            good = Path(directory) / "good.wav"; self._wav(good)
            facade = MusicAnalysisFacade(_Library((_Track(1, str(good)),)))
            registry = ToolRegistry.default(_Library(()), object(), object(), music_analysis_facade=facade)
        self.assertIn("music_analysis_batch", registry.registered_tool_names())

    def test_benchmark_analyses_small_in_memory_batch_without_storing_results(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "benchmark.wav"; self._wav(path, 2)
            facade = MusicAnalysisFacade(_Library(tuple(_Track(index, str(path)) for index in range(1, 9))))
            started = time.perf_counter()
            result = facade.analyze(MusicAnalysisBatchQueryDTO(limit=8, max_concurrency=2))
        self.assertEqual(len(result.items), 8)
        self.assertTrue(all(item.status == "completed" for item in result.items))
        self.assertLess(time.perf_counter() - started, 10.0)
