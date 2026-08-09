import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.metadata_service import MetadataService


class _Audio:
    tags = {"TIT2": ["ID3v2 Title"], "TPE1": ["ID3v2 Artist"]}
    info = None


class MetadataServiceId3Tests(unittest.TestCase):
    def test_embedded_reader_prefers_id3v2_and_falls_back_to_id3v1(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "track.mp3"
            block = b"TAG" + b"ID3v1 Title".ljust(30, b" ") + b"ID3v1 Artist".ljust(30, b" ") + b"ID3v1 Album".ljust(30, b" ") + b"0" * 35
            path.write_bytes(b"audio" + block)
            with patch("app.services.metadata_service.File", return_value=_Audio()):
                metadata = MetadataService().read_embedded(path)
            self.assertEqual((metadata.title, metadata.artist, metadata.album), ("ID3v2 Title", "ID3v2 Artist", "ID3v1 Album"))
