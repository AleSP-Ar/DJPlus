import tempfile
import unittest
import wave
import math
from pathlib import Path

from app.services.audio_analysis_service import AudioAnalysisError, AudioAnalysisQueryDTO, MusicAnalysisService


class _Token:
    def __init__(self, cancelled=False): self.cancelled = cancelled
    def is_cancelled(self): return self.cancelled


class _CancelAfter:
    def __init__(self, calls): self.calls, self.count = calls, 0
    def is_cancelled(self):
        self.count += 1
        return self.count >= self.calls


class AudioAnalysisServiceTests(unittest.TestCase):
    def _wav(self, directory, name="audio.wav"):
        path = Path(directory) / name
        with wave.open(str(path), "wb") as source:
            source.setnchannels(2); source.setsampwidth(2); source.setframerate(8000)
            source.writeframes((b"\xff\x7f" + b"\x00\x00") * 800)
        return path

    def test_analyzes_deterministic_pcm_features_and_keeps_future_features_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            result = MusicAnalysisService().analyze(AudioAnalysisQueryDTO(str(self._wav(directory))))
        self.assertEqual(result.status, "completed")
        self.assertEqual((result.features.sample_rate, result.features.channels), (8000, 2))
        self.assertAlmostEqual(result.features.duration_seconds, 0.1)
        self.assertEqual(result.features.peak, 1.0)
        self.assertIsNone(result.features.bpm)

    def test_rejects_bad_paths_formats_and_corrupt_wav(self):
        with self.assertRaises(AudioAnalysisError): MusicAnalysisService().analyze(AudioAnalysisQueryDTO("missing.mp3"))
        with self.assertRaises(AudioAnalysisError): MusicAnalysisService().analyze(AudioAnalysisQueryDTO("missing.wav"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.wav"; path.write_bytes(b"not wav")
            with self.assertRaises(AudioAnalysisError): MusicAnalysisService().analyze(AudioAnalysisQueryDTO(str(path)))

    def test_cancellation_returns_typed_explanation_without_partial_result(self):
        with tempfile.TemporaryDirectory() as directory:
            result = MusicAnalysisService().analyze(AudioAnalysisQueryDTO(str(self._wav(directory)), _Token(True)))
        self.assertEqual(result.status, "cancelled")
        self.assertIsNone(result.features)

    def test_extracts_rms_energy_and_tempo_from_synthetic_stereo_pulses(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pulses.wav"
            self._pulse_wav(path, seconds=8, stereo=True)
            result = MusicAnalysisService().analyze(AudioAnalysisQueryDTO(str(path)))
        self.assertGreater(result.energy_analysis.rms, 0)
        self.assertGreater(result.features.energy, 0)
        self.assertIsNotNone(result.features.bpm)
        self.assertAlmostEqual(result.features.bpm, 120, delta=8)
        self.assertGreaterEqual(result.tempo_analysis.confidence, 0.55)

    def test_silence_short_audio_and_mid_stream_cancellation_remain_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            silent = Path(directory) / "silent.wav"; self._pulse_wav(silent, seconds=4, amplitude=0)
            short = Path(directory) / "short.wav"; self._pulse_wav(short, seconds=1)
            long = Path(directory) / "long.wav"; self._pulse_wav(long, seconds=8)
            silent_result = MusicAnalysisService().analyze(AudioAnalysisQueryDTO(str(silent)))
            short_result = MusicAnalysisService().analyze(AudioAnalysisQueryDTO(str(short)))
            cancelled = MusicAnalysisService().analyze(AudioAnalysisQueryDTO(str(long), _CancelAfter(3)))
        self.assertIsNone(silent_result.features.bpm)
        self.assertIn("silencioso", silent_result.tempo_analysis.explanation)
        self.assertIsNone(short_result.features.bpm)
        self.assertEqual(cancelled.status, "cancelled")

    def test_detects_normalized_major_and_minor_keys_from_synthetic_chords(self):
        with tempfile.TemporaryDirectory() as directory:
            major = Path(directory) / "c_major.wav"; self._chord_wav(major, (261.63, 329.63, 392.0), stereo=True)
            minor = Path(directory) / "a_minor.wav"; self._chord_wav(minor, (220.0, 261.63, 329.63))
            major_result = MusicAnalysisService().analyze(AudioAnalysisQueryDTO(str(major)))
            minor_result = MusicAnalysisService().analyze(AudioAnalysisQueryDTO(str(minor)))
        self.assertEqual(major_result.features.key, "C major")
        self.assertEqual(major_result.key_analysis.root, "C")
        self.assertEqual(major_result.key_analysis.mode, "major")
        self.assertEqual(minor_result.features.key, "A minor")
        self.assertEqual(len(major_result.chroma_analysis.profile), 12)

    def test_key_is_absent_for_silence_short_audio_and_cooperative_cancellation(self):
        with tempfile.TemporaryDirectory() as directory:
            silent = Path(directory) / "silent_key.wav"; self._chord_wav(silent, (), seconds=3)
            short = Path(directory) / "short_key.wav"; self._chord_wav(short, (261.63, 329.63, 392.0), seconds=1)
            long = Path(directory) / "long_key.wav"; self._chord_wav(long, (261.63, 329.63, 392.0), seconds=5)
            silent_result = MusicAnalysisService().analyze(AudioAnalysisQueryDTO(str(silent)))
            short_result = MusicAnalysisService().analyze(AudioAnalysisQueryDTO(str(short)))
            cancelled = MusicAnalysisService().analyze(AudioAnalysisQueryDTO(str(long), _CancelAfter(10)))
        self.assertIsNone(silent_result.features.key)
        self.assertIsNone(short_result.features.key)
        self.assertEqual(cancelled.status, "cancelled")

    def _pulse_wav(self, path, seconds, amplitude=20000, stereo=False):
        sample_rate, frames = 8000, int(seconds * 8000)
        samples = bytearray()
        for index in range(frames):
            value = amplitude if index % 4000 < 120 else 0
            encoded = int(value).to_bytes(2, "little", signed=True)
            samples.extend(encoded * (2 if stereo else 1))
        with wave.open(str(path), "wb") as source:
            source.setnchannels(2 if stereo else 1); source.setsampwidth(2); source.setframerate(sample_rate)
            source.writeframes(bytes(samples))

    def _chord_wav(self, path, frequencies, seconds=3, stereo=False):
        sample_rate, frames, amplitude = 8000, int(seconds * 8000), 7000
        samples = bytearray()
        for index in range(frames):
            value = sum(math.sin(2 * math.pi * frequency * index / sample_rate) for frequency in frequencies)
            encoded = int(max(-32768, min(32767, value * amplitude))).to_bytes(2, "little", signed=True)
            samples.extend(encoded * (2 if stereo else 1))
        with wave.open(str(path), "wb") as source:
            source.setnchannels(2 if stereo else 1); source.setsampwidth(2); source.setframerate(sample_rate)
            source.writeframes(bytes(samples))
