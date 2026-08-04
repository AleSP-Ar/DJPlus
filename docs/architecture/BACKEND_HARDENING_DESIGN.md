# Backend Hardening Design

## Startup and shutdown

The supported order is: load/migrate settings, configure local logging, explicitly initialize the database, compose history/player/services, create `MainWindow`, then execute Qt. Shutdown closes preview/history, logs shutdown and closes the logging service. Directory creation for the canonical database is now inside `init_database()`, not module import.

Imports must not create Qt objects, start FFmpeg, scan music, start workers, open a session or configure handlers. Legacy modules may emit controlled `DeprecationWarning` but must not perform work until an explicit function is called. `AppLoggingService` installs hooks only when explicitly requested and restores prior hooks at shutdown.

`MainWindowDependencies` is a narrow optional widget-composition seam. No-argument startup still builds the same production panels and services. Tests may inject already-composed temporary widgets, allowing an isolated lifecycle without changing layout, signals or visible behaviour. `MainWindow` closes its library view and preview player once; repeated close remains idempotent.

## Resource guarantees

Repository sessions are operation-owned or injected for tests; workers and restore use explicit cooperative close paths. Global ranking closes its candidate iterator on completion/cancellation. Restore takes an exclusive lock, creates a preventive backup, invokes the injected connection-dispose callback before atomic replacements, and releases locks in `finally`.

`DatabaseMigrationCoordinator` applies the same rule to startup migrations: current databases skip backup; historical ones require a verified pre-action backup before the injected dispose callback and migration runner execute. Its typed result does not silently repair future or inconsistent history.

## Dependencies and performance

Dependencies remain unchanged. The subprocess import smoke test runs canonical and legacy boundaries from a temporary working directory with redirected user-path variables; it verifies no configuration, database, log or backup file is created by imports alone. It is not a package-installation test: dependency installation and a fully injected `MainWindow` clean-install lifecycle remain separate work because the current UI composes global library services.

Migration operations are schema DDL/metadata work rather than per-track rewrites; performance measurements remain outside the standard suite for 10k+ fixtures. A controlled fault after 0002 DDL/index creation demonstrates that the migration record is not advanced before success. SQLite may preserve idempotent DDL after a fault, so the system does not claim an all-or-nothing DDL rollback.

The test-only `run_migrations(..., execution_hook=...)` seam covers start, DDL/table/index boundaries, ALTER/data transformation, migration-record boundaries and pre-validation. The coordinator reports `FAILED` for injected runtime faults, preserves a verified pre-action backup, and a retry converges when SQLite's idempotent DDL state is recoverable.

## Residual risk

SQLite cannot promise a single transaction spanning database replacement and settings files. Cancellation remains cooperative. The historical restore path now migrates only a second temporary candidate and has end-to-end 0001/0003/0005 coverage; its remaining risk is interruption during the two independent filesystem replacements. A complete isolated MainWindow startup test requires dependency injection for the global library composition and is intentionally not claimed by the import smoke test.
