# DJPlus — Pipeline de empaquetado reproducible para Windows

Estado: plan previo a `v1.0.0`. Este documento no implementa empaquetado ni cambia código.

## Recomendación

La herramienta principal recomendada es **PyInstaller en modo `onedir`**, ejecutado desde un entorno virtual limpio y fijado por `requirements.txt`.

`onedir` es preferible a `onefile` para DJPlus porque:

- PySide6 necesita distribuir plugins Qt (`platforms`, `imageformats`, `styles`, y los plugins multimedia disponibles).
- FFmpeg es un ejecutable externo grande, con licencia y checksum propios.
- SQLite, migraciones, manifiestos y diagnósticos deben poder inspeccionarse en una instalación fallida.
- El arranque es más predecible y no depende de extraer un árbol temporal en cada ejecución.

Alternativa: **Nuitka standalone**, evaluada después de obtener un build PyInstaller reproducible. Puede ofrecer mejor rendimiento de arranque y binarios más cercanos a distribución, pero exige validar explícitamente plugins PySide6, imports dinámicos, Qt Multimedia y la inclusión de migraciones. No se recomienda como primer pipeline.

## Punto de entrada y restricciones actuales

El entry point operativo es:

```powershell
python -m app.main
```

`app.main` carga configuración, instala `AppLoggingService`, ejecuta `init_database()`, crea `QApplication`, compone `MainWindow` y cierra Preview Player, historial y logging en `finally`. El wrapper de PyInstaller debe invocar la función equivalente y conservar un proceso GUI (`--noconsole`), sin importar `app.main` durante el build.

Gate previo obligatorio: `app.database.database` define actualmente `DATABASE_PATH` como `<PROJECT_ROOT>/data/djplus.db`. Una instalación en `Program Files` no debe intentar escribir allí. Antes de distribuir, debe existir una política aprobada para redirigir la base mutable a `%LOCALAPPDATA%\DJPlus` (o instalar en una ubicación escribible). El plan no autoriza corregirlo en esta fase.

## Estructura propuesta del artefacto `DJPlus-v1.0.0-win64`

```text
DJPlus-v1.0.0-win64/
  DJPlus.exe
  _internal/                 # bootloader, Python y módulos congelados
  PySide6/                   # plugins Qt incluidos por PyInstaller
  runtime/ffmpeg/
    ffmpeg.exe
    CHECKSUM.sha256
    LICENSE.txt
    NOTICE.txt
    SOURCE.txt
    VERSION.txt
    BUILD_CONFIGURATION.txt
  migrations/                 # cuerpos de migración si el build los requiere
  README.txt
  THIRD_PARTY_NOTICES.txt
```

La base SQLite, configuración, logs, backups, cachés y música no forman parte del artefacto.

## Incluidos

- `app.main` y todos los módulos transitivamente importados por la aplicación.
- Migraciones canónicas de `app.database.migrations` y recursos que se carguen por ruta relativa.
- Dependencias fijadas: `PySide6`, `SQLAlchemy`, `greenlet`, `mutagen`, `python-dotenv` y `typing_extensions`.
- Plugins Qt detectados por la prueba de arranque: `platforms/qwindows.dll`, `imageformats`, `styles` y multimedia si el backend está disponible.
- Los seis manifiestos/licencias versionados de `runtime/ffmpeg` y el `ffmpeg.exe` aprobado, sólo después de validar SHA-256.
- Información de versión `app.version.VERSION`, release notes y avisos de terceros necesarios para distribución.

## Excluidos

- `.venv`, `__pycache__`, `.pyc`, tests, benchmarks, fixtures, notebooks y herramientas de desarrollo.
- `data/djplus.db`, bases de prueba, imports, música, playlists exportadas, backups y logs.
- `.env`, credenciales, configuraciones de usuario, prompts, sesiones y diagnósticos generados.
- `.git`, `.github`, documentación interna no requerida y directorios legacy de compatibilidad que no sean imports runtime.
- Git LFS y cualquier puntero de FFmpeg. `runtime/ffmpeg/ffmpeg.exe` permanece ignorado en Git y se incorpora sólo al staging del instalador.

## FFmpeg

El resolver busca, en orden, ruta configurada, `PATH` y `runtime/ffmpeg/ffmpeg.exe`. El build debe copiar el binario Windows x64 aprobado junto con sus manifiestos, verificar `CHECKSUM.sha256` antes de empaquetar y repetir la verificación después de instalar. No se descarga ni instala FFmpeg durante la ejecución.

El pipeline debe registrar versión, arquitectura, variante LGPL, origen, checksum del ZIP y checksum del ejecutable. Si falta o no coincide, el instalador debe fallar antes de publicar; la aplicación debe conservar el modo degradado para WAV/AIFF y reportar MP3/FLAC no disponibles.

## Datos, configuración y logging de usuario

La configuración y logging usan las rutas derivadas por `SettingsService`/`AppLoggingService`, normalmente bajo `%APPDATA%\DJPlus` o `%LOCALAPPDATA%\DJPlus` según la configuración. La base SQLite actual debe migrarse de `PROJECT_ROOT/data` a una ubicación escribible de usuario antes del primer instalador; no debe guardarse junto al ejecutable.

En instalación limpia se deben comprobar permisos, creación de directorios, migraciones `0001`–`0005`, backup/restore, rotación de logs y exportación diagnóstica sin incluir secretos, prompts, rutas completas de música ni el binario FFmpeg.

## Flujo reproducible de build

```powershell
python -m venv .build-venv
.\.build-venv\Scripts\python.exe -m pip install --upgrade pip
.\.build-venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller
.\.build-venv\Scripts\python.exe -m pip check
.\.build-venv\Scripts\python.exe -m compileall app
Get-FileHash runtime\ffmpeg\ffmpeg.exe -Algorithm SHA256
.\.build-venv\Scripts\pyinstaller.exe --noconfirm --clean --onedir --windowed --name DJPlus app\main.py
```

El comando final deberá evolucionar a un `.spec` versionado para declarar hidden imports, `PySide6` plugins, migraciones y `runtime/ffmpeg`; no se debe depender de autodetección sin inspeccionar el warnings file. El build debe ejecutarse en un checkout limpio, con locale/timezone controlados y una versión de Python/Windows documentada.

## Instalación limpia y actualización

1. Crear una VM o perfil Windows nuevo sin Python, Qt, FFmpeg ni datos DJPlus.
2. Instalar el artefacto en una ruta protegida y confirmar que los datos mutables no se escriben allí.
3. Ejecutar `DJPlus.exe`, comprobar migraciones, creación de configuración, logging y navegación completa.
4. Probar WAV/AIFF sin FFmpeg y MP3/FLAC con el binario validado; probar también checksum inválido y modo degradado.
5. Importar una biblioteca de prueba, cerrar/reabrir y verificar SQLite, historial, Preview Player y diagnósticos.
6. Actualizar sobre una instalación anterior, conservar datos, ejecutar migraciones idempotentes y verificar rollback del instalador.

## Criterios de aprobación

- Artefacto reproducible desde checkout limpio con hashes registrados.
- `python -m app.main` y `DJPlus.exe` muestran el mismo comportamiento observable.
- Suite completa, focales de packaging/headless, `compileall`, `pip check` y `git diff --check` pasan.
- Qt plugins presentes, sin errores de `platform plugin`, y cierre libera logging, SQLite, workers y Preview Player.
- FFmpeg incluido sólo tras checksum/licencia correctos; LFS permanece vacío.
- Datos de usuario escribibles, migraciones verificadas y diagnóstico exportable sin datos sensibles.
- La gate de ruta SQLite mutable queda resuelta y probada antes de etiquetar `v1.0.0`.

## Reversión y diagnóstico

El instalador debe conservar la versión anterior hasta que la nueva supere el smoke test. Ante fallo, detener la actualización, restaurar el directorio de aplicación anterior y conservar datos de usuario intactos. No borrar automáticamente la base ni backups.

Los primeros diagnósticos son: `DJPlus.exe` con logging de arranque, `AppLoggingService` y exportación diagnóstica, presencia de plugins Qt, permisos de `%APPDATA%`/`%LOCALAPPDATA%`, estado de migraciones y checksum de FFmpeg. Un build que falla por plugin, migración, ruta escribible o checksum no se publica; se conserva el log y el hash del artefacto para reproducirlo.
