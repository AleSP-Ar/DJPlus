# Coding Standards

## Reglas de proyecto

- Un commit por hito importante y validado.
- No desarrollar sobre código sin una prueba proporcional al cambio.
- Toda función nueva debe reflejarse en roadmap y documentación aplicable.
- No duplicar lógica entre módulos.
- Mantener interfaz, persistencia y servicios separados.
- Documentar decisiones que afecten la arquitectura.

## Reglas adicionales

- La UI no accede directamente a SQLAlchemy ni a SQLite.
- Los servicios no importan Qt.
- Los repositorios exponen contratos claros y consultas parametrizadas.
- Las operaciones de biblioteca se diseñan para datos grandes, sin asumir carga completa en memoria.
- Toda migración de esquema debe ser compatible, verificable y documentada.
