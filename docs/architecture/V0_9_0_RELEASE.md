# DJPlus v0.9.0 — AI Assistant Foundations

## Release scope

- AI Provider Infrastructure: provider abstractions, registry/factory, capabilities, configuration, retries, typed errors, credentials redaction and transport contracts.
- Tool Calling Framework: allowlisted schemas and service-only tools.
- Execution Framework: simulated confirmation-to-executor flow, authorization, idempotency, audit log and typed rollback. No real action is executed.
- Ollama Local Assistant MVP: stdlib HTTP transport restricted to `http://localhost:<port>`, local configuration, cancellation and a non-blocking PySide6 panel.
- Natural Language Library Search: deterministic filtering by text, BPM, key, rating, favorite and genre; paged results are served only by `LibraryService`.

## Safety posture

No provider SDK, secret, external endpoint, generated SQL, direct Repository access from assistant tools, automatic action or library write is included. The only real network path is local HTTP to `localhost` in the dedicated transport.

## Release checks

The release candidate requires a full automated suite, `compileall`, `git diff --check`, a library benchmark and a headless `AssistantPanel` smoke test. Commit and tag creation are deliberately excluded until explicit approval.
