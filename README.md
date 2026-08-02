# DJPlus

DJPlus v0.6.1 es una biblioteca musical local para DJs, basada en PySide6, SQLAlchemy y SQLite.

Estado: Import Engine endurecido para cierre; el commit y tag requieren aprobación explícita.

## Capacidades v0.6.1

- Biblioteca virtual con carga incremental, búsqueda, filtros y ordenamiento SQLite.
- Colecciones manuales, playlists ordenadas, favoritos e historial de actividad.
- Smart Collections basadas en reglas AND compatibles con los filtros actuales.
- Migraciones SQLite idempotentes y versionadas desde la línea base v0.5.
- Import Engine sin UI: descubrimiento, metadata, cola persistente, worker y transacciones atómicas por pista.
- Reimportación por filepath normalizado: crea, omite archivos intactos o refresca metadata sin modificar datos de usuario.

## Arquitectura

La UI utiliza Services, que coordinan Repositories y motores de consulta. La documentación completa está en [DJPLUS_ARCHITECTURE.md](docs/architecture/DJPLUS_ARCHITECTURE.md).

## Requisitos

```bash
pip install -r requirements.txt
```

## Uso

```bash
python -m app.main
```

La versión de aplicación se centraliza en `app/version.py`.
