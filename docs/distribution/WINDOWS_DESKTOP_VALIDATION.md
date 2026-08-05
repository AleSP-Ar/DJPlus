# Validación manual del artefacto Windows

Esta guía valida el comportamiento que no debe automatizarse: ventana visible, navegación, audio y cierre desde el escritorio. Se aplica al artefacto `onedir` ya construido; no genera un instalador.

## Preparación

Desde la raíz del repositorio, use una carpeta temporal dedicada y manténgala para la reapertura:

```powershell
$env:DJPLUS_USER_DATA_DIR = Join-Path $env:TEMP "DJPlus-desktop-validation"
Remove-Item -LiteralPath $env:DJPLUS_USER_DATA_DIR -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $env:DJPLUS_USER_DATA_DIR | Out-Null
.\dist\DJPlus\DJPlus.exe
```

Antes de la revisión visual, el smoke automatizable comprueba el ejecutable, FFmpeg, SQLite, migraciones y que los datos no entren en `dist`:

```powershell
.\tools\smoke_artifact_windows.ps1 -ArtifactRoot .\dist\DJPlus -ValidationPython .\.build-venv\Scripts\python.exe -Headless
```

`-Headless` se reserva para CI o sesiones sin escritorio: verifica inicio y limpieza controlada, pero no puede comprobar el cierre por la X. En un escritorio Windows, ejecute el script sin `-Headless` para verificar el cierre nativo.

## Recorrido manual obligatorio

Con la ventana visible, confirme lo siguiente:

1. La ventana abre sin diálogo de error, con tamaño normal y con Preview Player fijo abajo.
2. Navegue por Biblioteca, Colecciones, Playlists, Importar, Metadata, Assistant y Diagnóstico. Cada sección debe cargar y conservar su navegación básica.
3. En Biblioteca cargue explícitamente una pista en Preview Player; pruebe reproducción de MP3, FLAC, AIFF y WAV. Confirme transporte, volumen y dispositivo, sin autoplay inesperado.
4. Reduzca la ventana a un ancho estrecho y vuelva a ampliarla. Los controles esenciales y la barra inferior deben seguir accesibles.
5. Ejecute las acciones ya disponibles en Importar, Metadata, Assistant y Diagnóstico, incluyendo sus estados vacío, procesamiento, error o no configurado cuando correspondan.
6. Cierre con la X de Windows. Confirme que `DJPlus.exe` desaparece del Administrador de tareas y que no quedan archivos `*.lock`, `*.sqlite-wal`, `*.sqlite-shm`, `*.tmp` o `*.temp` en `$env:DJPLUS_USER_DATA_DIR`.
7. Abra de nuevo `DJPlus.exe` con el mismo `DJPLUS_USER_DATA_DIR`. Confirme que se reutilizan la base y la configuración existentes, sin crear datos dentro de `dist\DJPlus`.

## Criterio de aprobación

La validación aprueba cuando el smoke pasa, el recorrido anterior no presenta errores visibles y la carpeta del artefacto no contiene SQLite, configuración, logs ni backups. La apertura visible, la navegación por clic, la reproducción real y el cierre por la X requieren intervención manual del usuario; no se incluyen dependencias ni automatización gráfica.
