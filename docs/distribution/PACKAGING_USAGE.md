# Build base Windows x64

El build base usa PyInstaller en modo `onedir` y conserva el desarrollo con:

```powershell
python -m app.main
```

## Preparación

```powershell
python -m venv .build-venv
.\.build-venv\Scripts\python.exe -m pip install --upgrade pip
.\tools\build_windows.ps1
```

El script valida el runtime FFmpeg, sus manifiestos y su SHA-256; limpia `build/` y `dist/`; instala `requirements-build.txt`; y genera `dist\DJPlus\DJPlus.exe`. No genera instalador.

Usar una versión de Python de 64 bits compatible con las dependencias fijadas; el primer build validado utilizó Python 3.11.

El `.spec` usa los hooks oficiales de PyInstaller para incluir sólo plugins Qt alcanzados por los módulos PySide6 usados por DJPlus; no recolecta el paquete PySide6 completo.

Usar `-SkipFfmpegChecksum` sólo para diagnóstico local, nunca para publicar. El artefacto no incluye bases SQLite, configuración, logs, backups, tests ni entornos virtuales. Los datos mutables se resuelven mediante `DJPLUS_USER_DATA_DIR` o la ruta de usuario de Windows.
