# Epic 7 - Tool Planning Framework: Final Architecture Audit

## Flow

`DeterministicToolPlanner` produces an immutable ordered `ToolPlanDTO`. `ToolPlanExecutor` executes eligible plan steps only through `ToolDispatcher`; failures are typed and dependent steps become `blocked`. `ToolResultComposer` receives that execution and returns `ComposedToolResponseDTO`, preserving the original plan order and producing a deterministic summary.

## Safety audit

Planning imports only tool DTOs and the registry. Execution imports only the dispatcher and plan contracts. Composition imports only execution DTOs. None of these modules imports the Action Execution Framework, Services, repositories, SQLite, provider transport or UI. The composer does not dispatch, execute, or alter results.

`AssistantRuntime` exposes plan execution and composition as optional typed outputs. Direct tool calls retain their prior flow when no plan is supplied.

## Result states

- Complete: all steps succeeded.
- Partial: at least one step succeeded and one failed or was blocked.
- Failed: no step succeeded.

Each failed or blocked step has an explanatory message in plan order. No action proposal is executed by the planning stack.
