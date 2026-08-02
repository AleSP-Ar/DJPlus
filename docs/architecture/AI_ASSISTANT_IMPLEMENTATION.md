# AI Assistant Foundation — v0.8

## Implemented boundary

v0.8 introduces an allowlisted, provider-free assistant boundary:

```text
Caller / future AI model
        |
AssistantFacade
        |
AssistantTool allowlist
        |
Injected existing services
        |
AssistantResponseDTO
```

No model, prompt interpreter, network call, API credential, SQL, filesystem operation, repository, ORM object, SQLite session, or arbitrary execution capability is implemented.

## Tools

| Tool | Allowed data | Output |
|---|---|---|
| `library_query` | total track count through injected library service | bounded library statistic |
| `playlist_insight` | playlist and associated-track counts through injected playlist service | aggregate statistic and optional playlist proposal |
| `dj_compatibility` | caller-provided track-compatible DTOs through `DJIntelligenceService` | deterministic score, reasons, confidence |

Tools expose `name`, description, input schema, and `execute()`. The facade registers a fixed unique set at construction and rejects unknown names. Tools return `AssistantToolResultDTO`; the facade converts it to `AssistantResponseDTO`.

## Proposals and confirmation

An action proposal is descriptive data only: action type, label, and payload. For example, `playlist_insight` can propose “Crear playlist Progressive Sunset”. The response marks `requires_confirmation=True` whenever it contains proposals.

This foundation intentionally has no apply/confirm execution method. Therefore confirmation cannot cause any write, playlist creation, file change, sync, or background work in v0.8.

## Safety boundaries

- The assistant can invoke only registered `AssistantTool` instances.
- Tool schemas are published as data; they are not executable instructions.
- Services are injected into narrow tools; the facade does not import repositories or persistence layers.
- Responses contain selected DTO fields only, never ORM objects or file paths by default.
- Proposed actions are separated from read results and cannot be invoked by the facade.

## Future integrations

A future provider adapter may transform model tool calls into `AssistantFacade.execute()` requests only after schema validation, rate limits, redaction, audit policy, and opt-in decisions are approved. A future confirmed-action service must validate proposal payloads through existing application services and record an audit event before writing.

## Deferred and risks

- No natural-language parsing, remote model, local model, authentication, credential handling, audit persistence, or streaming.
- Existing service data may need additional privacy-oriented facades before being exposed to a remote provider.
- A model can still suggest unsuitable actions in future; deterministic validation and explicit user confirmation remain mandatory.
