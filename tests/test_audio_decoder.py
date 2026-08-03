import aifc
import math
import tempfile
import unittest
import wave
from pathlib import Path

from app.services.audio_analysis_service import AudioAnalysisError, AudioAnalysisQueryDTO, MusicAnalysisService
from app.services.audio_decoder import (
    AIFFPCMDecoder,
    AudioDecoderError,
    AudioDecoderRegistry,
    CorruptAudioFileError,
    UnsupportedAudioFormatError,
    WAVPCMDecoder,
)


class _CancelAfter:
    def __init__(self, calls):
        self.calls, self.count = calls, 0

    def is_cancelled(self):
        self.count += 1
        return self.count >= self.calls


class AudioDecoderTests(unittest.TestCase):
    def _pcm(self, frames, channels, byteorder):
        values = bytearray()
        for index in range(frames):
            sample = int(12000 * math.sin(2 * math.pi * index / 32))
            encoded = sample.to_bytes(2, byteorder, signed=True)
            values.extend(encoded * channels)
        return bytes(values)

    def _wav(self, directory, name="tone.wav", rate=11025, channels=1, frames=2205):
        path = Path(directory) / name
        with wave.open(str(path), "wb") as output:
            output.setnchannels(channels); output.setsampwidth(2); output.setframerate(rate)
            output.writeframes(self._pcm(frames, channels, "little"))
        return path

    def _aiff(self, directory, name="tone.aif", rate=8000, channels=2, frames=1600):
        path = Path(directory) / name
        with aifc.open(str(path), "wb") as output:
            output.setnchannels(channels); output.setsampwidth(2); output.setframerate(rate)
            output.writeframes(self._pcm(frames, channels, "big"))
        return path

    def test_registry_detects_content_before_extension_and_rejects_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            wav = self._wav(directory, "renamed.aiff")
            registry = AudioDecoderRegistry.default()
            self.assertEqual(registry.detect(str(wav)).audio_format.name, "wav")
            with self.assertRaises(AudioDecoderError):
                registry.register(WAVPCMDecoder())

    def test_wav_and_aiff_decode_bounded_normalized_blocks_and_preserve_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            wav, aiff = self._wav(directory), self._aiff(directory, name="stereo.aiff")
            registry = AudioDecoderRegistry.default()
            wav_info, wav_blocks = registry.decode(str(wav), 128)
            aiff_info, aiff_blocks = registry.decode(str(aiff), 128)
            wav_blocks, aiff_blocks = tuple(wav_blocks), tuple(aiff_blocks)
        self.assertEqual((wav_info.audio_format.name, wav_info.channels, wav_info.sample_rate), ("wav", 1, 11025))
        self.assertEqual((aiff_info.audio_format.name, aiff_info.channels, aiff_info.sample_rate), ("aiff", 2, 8000))
        self.assertTrue(all(0 < block.frame_count <= 128 for block in wav_blocks + aiff_blocks))
        self.assertTrue(all(-1 <= sample <= 1 for block in wav_blocks + aiff_blocks for sample in block.samples))
        self.assertEqual(aiff_blocks[0].frame_count * 2, len(aiff_blocks[0].samples))

    def test_music_analysis_service_integrates_aiff_and_wav_decoders(self):
        with tempfile.TemporaryDirectory() as directory:
            wav, aiff = self._wav(directory), self._aiff(directory)
            wav_result = MusicAnalysisService().analyze(AudioAnalysisQueryDTO(str(wav)))
            aiff_result = MusicAnalysisService().analyze(AudioAnalysisQueryDTO(str(aiff)))
        self.assertEqual((wav_result.features.sample_rate, wav_result.features.channels), (11025, 1))
        self.assertEqual((aiff_result.features.sample_rate, aiff_result.features.channels), (8000, 2))
        self.assertGreater(aiff_result.features.peak, 0)

    def test_service_accepts_an_injected_decoder_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            aiff = self._aiff(directory)
            service = MusicAnalysisService(decoder_registry=AudioDecoderRegistry((AIFFPCMDecoder(),)))
            result = service.analyze(AudioAnalysisQueryDTO(str(aiff)))
        self.assertEqual(result.features.channels, 2)

    def test_typed_corrupt_unsupported_and_cooperative_cancellation_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "bad.aif"; bad.write_bytes(b"FORM\x00\x00\x00\x04AIFFbad")
            unsupported = Path(directory) / "audio.mp3"; unsupported.write_bytes(b"ID3")
            long = self._wav(directory, name="long.wav", frames=12000)
            registry = AudioDecoderRegistry.default()
            with self.assertRaises(CorruptAudioFileError):
                registry.decode(str(bad), 64)[0]
            with self.assertRaises(UnsupportedAudioFormatError):
                registry.detect(str(unsupported))
            token = _CancelAfter(3)
            _info, blocks = registry.decode(str(long), 64, token)
            self.assertLess(len(tuple(blocks)), 12000 // 64)
            result = MusicAnalysisService().analyze(AudioAnalysisQueryDTO(str(long), _CancelAfter(3)))
        self.assertEqual(result.status, "cancelled")
        with self.assertRaises(AudioAnalysisError):
            MusicAnalysisService().analyze(AudioAnalysisQueryDTO(str(unsupported)))
