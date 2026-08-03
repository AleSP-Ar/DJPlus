# FFmpeg Distribution, Licenses and Attribution

## Bundled development runtime

The reproducible Windows x64 development runtime is sourced from BtbN/FFmpeg-Builds release `autobuild-2026-08-02-13-17`, artifact `ffmpeg-N-125907-ga7e72069f1-win64-lgpl.zip`. Its published ZIP SHA-256 is `a74ad9068f12355118111a57111d548882c0a59f2520ad3e65188aa52a02ff9c`; the extracted `ffmpeg.exe` SHA-256 is `499e983f598162cde152e8a411fb0f4baf51e7d59f7c0a9a8c65bf313017be4e`. The adjacent runtime files record the exact source, checksums, FFmpeg version and build configuration. `LICENSE.txt`, copied from the verified artifact, identifies GNU LGPL v3.

`FFmpegResolver` uses the fixed priority configured path, system PATH, then bundled runtime. It verifies the bundled executable against `runtime/ffmpeg/CHECKSUM.sha256` before selecting it. A missing, malformed or mismatched bundled checksum produces a typed unavailable resolution and never starts that executable; configured and PATH executables are not treated as bundled distribution artifacts.

## Repository and package strategy

`runtime/ffmpeg/ffmpeg.exe` is 114,863,104 bytes (about 114.9 MB decimal / 109.5 MiB). It exceeds GitHub's regular-Git object limit, so the executable is deliberately ignored by Git. The versioned manifests remain in `runtime/ffmpeg/`; developers place the approved binary locally at that path, and the Windows installer build includes it only after checking the SHA-256 in `CHECKSUM.sha256`. This retains local MP3/FLAC analysis without putting a large binary or a Git LFS pointer in repository history. Do not replace the runtime with a download-at-install or runtime-download mechanism.

## Mandatory runtime update procedure

1. Select an approved Windows x64 FFmpeg release and record its exact provider, tag, artifact and license.
2. Download the artifact and its release checksum through the release process, then compare the ZIP SHA-256 exactly before extraction.
3. Extract only `ffmpeg.exe` and the supplied license to `runtime/ffmpeg`; do not change PATH or install globally.
4. Recalculate `ffmpeg.exe` SHA-256 and update `CHECKSUM.sha256`, `SOURCE.txt`, `VERSION.txt`, `BUILD_CONFIGURATION.txt` and `NOTICE.txt` together.
5. Run `ffmpeg -version`, `ffmpeg -buildconf` and decoder checks for MP3/FLAC, then execute real MP3/FLAC, corrupt-input, bundled-fallback and invalid-checksum tests.
6. Keep `ffmpeg.exe` ignored by Git. During the installer build, verify its checksum, copy it into the installer payload with the six versioned manifest/license files, and record the verification result in the build log.

DJPlus does not download or install FFmpeg at runtime. A Windows installer may distribute an approved `ffmpeg.exe` only at `runtime/ffmpeg/ffmpeg.exe`; the application resolves that existing file after explicit configuration and PATH, without changing global or process PATH.

Before distributing a binary, the release owner must record its source URL or supplier, exact version, build configuration, architecture, checksum, and whether the selected build is LGPL-only or includes GPL-enabled components. The installer and release notes must include the corresponding FFmpeg license notices, required source/offering information, and third-party attribution supplied by that build. Do not state that a generic FFmpeg binary is LGPL-only without validating its configure flags and bundled codecs.

The `FFmpegCapabilityProbe` reports the resolved origin, checksum state and version at runtime for diagnostics only. It does not upload telemetry, validate a binary over the network, alter the executable, or grant a license. If the included binary is missing, has an invalid checksum, lacks MP3/FLAC support, or times out, DJPlus keeps native AIFF/AIF and WAV analysis available and reports a typed local error for FFmpeg formats.
