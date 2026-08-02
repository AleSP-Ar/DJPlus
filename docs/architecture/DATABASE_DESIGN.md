# Database Design

## Estado actual

DJPlus utiliza SQLite con SQLAlchemy. La entidad principal es `tracks`, que conserva identidad, metadatos, ruta local y campos preparados para evolución musical.

## Principios

- SQLite es la fuente de verdad local.
- Los repositorios encapsulan consultas y transacciones.
- La UI nunca accede a sesiones ni construye SQL.
- Las migraciones son explícitas, repetibles y compatibles con bibliotecas existentes.
- Los índices se agregan a partir de consultas medidas.

## Evolución prevista

- Proyecciones de filas ligeras para la biblioteca.
- Índices para órdenes y filtros aprobados.
- Cursor estable para carga incremental.
- FTS5 evaluado separadamente para búsqueda textual a gran escala.
- Tablas independientes para colecciones, playlists, historial y análisis cuando sus casos de uso sean aprobados.

La propuesta detallada está en [LIBRARY_ENGINE_DESIGN.md](LIBRARY_ENGINE_DESIGN.md).
