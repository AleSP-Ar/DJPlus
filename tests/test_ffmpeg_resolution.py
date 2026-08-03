import io
import tempfile
import unittest
import hashlib
from pathlib import Path

from app.services.audio_decoder import AudioDecoderRegistry, OFFICIAL_AUDIO_FORMAT_ORDER
from app.services.ffmpeg_audio_decoder import (
    FFmpegAudioDecoder,
    FFmpegCapabilityProbe,
    FFmpegDecoderConfigDTO,
    FFmpegProcessError,
    FFmpegResolver,
)


class _Process:
    def __init__(self, stderr=b"", returncode=0):
        self.stdout, self.stderr, self.returncode = io.BytesIO(), io.BytesIO(stderr), returncode

    def communicate(self, timeout=None): return self.stdout.getvalue(), self.stderr.getvalue()
    def wait(self, timeout=None): return self.returncode
    def poll(self): return self.returncode
    def terminate(self): self.returncode = -15
    def kill(self): self.returncode = -9


class _CapabilityFactory:
    def __init__(self, decoders=b" A..... mp3\n A..... flac\n"):
        self.decoders = decoders

    def __call__(self, command, **kwargs):
        if "-version" in command:
            return _Process(b"ffmpeg version resolver-test")
        if "-decoders" in command:
            return _Process(self.decoders)
        return _Process()


class FFmpegResolutionTests(unittest.TestCase):
    def test_configured_path_has_priority_and_reports_version_capabilities(self):
        configured, system = "C:/configured/ffmpeg.exe", "C:/system/ffmpeg.exe"
        config = FFmpegDecoderConfigDTO(executable_path=configured)
        resolver = FFmpegResolver(config, which=lambda _: system, path_exists=lambda value: value in {configured, system})
        decoder = FFmpegAudioDecoder(config, resolver=resolver, capability_probe=FFmpegCapabilityProbe(config, _CapabilityFactory()))
        availability = decoder.availability()
        self.assertEqual((availability.origin, availability.version), ("configured", "resolver-test"))
        self.assertTrue(availability.supports_mp3 and availability.supports_flac)

    def test_system_path_and_bundled_runtime_follow_resolution_priority(self):
        system = "C:/system/ffmpeg.exe"
        with tempfile.TemporaryDirectory() as directory:
            bundled = Path(directory) / "ffmpeg.exe"; bundled.write_bytes(b"bundled-runtime")
            (Path(directory) / "CHECKSUM.sha256").write_text(
                f"{hashlib.sha256(bundled.read_bytes()).hexdigest()}  ffmpeg.exe\n", encoding="utf-8"
            )
            system_resolver = FFmpegResolver(which=lambda _: system, path_exists=lambda value: value == system, bundled_path=str(bundled))
            bundled_resolver = FFmpegResolver(which=lambda _: None, bundled_path=str(bundled))
            self.assertEqual(system_resolver.resolve().origin, "path")
            resolution = bundled_resolver.resolve()
        self.assertEqual(resolution.origin, "bundled")
        self.assertTrue(resolution.checksum_verified)

    def test_invalid_bundled_checksum_is_rejected_without_using_the_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            bundled = Path(directory) / "ffmpeg.exe"; bundled.write_bytes(b"altered-runtime")
            (Path(directory) / "CHECKSUM.sha256").write_text("0" * 64 + "  ffmpeg.exe\n", encoding="utf-8")
            resolution = FFmpegResolver(which=lambda _: None, bundled_path=str(bundled)).resolve()
        self.assertEqual(resolution.origin, "unavailable")
        self.assertIn("Checksum invalido", resolution.error)

    def test_invalid_and_totally_absent_executables_are_typed_unavailable(self):
        config = FFmpegDecoderConfigDTO(executable_path="C:/missing/ffmpeg.exe")
        resolver = FFmpegResolver(config, which=lambda _: None, path_exists=lambda _: False, bundled_path="D:/missing/ffmpeg.exe")
        decoder = FFmpegAudioDecoder(config, resolver=resolver, capability_probe=FFmpegCapabilityProbe(config, _CapabilityFactory()))
        availability = decoder.availability()
        self.assertFalse(availability.available)
        self.assertEqual(availability.origin, "unavailable")
        self.assertIn("configurada", availability.reason)

    def test_mp3_capability_is_required_before_audio_decode(self):
        executable = "C:/configured/ffmpeg.exe"
        config = FFmpegDecoderConfigDTO(executable_path=executable)
        resolver = FFmpegResolver(config, which=lambda _: None, path_exists=lambda value: value == executable)
        decoder = FFmpegAudioDecoder(config, resolver=resolver, capability_probe=FFmpegCapabilityProbe(config, _CapabilityFactory(b" A..... flac\n")))
        with tempfile.TemporaryDirectory() as directory:
            mp3 = Path(directory) / "fixture.mp3"; mp3.write_bytes(b"ID3fixture")
            with self.assertRaises(FFmpegProcessError):
                decoder.probe(str(mp3))
        self.assertFalse(decoder.availability().supports_mp3)
        self.assertTrue(decoder.availability().supports_flac)

    def test_official_format_order_is_used_by_registry_exports(self):
        registry = AudioDecoderRegistry.default(ffmpeg_decoder=FFmpegAudioDecoder(which=lambda _: None))
        self.assertEqual(OFFICIAL_AUDIO_FORMAT_ORDER, ("mp3", "flac", "aiff", "wav"))
        self.assertEqual(registry.supported_format_names(), OFFICIAL_AUDIO_FORMAT_ORDER)
        self.assertEqual(registry.supported_extensions(), (".mp3", ".flac", ".aif", ".aiff", ".wav"))
