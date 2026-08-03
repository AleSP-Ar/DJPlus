# DJPlus

DJPlus v0.9.0 es una biblioteca musical local para DJs, basada en PySide6, SQLAlchemy y SQLite.

Estado: v0.9.0 preparada para revisión de release; el commit y tag requieren aprobación explícita.

## Capacidades v0.9.0

- AI Provider Infrastructure con contratos, registro, configuración, resiliencia, credenciales redactadas y transportes mock/locales.
- Tool Calling Framework con schemas validados y herramientas de biblioteca acotadas a Services.
- Execution Framework simulado, con confirmación, autorización, idempotencia, auditoría y rollback tipado; no ejecuta escrituras reales.
- Asistente local Ollama restringido a `http://localhost:<puerto>`, con timeout, cancelación, worker Qt y panel PySide6 no bloqueante.
- Búsqueda natural de biblioteca por texto, BPM, tonalidad, rating, favoritos y género, con filtros compuestos y paginación mediante `LibraryService`.

## Capacidades heredadas

- Biblioteca virtual con carga incremental, búsqueda, filtros y ordenamiento SQLite.
- Colecciones manuales, playlists ordenadas, favoritos e historial de actividad.
- Smart Collections basadas en reglas AND compatibles con los filtros actuales.
- Migraciones SQLite idempotentes y versionadas desde la línea base v0.5.
- Import Engine sin UI: descubrimiento, metadata, cola persistente, worker y transacciones atómicas por pista.
- Reimportación por filepath normalizado: crea, omite archivos intactos o refresca metadata sin modificar datos de usuario.
- AI Runtime independiente del proveedor: `AssistantRuntime`, `PromptBuilder`, `ToolRegistry` y `ToolDispatcher` separan el flujo interno de futuros proveedores como OpenAI, Ollama o modelos locales.
- Sesiones conversacionales locales y efímeras, sin memoria persistente ni acceso directo a SQLite, ORM, repositorios o filesystem.
- Action Pipeline y Confirmation Manager: las herramientas sólo generan propuestas inmutables, auditables y sujetas a confirmación; no ejecutan acciones de escritura.
- Auditoría arquitectónica y ADRs para límites del Runtime, herramientas, conversaciones, propuestas y políticas de confirmación.

## Arquitectura

La UI utiliza Services, que coordinan Repositories y motores de consulta. El Runtime de IA es una capa de servicios aislada y basada en DTOs; no conoce proveedores de IA ni infraestructura de persistencia. La documentación completa está en [DJPLUS_ARCHITECTURE.md](docs/architecture/DJPLUS_ARCHITECTURE.md) y [AI_RUNTIME_IMPLEMENTATION.md](docs/architecture/AI_RUNTIME_IMPLEMENTATION.md).

## Requisitos

```bash
pip install -r requirements.txt
```

## Uso

```bash
python -m app.main
```

La versión de aplicación se centraliza en `app/version.py`.
