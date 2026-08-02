import tempfile
import unittest
import wave
from pathlib import Path

from app.services.metadata_service import MetadataReadError, MetadataService


class MetadataServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = MetadataService()

    def test_reads_and_normalizes_a_valid_audio_file(self):
        with tempfile.TemporaryDirectory() as directory:
            filepath = Path(directory) / "Test Track.wav"
            with wave.open(str(filepath), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(44100)
                audio.writeframes(b"\x00\x00" * 4410)

            metadata = self.service.read(filepath)

        self.assertEqual(metadata.title, "Test Track")
        self.assertEqual(metadata.artist, "Unknown")
        self.assertEqual(metadata.sample_rate, 44100)
        self.assertAlmostEqual(metadata.duration, 0.1, places=2)
        self.assertIsNone(metadata.album)
        self.assertIsNone(metadata.genre)
        self.assertIsNone(metadata.bpm)
        self.assertIsNone(metadata.key)

    def test_rejects_missing_and_corrupt_files(self):
        with self.assertRaises(MetadataReadError):
            self.service.read("missing.mp3")

        with tempfile.TemporaryDirectory() as directory:
            filepath = Path(directory) / "corrupt.mp3"
            filepath.write_bytes(b"not an audio file")
            with self.assertRaises(MetadataReadError):
                self.service.read(filepath)
