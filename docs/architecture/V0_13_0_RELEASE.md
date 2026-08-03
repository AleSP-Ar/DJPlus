# DJPlus v0.13.0 — Intelligent Set Builder

## Release scope

- `SetPlanningEngine`, DTOs inmutables y políticas de salto máximo BPM y energía.
- `EnergyJourneyPlanner` con curvas ascending, descending y arc; fases warm-up, build, peak y cooldown.
- `SetBuilderFacade`, `SetBuilderTool` read-only, filtros de candidatas, exclusión de historial e integración opcional con `AssistantPanel`.
- Secuencias explicables con score, confianza, razones, desviaciones, planes parciales y exportación a texto.

## Limits and safety posture

El ranking se calcula sólo sobre la página de candidatas recuperada por `LibraryService`; no es un ranking global de biblioteca. Si faltan candidatas que respeten las políticas o el objetivo energético, se devuelve el prefijo válido como plan parcial con explicación.

No se persiste ningún plan ni se crea una playlist. La capa no accede a Repository o SQLite directamente y no usa IA generativa.

## Release checks

La candidata requiere suite completa `unittest`, `compileall`, `git diff --check`, benchmark de 100 sets en memoria, prueba headless de `AssistantPanel` y auditoría de archivos. Commit y tag requieren aprobación separada.
