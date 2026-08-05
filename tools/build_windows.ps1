[CmdletBinding()]
param(
    [string]$Python = ".\.build-venv\Scripts\python.exe",
    [switch]$SkipFfmpegChecksum
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$specPath = Join-Path $projectRoot "packaging\DJPlus.spec"
$runtimePath = Join-Path $projectRoot "runtime\ffmpeg"
$requiredRuntimeFiles = @("ffmpeg.exe", "CHECKSUM.sha256", "LICENSE.txt", "NOTICE.txt", "SOURCE.txt", "VERSION.txt", "BUILD_CONFIGURATION.txt")

foreach ($relative in @("app\main.py", "requirements-build.txt", "packaging\included-files.json", "packaging\DJPlus.spec")) {
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot $relative) -PathType Leaf)) {
        throw "Falta el archivo obligatorio: $relative"
    }
}
foreach ($name in $requiredRuntimeFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $runtimePath $name) -PathType Leaf)) {
        throw "Falta el recurso FFmpeg obligatorio: runtime/ffmpeg/$name"
    }
}
if (-not $SkipFfmpegChecksum) {
    $expected = (Get-Content -LiteralPath (Join-Path $runtimePath "CHECKSUM.sha256") | Where-Object { $_ -match '\sffmpeg\.exe$' } | Select-Object -First 1).Split()[0]
    $actual = (Get-FileHash -LiteralPath (Join-Path $runtimePath "ffmpeg.exe") -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($expected -ne $actual) { throw "El checksum de runtime/ffmpeg/ffmpeg.exe no coincide." }
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw "No se encontró Python de build: $Python" }

foreach ($directory in @("build", "dist")) {
    $target = Join-Path $projectRoot $directory
    if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
}

& $Python -m pip install --requirement (Join-Path $projectRoot "requirements-build.txt")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -m PyInstaller --noconfirm --clean --workpath (Join-Path $projectRoot "build") --distpath (Join-Path $projectRoot "dist") $specPath
exit $LASTEXITCODE
