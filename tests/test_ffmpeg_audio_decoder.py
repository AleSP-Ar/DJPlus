import io
import subprocess
import tempfile
import unittest
from pathlib import Path

from app.services.audio_analysis_service import AudioAnalysisError, AudioAnalysisQueryDTO, MusicAnalysisService
from app.services.audio_decoder import AudioDecoderRegistry
from app.services.ffmpeg_audio_decoder import (
    FFmpegAudioDecoder,
    FFmpegDecoderConfigDTO,
    FFmpegProcessError,
    FFmpegResolver,
)


_PROBE = b"Input #0, mp3, from 'fixture.mp3':\n  Duration: 00:00:01.00, start: 0.0\n  Stream #0:0: Audio: mp3, 8000 Hz, mono, s16p\n"
_VERSION = b"ffmpeg version test-build"
_DECODERS = b" A..... mp3\n A..... flac\n"


class _Process:
    def __init__(self, stdout=b"", stderr=b"", returncode=0, timeout=False):
        self.stdout, self.stderr = io.BytesIO(stdout), io.BytesIO(stderr)
        self.returncode, self.timeout, self.terminated, self.killed = returncode, timeout, False, False
        self._finished = False

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

    def terminate(self):
        self.terminated = True
        self.returncode = -15
        self._finished = True

    def kill(self):
        self.killed = True
        self.returncode = -9
        self._finished = True


class _Factory:
    def __init__(self, raw=b"", probe=_PROBE, decode_returncode=0, decode_stderr=b"", timeout_decode=False):
        self.raw, self.probe, self.decode_returncode = raw, probe, decode_returncode
        self.decode_stderr, self.timeout_decode, self.processes = decode_stderr, timeout_decode, []

    def __call__(self, command, **kwargs):
        if "-version" in command:
            process = _Process(stderr=_VERSION)
        elif "-decoders" in command:
            process = _Process(stderr=_DECODERS)
        else:
            process = _Process(
            stderr=self.probe if "-frames:a" in command else self.decode_stderr,
            stdout=b"" if "-frames:a" in command else self.raw,
            returncode=0 if "-frames:a" in command else self.decode_returncode,
            timeout=False if "-frames:a" in command else self.timeout_decode,
            )
        self.processes.append(process)
        return process


class _Cancelled:
    def is_cancelled(self):
        return True


class FFmpegAudioDecoderTests(unittest.TestCase):
    def _fixture(self, directory, name, content):
        path = Path(directory) / name
        path.write_bytes(content)
        return path

    def _decoder(self, factory, executable):
        return FFmpegAudioDecoder(
            FFmpegDecoderConfigDTO(executable_path=str(executable), timeout_seconds=1),
            process_factory=factory,
        )

    def test_unavailable_ffmpeg_is_typed_and_never_downloaded(self):
        decoder = FFmpegAudioDecoder(
            which=lambda _: None,
            resolver=FFmpegResolver(which=lambda _: None, path_exists=lambda _: False, bundled_path="missing-runtime.exe"),
        )
        availability = decoder.availability()
        self.assertFalse(availability.available)
        with self.assertRaises(FFmpegProcessError):
            decoder.probe("missing.mp3")

    def test_registry_optionally_detects_mp3_and_flac_by_content_or_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = self._fixture(directory, "ffmpeg.exe", b"")
            mp3 = self._fixture(directory, "renamed.bin", b"ID3fixture")
            flac = self._fixture(directory, "fixture.flac", b"fLaCfixture")
            decoder = self._decoder(_Factory(), executable)
            registry = AudioDecoderRegistry.default(ffmpeg_decoder=decoder)
            self.assertEqual(registry.detect(str(mp3)).audio_format.name, "ffmpeg")
            self.assertEqual(registry.detect(str(flac)).audio_format.name, "ffmpeg")
            flac_info, _blocks = registry.decode(str(flac), 64)
            self.assertEqual(flac_info.audio_format.name, "flac")
            self.assertNotIn("ffmpeg", AudioDecoderRegistry.default()._decoders)

    def test_streams_pcm_blocks_and_integrates_with_audio_analysis_service(self):
        raw = b"\x00\x00\xff\x7f\x00\x80\x00\x00"
        with tempfile.TemporaryDirectory() as directory:
            executable = self._fixture(directory, "ffmpeg.exe", b"")
            mp3 = self._fixture(directory, "fixture.mp3", b"ID3fixture")
            factory = _Factory(raw)
            decoder = self._decoder(factory, executable)
            registry = AudioDecoderRegistry.default(ffmpeg_decoder=decoder)
            info, blocks = registry.decode(str(mp3), 2)
            blocks = tuple(blocks)
            result = MusicAnalysisService(decoder_registry=registry).analyze(AudioAnalysisQueryDTO(str(mp3)))
        self.assertEqual((info.audio_format.name, info.sample_rate, info.channels), ("mp3", 8000, 1))
        self.assertEqual(tuple(block.frame_count for block in blocks), (2, 2))
        self.assertTrue(all(-1 <= sample <= 1 for block in blocks for sample in block.samples))
        self.assertEqual(result.status, "completed")
        self.assertAlmostEqual(result.features.duration_seconds, 1.0)

    def test_cancellation_timeout_and_safe_stderr_close_the_process(self):
        raw = b"\x00\x00" * 32
        with tempfile.TemporaryDirectory() as directory:
            executable = self._fixture(directory, "ffmpeg.exe", b"")
            mp3 = self._fixture(directory, "secret.mp3", b"ID3fixture")
            cancelled_factory = _Factory(raw)
            decoder = self._decoder(cancelled_factory, executable)
            self.assertEqual(tuple(decoder.iter_blocks(str(mp3), 4, _Cancelled())), ())
            self.assertTrue(cancelled_factory.processes[-1].terminated)

            failed_factory = _Factory(raw, decode_returncode=1, decode_stderr=f"{mp3} token=supersecret".encode())
            failed_decoder = self._decoder(failed_factory, executable)
            with self.assertRaises(FFmpegProcessError) as error:
                tuple(failed_decoder.iter_blocks(str(mp3), 64))
            self.assertNotIn("supersecret", error.exception.safe_stderr)
            self.assertNotIn(str(mp3), error.exception.safe_stderr)

            timeout_factory = _Factory(b"", timeout_decode=True)
            timeout_decoder = self._decoder(timeout_factory, executable)
            with self.assertRaises(FFmpegProcessError):
                tuple(timeout_decoder.iter_blocks(str(mp3), 64))
            self.assertTrue(timeout_factory.processes[-1].terminated)

        with self.assertRaises(AudioAnalysisError):
            MusicAnalysisService(decoder_registry=AudioDecoderRegistry.default()).analyze(AudioAnalysisQueryDTO("fixture.mp3"))
