import aifc
import io
import math
import os
import shutil
import subprocess
import tempfile
import time
import unittest
import wave
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qt_test_helpers import ensure_qapplication
from app.database import init_database
from app.services.audio_decoder import AudioDecoderRegistry
from app.services.ffmpeg_audio_decoder import FFmpegAudioDecoder, FFmpegDecoderConfigDTO, FFmpegResolver
from app.services.library_tools import MusicAnalysisBatchTool
from app.services.multi_format_audio_analysis_facade import MultiFormatAudioAnalysisFacade
from app.services.music_analysis_facade import MusicAnalysisBatchQueryDTO
from app.ui.main_window import MainWindow


_PROBE = b"Input #0, mp3, from 'fixture.mp3':\n  Duration: 00:00:00.10, start: 0.0\n  Stream #0:0: Audio: mp3, 8000 Hz, mono, s16p\n"
_VERSION = b"ffmpeg version test-build"
_DECODERS = b" A..... mp3\n A..... flac\n"
_BUNDLED_FFMPEG = Path(__file__).resolve().parents[1] / "runtime" / "ffmpeg" / "ffmpeg.exe"


class _Process:
    def __init__(self, stdout=b"", stderr=b"", returncode=0, timeout=False):
        self.stdout, self.stderr = io.BytesIO(stdout), io.BytesIO(stderr)
        self.returncode, self.timeout, self._finished = returncode, timeout, False

    def communicate(self, timeout=None):
        if self.timeout and not self._finished:
            raise subprocess.TimeoutExpired("ffmpeg", timeout)
        self._finished = True
        return b"", self.stderr.getvalue()

    def wait(self, timeout=None):
        if self.timeout and not self._finished:
            raise subprocess.TimeoutExpired("ffmpeg", timeout)
        self._finished = True
        return self.returncode

    def poll(self):
        return self.returncode if self._finished else None

    def terminate(self): self.returncode, self._finished = -15, True
    def kill(self): self.returncode, self._finished = -9, True


class _Factory:
    def __init__(self, raw=b"\x00\x00\xff\x7f", timeout_decode=False):
        self.raw, self.timeout_decode = raw, timeout_decode

    def __call__(self, command, **kwargs):
        if "-version" in command:
            return _Process(stderr=_VERSION)
        if "-decoders" in command:
            return _Process(stderr=_DECODERS)
        probe = "-frames:a" in command
        return _Process(b"" if probe else self.raw, _PROBE if probe else b"", timeout=False if probe else self.timeout_decode)


@dataclass(frozen=True)
class _Track:
    id: int
    filepath: str


class _Library:
    def __init__(self, rows): self.rows = tuple(rows)
    def query(self, text=""): return self.rows, False


class _Cancelled:
    def is_cancelled(self): return True


class MultiFormatAudioAnalysisFacadeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = ensure_qapplication()

    def _pcm(self, frames=800, channels=1, order="little"):
        data = bytearray()
        for index in range(frames):
            value = int(9000 * math.sin(2 * math.pi * index / 32))
            data.extend(value.to_bytes(2, order, signed=True) * channels)
        return bytes(data)

    def _wav(self, directory, name="tone.wav"):
        path = Path(directory) / name
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1); output.setsampwidth(2); output.setframerate(8000); output.writeframes(self._pcm())
        return path

    def _aiff(self, directory, name="tone.aif"):
        path = Path(directory) / name
        with aifc.open(str(path), "wb") as output:
            output.setnchannels(2); output.setsampwidth(2); output.setframerate(8000); output.writeframes(self._pcm(channels=2, order="big"))
        return path

    def _ffmpeg_registry(self, directory, factory=None):
        executable = Path(directory) / "ffmpeg.exe"; executable.write_bytes(b"")
        decoder = FFmpegAudioDecoder(
            FFmpegDecoderConfigDTO(executable_path=str(executable), timeout_seconds=1),
            process_factory=factory or _Factory(),
        )
        return AudioDecoderRegistry.default(ffmpeg_decoder=decoder)

    def test_end_to_end_wav_aiff_wrong_extension_tool_and_text_export(self):
        with tempfile.TemporaryDirectory() as directory:
            wav = self._wav(directory, "wrong.mp3")
            aiff = self._aiff(directory)
            facade = MultiFormatAudioAnalysisFacade(_Library((_Track(1, str(wav)), _Track(2, str(aiff)))), decoder_registry=AudioDecoderRegistry.default())
            result = facade.analyze(MusicAnalysisBatchQueryDTO())
            tool_result = MusicAnalysisBatchTool(facade).execute({})
        self.assertEqual(tuple(item.audio_format for item in result.items), ("wav", "aiff"))
        self.assertEqual(tuple(item.decoder for item in result.items), ("wav", "aiff"))
        self.assertIn("format=wav; decoder=wav", result.export_text())
        self.assertIn("music_analysis_report", tool_result.data_used)

    def test_mixed_mp3_flac_simulated_ffmpeg_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            mp3 = Path(directory) / "one.mp3"; mp3.write_bytes(b"ID3fixture")
            flac = Path(directory) / "two.flac"; flac.write_bytes(b"fLaCfixture")
            registry = self._ffmpeg_registry(directory)
            result = MultiFormatAudioAnalysisFacade(_Library((_Track(1, str(mp3)), _Track(2, str(flac)))), decoder_registry=registry).analyze(MusicAnalysisBatchQueryDTO())
        self.assertEqual(tuple(item.status for item in result.items), ("completed", "completed"))
        self.assertEqual(tuple(item.audio_format for item in result.items), ("mp3", "flac"))
        self.assertTrue(all(item.decoder == "ffmpeg" and item.analyzer_version for item in result.items))
        self.assertTrue(result.diagnostics.ffmpeg_availability.available)

    def test_corrupt_cancellation_timeout_and_unavailable_ffmpeg_are_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            corrupt = Path(directory) / "bad.aif"; corrupt.write_bytes(b"FORM\x00\x00\x00\x04AIFFbad")
            mp3 = Path(directory) / "timeout.mp3"; mp3.write_bytes(b"ID3fixture")
            timeout_registry = self._ffmpeg_registry(directory, _Factory(timeout_decode=True))
            timeout_result = MultiFormatAudioAnalysisFacade(_Library((_Track(1, str(corrupt)), _Track(2, str(mp3)))), decoder_registry=timeout_registry).analyze(MusicAnalysisBatchQueryDTO())
            cancelled = MultiFormatAudioAnalysisFacade(_Library((_Track(3, str(mp3)),)), decoder_registry=timeout_registry).analyze(MusicAnalysisBatchQueryDTO(cancellation_token=_Cancelled()))
            unavailable_config = FFmpegDecoderConfigDTO(executable_path=str(Path(directory) / "missing.exe"))
            unavailable_decoder = FFmpegAudioDecoder(
                unavailable_config,
                resolver=FFmpegResolver(unavailable_config, which=lambda _: None, path_exists=lambda _: False, bundled_path=str(Path(directory) / "missing-runtime.exe")),
            )
            unavailable = MultiFormatAudioAnalysisFacade(_Library((_Track(4, str(mp3)),)), decoder_registry=AudioDecoderRegistry.default(ffmpeg_decoder=unavailable_decoder)).analyze(MusicAnalysisBatchQueryDTO())
        self.assertEqual(tuple(item.status for item in timeout_result.items), ("error", "error"))
        self.assertIn("timeout", timeout_result.items[1].error)
        self.assertEqual(cancelled.items[0].status, "cancelled")
        self.assertFalse(unavailable.diagnostics.ffmpeg_availability.available)
        self.assertEqual(unavailable.items[0].status, "error")

    def test_benchmark_mixed_batch_and_headless_main_window_integration(self):
        with tempfile.TemporaryDirectory() as directory:
            wav, aiff = self._wav(directory), self._aiff(directory)
            mp3 = Path(directory) / "fixture.mp3"; mp3.write_bytes(b"ID3fixture")
            registry = self._ffmpeg_registry(directory)
            tracks = tuple(_Track(index, str((wav, aiff, mp3)[(index - 1) % 3])) for index in range(1, 31))
            facade = MultiFormatAudioAnalysisFacade(_Library(tracks), decoder_registry=registry)
            started = time.perf_counter(); result = facade.analyze(MusicAnalysisBatchQueryDTO(limit=30, max_concurrency=2)); elapsed = time.perf_counter() - started
        init_database(); window = MainWindow()
        self.assertEqual(len(result.items), 30)
        self.assertLess(elapsed, 8)
        self.assertTrue(hasattr(window, "multi_format_audio_analysis_facade"))
        self.assertIsNotNone(window.multi_format_audio_analysis_facade.diagnostics())
        window.close()

    @unittest.skipUnless(_BUNDLED_FFMPEG.is_file(), "El runtime FFmpeg bundled no esta disponible")
    def test_real_bundled_ffmpeg_mp3_flac_corrupt_inputs_and_pipeline_fields(self):
        executable = str(_BUNDLED_FFMPEG)
        with tempfile.TemporaryDirectory() as directory:
            wav = self._wav(directory)
            mp3, flac = Path(directory) / "real.mp3", Path(directory) / "real.flac"
            for target in (mp3, flac):
                subprocess.run([executable, "-y", "-v", "error", "-i", str(wav), str(target)], check=True)
            bundled = FFmpegAudioDecoder(resolver=FFmpegResolver(which=lambda _: None))
            registry = AudioDecoderRegistry.default(ffmpeg_decoder=bundled)
            result = MultiFormatAudioAnalysisFacade(
                _Library((_Track(1, str(mp3)), _Track(2, str(flac)))),
                decoder_registry=registry,
            ).analyze(MusicAnalysisBatchQueryDTO())
            corrupt_result = MultiFormatAudioAnalysisFacade(
                _Library((_Track(3, str(Path(directory) / "bad.mp3")), _Track(4, str(Path(directory) / "bad.flac")))),
                decoder_registry=registry,
            )
            (Path(directory) / "bad.mp3").write_bytes(b"ID3corrupt")
            (Path(directory) / "bad.flac").write_bytes(b"fLaCcorrupt")
            corrupt = corrupt_result.analyze(MusicAnalysisBatchQueryDTO())
        self.assertEqual(tuple(item.status for item in result.items), ("completed", "completed"))
        self.assertEqual((result.diagnostics.ffmpeg_availability.origin, result.diagnostics.ffmpeg_availability.checksum_verified), ("bundled", True))
        for item in result.items:
            self.assertIsNotNone(item.audio_format); self.assertEqual(item.decoder, "ffmpeg")
            self.assertIsNotNone(item.duration_seconds); self.assertIsNotNone(item.peak); self.assertIsNotNone(item.rms)
            self.assertIsNotNone(item.energy); self.assertTrue(hasattr(item, "bpm") and hasattr(item, "key"))
            self.assertTrue(hasattr(item, "tempo_confidence") and hasattr(item, "key_confidence"))
        self.assertEqual(tuple(item.status for item in corrupt.items), ("error", "error"))
