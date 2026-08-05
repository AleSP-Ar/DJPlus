[CmdletBinding()]
param(
    [string]$ArtifactRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) "dist\DJPlus"),
    [string]$ValidationPython = "python",
    [int]$StartupSeconds = 8,
    [int]$ShutdownSeconds = 15,
    [switch]$Headless,
    [switch]$KeepUserData
)

$ErrorActionPreference = "Stop"
$ArtifactRoot = [System.IO.Path]::GetFullPath($ArtifactRoot)
$executable = Join-Path $ArtifactRoot "DJPlus.exe"
$runtimePath = Join-Path $ArtifactRoot "_internal\runtime\ffmpeg"
$requiredRuntimeFiles = @(
    "ffmpeg.exe", "CHECKSUM.sha256", "LICENSE.txt", "NOTICE.txt",
    "SOURCE.txt", "VERSION.txt", "BUILD_CONFIGURATION.txt"
)
$expectedMigrations = @(
    "0001_baseline_schema", "0002_import_engine", "0003_track_import_snapshots",
    "0004_analysis_provenance", "0005_track_metadata_history"
)
$createdDataRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("DJPlus-smoke-" + [guid]::NewGuid().ToString("N"))
$process = $null
$originalEnvironment = @{
    DJPLUS_USER_DATA_DIR = $env:DJPLUS_USER_DATA_DIR; PYTHONPATH = $env:PYTHONPATH
    PYTHONHOME = $env:PYTHONHOME; VIRTUAL_ENV = $env:VIRTUAL_ENV; QT_QPA_PLATFORM = $env:QT_QPA_PLATFORM
}

function Assert-ArtifactHasNoMutableData {
    $forbiddenFiles = @("*.db", "*.sqlite", "*.sqlite-wal", "*.sqlite-shm", "config.json", "*.jsonl", "*.lock", "*.tmp", "*.temp")
    $foundFiles = Get-ChildItem -LiteralPath $ArtifactRoot -Recurse -Force -File |
        Where-Object {
            $name = $_.Name
            $forbiddenFiles | Where-Object { $name -like $_ }
        }
    $foundDirectories = Get-ChildItem -LiteralPath $ArtifactRoot -Recurse -Force -Directory |
        Where-Object { $_.Name -in @("data", "logs", "backups") }
    if ($foundFiles -or $foundDirectories) {
        $items = @($foundFiles + $foundDirectories) | ForEach-Object { $_.FullName }
        throw "El artefacto contiene datos mutables no permitidos: $($items -join '; ')"
    }
}

function Test-SqliteDatabase {
    param([string]$DatabasePath)
    $validationCode = "import sqlite3,sys; db=sys.argv[1]; con=sqlite3.connect(db); integrity=con.execute('PRAGMA integrity_check').fetchone()[0]; migrations=[row[0] for row in con.execute('SELECT version FROM schema_migrations ORDER BY version')]; con.close(); print(integrity); print(','.join(migrations))"
    $result = & $ValidationPython -c $validationCode $DatabasePath
    if ($LASTEXITCODE -ne 0) { throw "La validacion SQLite no pudo ejecutarse con: $ValidationPython" }
    if ($result.Count -lt 2 -or $result[0].Trim() -ne "ok") { throw "PRAGMA integrity_check no devolvio ok." }
    $actualMigrations = @($result[1].Trim().Split(',', [System.StringSplitOptions]::RemoveEmptyEntries))
    if (@(Compare-Object $expectedMigrations $actualMigrations).Count -ne 0) {
        throw "Las migraciones no coinciden. Esperadas: $($expectedMigrations -join ', '). Obtenidas: $($actualMigrations -join ', ')."
    }
}

try {
    if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) { throw "No se encontro el ejecutable: $executable" }
    foreach ($name in $requiredRuntimeFiles) {
        if (-not (Test-Path -LiteralPath (Join-Path $runtimePath $name) -PathType Leaf)) { throw "Falta el recurso obligatorio: _internal/runtime/ffmpeg/$name" }
    }
    $expectedChecksum = ((Get-Content -LiteralPath (Join-Path $runtimePath "CHECKSUM.sha256") | Where-Object { $_ -match '\sffmpeg\.exe$' } | Select-Object -First 1).Split()[0]).ToLowerInvariant()
    $actualChecksum = (Get-FileHash -LiteralPath (Join-Path $runtimePath "ffmpeg.exe") -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($expectedChecksum -ne $actualChecksum) { throw "El checksum de FFmpeg no coincide." }
    Assert-ArtifactHasNoMutableData
    if (-not (Test-Path -LiteralPath $ValidationPython -PathType Leaf) -and -not (Get-Command $ValidationPython -ErrorAction SilentlyContinue)) { throw "No se encontro el interprete para validar SQLite: $ValidationPython" }

    New-Item -ItemType Directory -Path $createdDataRoot -Force | Out-Null
    $env:DJPLUS_USER_DATA_DIR = $createdDataRoot
    Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
    Remove-Item Env:VIRTUAL_ENV -ErrorAction SilentlyContinue
    if ($Headless) { $env:QT_QPA_PLATFORM = "offscreen" } else { Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue }
    $process = Start-Process -FilePath $executable -WorkingDirectory $ArtifactRoot -PassThru
    Start-Sleep -Seconds $StartupSeconds
    $process.Refresh()
    if ($process.HasExited) { throw "DJPlus.exe finalizo durante el arranque (codigo $($process.ExitCode))." }

    $database = Join-Path $createdDataRoot "data\djplus.db"
    $log = Join-Path $createdDataRoot "logs\djplus.jsonl"
    if (-not (Test-Path -LiteralPath $database -PathType Leaf)) { throw "No se creo la base SQLite fuera del artefacto." }
    if (-not (Test-Path -LiteralPath $log -PathType Leaf)) { throw "No se creo el log fuera del artefacto." }
    Test-SqliteDatabase -DatabasePath $database
    Assert-ArtifactHasNoMutableData

    if ($Headless) {
        Stop-Process -Id $process.Id -Force
        $process.WaitForExit($ShutdownSeconds * 1000) | Out-Null
        $closure = "headless-cleanup; la comprobacion de cierre por X requiere escritorio"
    } else {
        if (-not $process.CloseMainWindow()) { throw "No se encontro una ventana nativa para cerrar. Use -Headless solo en CI; valide el cierre por X en escritorio." }
        if (-not $process.WaitForExit($ShutdownSeconds * 1000)) { throw "DJPlus.exe no cerro dentro de $ShutdownSeconds segundos." }
        $closure = "graceful"
    }
    $process = $null
    $residualPatterns = @("*.lock", "*.sqlite-wal", "*.sqlite-shm", "*.tmp", "*.temp")
    $residual = Get-ChildItem -LiteralPath $createdDataRoot -Recurse -Force -File |
        Where-Object { $name = $_.Name; $residualPatterns | Where-Object { $name -like $_ } }
    if ($residual) { throw "Quedaron locks o temporales: $($residual.FullName -join '; ')" }
    [pscustomobject]@{ Artifact = $ArtifactRoot; UserData = $createdDataRoot; FfmpegChecksum = $actualChecksum; DatabaseIntegrity = "ok"; Migrations = $expectedMigrations -join ", "; Closure = $closure; Result = "PASS" }
}
finally {
    if ($process -and -not $process.HasExited) { Stop-Process -Id $process.Id -Force }
    foreach ($name in $originalEnvironment.Keys) { if ($null -eq $originalEnvironment[$name]) { Remove-Item "Env:$name" -ErrorAction SilentlyContinue } else { Set-Item "Env:$name" $originalEnvironment[$name] } }
    if (-not $KeepUserData -and (Test-Path -LiteralPath $createdDataRoot)) { Remove-Item -LiteralPath $createdDataRoot -Recurse -Force }
}
