# DJPlus v0.12.0 — Core Optimization & Hardening

## Release scope

- Cachés locales acotadas y profiling por etapa para consultas, recomendaciones y planes.
- Hardening cooperativo de importación, asistente y planes: timeout configurable, cancelación, concurrencia, aislamiento y cierre seguro.
- Métricas tipadas de cancelación, timeout, error y rechazo por concurrencia.
- `DiagnosticsService`, `HealthSnapshotDTO`, `DiagnosticsTool`, exportación local y resumen opcional en `AssistantPanel`.

## Safety posture and risks

La observabilidad es local, efímera y agregada: no hay telemetría, persistencia, secretos, Repository, SQLite ni histórico. Los timeouts y cierres son cooperativos; no interrumpen por la fuerza una tarea que ya está dentro de una llamada no cooperativa.

## Release checks

La candidata requiere suite completa `unittest`, `compileall`, `git diff --check`, benchmark de 500 componentes, prueba headless de `AssistantPanel` y auditoría de archivos. Commit y tag requieren aprobación separada.
