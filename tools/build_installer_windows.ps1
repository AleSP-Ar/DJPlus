[CmdletBinding()]
param(
    [string]$BinRoot = "dist\DJPlus",
    [string]$InstallerScript = "installer\DJPlus.iss",
    [string]$OutputDirectory = "installer-output",
    [Alias("InnoSetup")][string]$InnoSetupCompiler = "C:\Users\PC Dell\AppData\Local\Programs\Inno Setup 6\ISCC.exe",
    [switch]$SkipFfmpegChecksum
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$distRoot = Join-Path $projectRoot $BinRoot
$installerScriptPath = Join-Path $projectRoot $InstallerScript
$outputRoot = Join-Path $projectRoot $OutputDirectory
$runtimePath = Join-Path $projectRoot "runtime\ffmpeg"
$requiredRuntimeFiles = @("ffmpeg.exe", "CHECKSUM.sha256", "LICENSE.txt", "NOTICE.txt", "SOURCE.txt", "VERSION.txt", "BUILD_CONFIGURATION.txt")

if (-not (Test-Path -LiteralPath $distRoot -PathType Container)) {
    throw "No se encontró el artefacto distribuible: $distRoot"
}
if (-not (Test-Path -LiteralPath $installerScriptPath -PathType Leaf)) {
    throw "No se encontró el script del instalador: $installerScriptPath"
}
if (-not (Test-Path -LiteralPath $InnoSetupCompiler -PathType Leaf)) {
    throw "No se encontró ISCC.exe: $InnoSetupCompiler"
}
foreach ($name in $requiredRuntimeFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $runtimePath $name) -PathType Leaf)) {
        throw "Falta el recurso FFmpeg obligatorio: runtime/ffmpeg/$name"
    }
}
if (-not $SkipFfmpegChecksum) {
    $expected = (Get-Content -LiteralPath (Join-Path $runtimePath "CHECKSUM.sha256") | Where-Object { $_ -match '\sffmpeg\.exe$' } | Select-Object -First 1).Split()[0]
    $actual = (Get-FileHash -LiteralPath (Join-Path $runtimePath "ffmpeg.exe") -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($expected -ne $actual) {
        throw "El checksum de runtime/ffmpeg/ffmpeg.exe no coincide. Esperado: $expected, actual: $actual"
    }
}

if (Test-Path -LiteralPath $outputRoot) {
    Remove-Item -LiteralPath $outputRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $outputRoot | Out-Null

$workDir = Join-Path $outputRoot "work"
if (Test-Path -LiteralPath $workDir) {
    Remove-Item -LiteralPath $workDir -Recurse -Force
}

$env:SourcePath = (Get-Item -LiteralPath $distRoot).FullName
Write-Host "Building installer from: $env:SourcePath"
Write-Host "Using Inno Setup compiler: $InnoSetupCompiler"
& "$InnoSetupCompiler" "/O$($outputRoot)" "/FDJPlus-Setup-1.0.0-rc1" "$installerScriptPath"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$installer = Join-Path $outputRoot "DJPlus-Setup-1.0.0-rc1.exe"
if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) {
    throw "No se generó el instalador esperado: $installer"
}

$hash = Get-FileHash -LiteralPath $installer -Algorithm SHA256
Write-Host "Installer generated: $installer"
Write-Host "Size (bytes): $((Get-Item -LiteralPath $installer).Length)"
Write-Host "SHA256: $($hash.Hash)"
exit 0
