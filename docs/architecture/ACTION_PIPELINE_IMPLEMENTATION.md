# Action Pipeline — Phase E

## Objective

`ActionPipeline` represents proposed assistant actions as explicit, immutable, validated, in-memory records. It is not an executor: it cannot confirm, apply, schedule, invoke callbacks, or write any action.

```text
Registered AssistantTool
          |
     ToolResultDTO
          |
   AssistantRuntime
          |
    ActionPipeline
          |
 ActionProposalDTO
```

## Contracts and validation

`ActionProposalDTO` contains a unique identifier, `ActionType`, title, description, recursively immutable basic-value payload, mandatory confirmation flag, and UTC timestamp. `ActionValidationDTO` reports validity, warnings, and errors as immutable tuples.

The pipeline accepts only proposals with a unique ID, enum action type, non-empty title, textual description, UTC timestamp, serializable basic payload, and `requires_confirmation=True`. Unsupported objects, callbacks, non-text keys, and optional confirmation are rejected before registration.

Initial action types are playlist creation, collection creation, library sync/export/import, and `CUSTOM`. `CUSTOM` preserves an unknown future tool proposal as data; it does not grant execution privileges.

## Runtime relationship

`AssistantRuntime` accepts an injected `ActionPipeline`. After ToolDispatcher returns a successful tool result, the Runtime translates any tool proposals into validated pipeline proposals and returns those records in `RuntimeResultDTO`. The Runtime neither confirms nor executes them.

## Safety boundaries

The pipeline has no UI, SQLite, repository, ORM, filesystem, network, model, subprocess, callback, or persistent-memory dependency. It owns no global state. Listing, reading, discarding, and clearing are in-memory lifecycle operations only.

## Future integrations and risks

A future confirmation service must revalidate a selected proposal against current authorization and application state before invoking a dedicated write service. Pipeline records are local and unbounded until discarded or cleared; future retention, audit persistence, redaction, and authorization policies must remain explicit.
