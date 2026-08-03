# Epic 10 - Final: Set Builder

`SetBuilderFacade` obtains one candidate page only through `LibraryService`, applies optional BPM, key, genre and favorite filters, and excludes recently played IDs through `HistoryService`. It then delegates sequencing to `SetPlanningEngine` and the selected energy curve to `EnergyJourneyPlanner`.

`SetBuilderResultDTO` retains the read-only sequence, transition score, confidence, reasons, phases, deviations and a plain-text export. `SetBuilderTool` is optional in `ToolRegistry`; `AssistantPanel` renders successful sequence items when the tool result is present. Neither component creates a playlist, writes the library, persists a plan, accesses Repository or SQLite, or uses generative AI.

The integration suite covers filters, recent-history exclusion, partial plans, tool dispatch and a deterministic 100-set in-memory benchmark.
