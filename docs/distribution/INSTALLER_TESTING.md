# Pruebas de instalador Windows

Este documento describe la validación del instalador local para DJPlus `v1.0.0-rc1`.

## Requisitos

- Inno Setup 6 instalado en `C:\Users\PC Dell\AppData\Local\Programs\Inno Setup 6\ISCC.exe`
- Artefacto PyInstaller ya generado en `dist\DJPlus`
- `runtime\ffmpeg\ffmpeg.exe` presente y validado con `CHECKSUM.sha256`

## Build del instalador

Desde la raíz del proyecto:

```powershell
.\tools\build_installer_windows.ps1
```

El script realiza:

- validación de `dist\DJPlus\DJPlus.exe`
- validación de los archivos FFmpeg y su checksum
- limpieza de `installer-output`
- ejecución de `ISCC.exe`
- generación de `installer-output\DJPlus-Setup-1.0.0-rc1.exe`
- cálculo de SHA-256 del instalador

## Smoke test del instalador

Desde la raíz del proyecto:

```powershell
.\tools\smoke_installer_windows.ps1 -ValidationPython .\.build-venv\Scripts\python.exe
```

El script realiza:

- instalación silenciosa en una carpeta temporal
- inicio de `DJPlus.exe` con `DJPLUS_USER_DATA_DIR` temporal
- validación SQLite y migraciones
- comprobación de ausencia de archivos mutables dentro de la instalación
- cierre de DJPlus
- desinstalación silenciosa
- conservación de datos de usuario
- verificación de que no queden procesos ni archivos temporales

## Resultados esperados

- el instalador se genera en `installer-output\DJPlus-Setup-1.0.0-rc1.exe`
- la instalación silenciosa crea `DJPlus.exe` en el directorio temporal
- el instalador no deja datos mutables dentro de `installer-output` ni en la instalación
- la desinstalación remueve la carpeta de instalación pero conserva `UserData`

## No se permite

- no crear asociaciones de archivos
- no usar `CreateDesktopIcon` en `[Setup]`
- no sobrescribir datos de usuario en desinstalar
- no generar instaladores fuera de `installer-output`
