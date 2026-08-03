# Epic 9 - Sprint 2: Execution Hardening

## Scope

`ImportWorker`, `AssistantWorker` and `ToolPlanExecutor` now accept the optional, immutable `ExecutionHardeningConfigDTO`. It has a disabled-by-default timeout and a bounded local concurrency limit. Existing constructors and execution methods retain their previous valid call forms.

## Cooperative boundaries

Timeouts never terminate threads. Import timeout requests its already-supported cancellation callback at the next emitted event. The assistant preserves its provider cancellation token and reports a deadline only after the cooperative local call returns. A tool plan checks cancellation and deadline between steps; a running read-only tool is never forcibly interrupted.

Each boundary has a non-blocking semaphore, so an excess task is rejected locally without affecting the task already running. Worker close requests cancellation and waits only for its caller-provided bound. Exceptions remain isolated to the worker or tool result that owns them.

## Metrics and tests

`ExecutionEventMetricsDTO` records cancellation, timeout, failure and concurrency rejection counts for the latest execution. Stress tests cover cooperative timeout, fault isolation, concurrent assistant rejection, tool-plan timeout/cancellation and concurrent plan rejection. No persistence collaborator, Repository, SQLite access, network dependency or action execution was added.
