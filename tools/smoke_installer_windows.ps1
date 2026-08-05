[CmdletBinding()]
param(
    [string]$InstallerExe = "installer-output\DJPlus-Setup-1.0.0-rc1.exe",
    [string]$ValidationPython = ".\.venv\Scripts\python.exe",
    [string]$TempInstallRoot = "$env:TEMP\DJPlusInstallerSmoke",
    [switch]$KeepInstall,
    [switch]$Headless
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$installerPath = Join-Path $projectRoot $InstallerExe
$installDir = Join-Path $TempInstallRoot "DJPlus"
$userDataDir = Join-Path $TempInstallRoot "UserData"
$runtimePath = Join-Path $installDir "_internal\runtime\ffmpeg"

if (-not (Test-Path -LiteralPath $installerPath -PathType Leaf)) {
    throw "No se encontró el instalador: $installerPath"
}
if (-not (Test-Path -LiteralPath $ValidationPython -PathType Leaf)) {
    throw "No se encontró el intérprete de validación: $ValidationPython"
}

if (Test-Path -LiteralPath $TempInstallRoot) {
    Remove-Item -LiteralPath $TempInstallRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $installDir -Force | Out-Null
New-Item -ItemType Directory -Path $userDataDir -Force | Out-Null

$installArgs = @(
    "/VERYSILENT",
    "/SUPPRESSMSGBOXES",
    "/NORESTART",
    "/DIR=$installDir"
)
Write-Host "Installing silently to: $installDir"
$process = Start-Process -FilePath $installerPath -ArgumentList $installArgs -Wait -PassThru -NoNewWindow
Write-Host "Installer process exit code: $($process.ExitCode)"
Write-Host "Install directory exists after install: $(Test-Path -LiteralPath $installDir -PathType Container)"
Write-Host "Install dir contents:" 
Get-ChildItem -LiteralPath $installDir -Recurse -Force | Select-Object -First 20 | ForEach-Object { Write-Host $_.FullName }

if (-not (Test-Path -LiteralPath $installDir -PathType Container)) {
    throw "La instalación silenciosa no creó el directorio: $installDir"
}

$exe = Join-Path $installDir "DJPlus.exe"
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "No se encontró el ejecutable en la instalación: $exe"
}

$requiredRuntimeFiles = @("ffmpeg.exe", "CHECKSUM.sha256", "LICENSE.txt", "NOTICE.txt", "SOURCE.txt", "VERSION.txt", "BUILD_CONFIGURATION.txt")
foreach ($name in $requiredRuntimeFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $runtimePath $name) -PathType Leaf)) {
        throw "Falta el recurso de runtime en la instalación: $name"
    }
}

$expected = (Get-Content -LiteralPath (Join-Path $runtimePath "CHECKSUM.sha256") | Where-Object { $_ -match '\sffmpeg\.exe$' } | Select-Object -First 1).Split()[0]
$actual = (Get-FileHash -LiteralPath (Join-Path $runtimePath "ffmpeg.exe") -Algorithm SHA256).Hash.ToLowerInvariant()
if ($expected -ne $actual) {
    throw "Checksum de FFmpeg en la instalación no coincide. Esperado: $expected, actual: $actual"
}

$logPath = Join-Path $TempInstallRoot "smoke.log"
$env:DJPLUS_USER_DATA_DIR = $userDataDir
$process = Start-Process -FilePath $exe -WorkingDirectory $installDir -PassThru
Start-Sleep -Seconds 8
$process.Refresh()
if ($process.HasExited) {
    throw "DJPlus.exe finalizó inmediatamente durante smoke install (code $($process.ExitCode))."
}

$database = Join-Path $userDataDir "data\djplus.db"
$validationCode = "import sqlite3,sys; db=sys.argv[1]; con=sqlite3.connect(db); integrity=con.execute('PRAGMA integrity_check').fetchone()[0]; migrations=[row[0] for row in con.execute('SELECT version FROM schema_migrations ORDER BY version')]; con.close(); print(integrity); print(','.join(migrations))"
Start-Sleep -Seconds 10
if (-not (Test-Path -LiteralPath $database -PathType Leaf)) {
    Stop-Process -Id $process.Id -Force
    throw "No se creó la base de datos en UserData durante el smoke install."
}
$child = & $ValidationPython -c $validationCode $database
if ($LASTEXITCODE -ne 0) {
    Stop-Process -Id $process.Id -Force
    throw "La validación SQLite falló con $ValidationPython"
}
$parts = $child -split "`n"
if ($parts[0].Trim() -ne 'ok') {
    Stop-Process -Id $process.Id -Force
    throw "PRAGMA integrity_check devolvió: $($parts[0])"
}
if ($parts[1].Trim() -ne '0001_baseline_schema,0002_import_engine,0003_track_import_snapshots,0004_analysis_provenance,0005_track_metadata_history') {
    Stop-Process -Id $process.Id -Force
    throw "Las migraciones SQLite no coinciden: $($parts[1])"
}

$installFiles = Get-ChildItem -LiteralPath $installDir -Recurse -File
$forbiddenPatterns = @('*.db', '*.sqlite', '*.sqlite-wal', '*.sqlite-shm', '*.jsonl', '*.lock', '*.tmp', '*.temp')
$forbidden = $installFiles | Where-Object { $name = $_.Name; $forbiddenPatterns | Where-Object { $name -like $_ } }
if ($forbidden) {
    Stop-Process -Id $process.Id -Force
    throw "La instalación contiene archivos mutables prohibidos: $($forbidden | ForEach-Object { $_.FullName } | Join-String '; ')"
}

if (-not $process.CloseMainWindow()) {
    Write-Host "DJPlus.exe no responde a CloseMainWindow, intentando terminación forzada."
    Stop-Process -Id $process.Id -Force
}
if (-not $process.WaitForExit(15000)) {
    Write-Host "DJPlus.exe no cerró en 15 segundos, forzando terminación."
    Stop-Process -Id $process.Id -Force
}
if (-not $process.HasExited) {
    throw "DJPlus.exe no pudo cerrarse después de intentar cerrar la ventana y forzar terminación."
}

Start-Sleep -Seconds 2
$leftover = Get-ChildItem -LiteralPath $userDataDir -Recurse -Force -File | Where-Object { $_.Name -like '*.lock' -or $_.Name -like '*.tmp' -or $_.Name -like '*.temp' -or $_.Name -like '*.sqlite-wal' -or $_.Name -like '*.sqlite-shm' }
if ($leftover) {
    throw "Quedaron archivos temporales o locks en UserData: $($leftover | ForEach-Object { $_.FullName } | Join-String '; ')"
}

$uninstExe = Join-Path $installDir "unins000.exe"
if (-not (Test-Path -LiteralPath $uninstExe -PathType Leaf)) {
    throw "No se encontró el desinstalador en la instalación: $uninstExe"
}
Start-Process -FilePath $uninstExe -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" -Wait -NoNewWindow

if (Test-Path -LiteralPath $installDir -PathType Container) {
    Remove-Item -LiteralPath $installDir -Recurse -Force
}

if (-not (Test-Path -LiteralPath $userDataDir -PathType Container)) {
    throw "Los datos de usuario se perdieron tras desinstalar."
}

$remainingUserFiles = Get-ChildItem -LiteralPath $userDataDir -Recurse -Force -File
if (-not $remainingUserFiles) {
    throw "No quedan datos de usuario después de la desinstalación cuando debían conservarse."
}

$remainingUserFiles = Get-ChildItem -LiteralPath $userDataDir -Recurse -File
if (-not $remainingUserFiles) {
    throw "No quedan datos de usuario después de la desinstalación cuando debían conservarse."
}

$processes = Get-Process -Name DJPlus -ErrorAction SilentlyContinue
if ($processes) {
    throw "DJPlus.exe sigue ejecutándose después de la desinstalación."
}

Write-Host "Smoke installer passed: installation, runtime validation, user data retention, uninstallation verified."
if (-not $KeepInstall) {
    Remove-Item -LiteralPath $TempInstallRoot -Recurse -Force
}
exit 0
