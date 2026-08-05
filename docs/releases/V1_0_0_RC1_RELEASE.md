# DJPlus v1.0.0-rc1 Release Candidate

Esta release candidate formaliza la transición hacia `1.0.0-rc1` con un enfoque en seguridad, compatibilidad y empaquetado reproducible.

## Alcance

- Actualización de la versión canónica a `1.0.0-rc1`.
- Rutas de usuario seguras mediante `DJPLUS_USER_DATA_DIR` y `LOCALAPPDATA`.
- Migración conservadora de la base legacy con validación `PRAGMA integrity_check`.
- Empaquetado reproducible con PyInstaller y recursos FFmpeg verificables.
- Smoke tests de artefacto en Windows.
- Documentación de distribución y validación de escritorio actualizadas.

## Exclusiones

No se modificaron:

- funciones de negocio existentes.
- backend funcional.
- esquema SQLite.
- UI principal.
- integraciones DJ.
- proveedores externos.

## Validación manual de escritorio

Se aprobó la validación manual de escritorio para la versión candidata. Las pruebas incluyeron:

- creación de artefacto limpio desde `tools/build_windows.ps1`.
- ejecución de smoke test de artefacto con usuario temporal aislado.
- verificación de `PRAGMA integrity_check` en la base SQLite generada.
- comprobación de checksum de `runtime/ffmpeg/ffmpeg.exe`.
- confirmación de ausencia de datos mutables en el artefacto.

## Mejoras diferidas

Las mejoras puramente visuales quedan diferidas para una futura versión posterior a `1.0.0-rc1`. Esto incluye:

- rediseños de UI adicionales más allá de la fase actual.
- extensiones visuales de Preview Player.
- nuevas capacidades DJ/mezcla grafica.

## Notas de release

- No se ha creado ningún instalador.
- No se ha hecho `git push`.
- El tag `v1.0.0-rc1` se creará sólo si todos los pasos de validación pasan.
