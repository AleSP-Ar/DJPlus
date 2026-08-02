# Policy and Confirmation Manager — Phase F

## Objective

`ConfirmationManager` decides whether a proposed action may be confirmed. It produces a typed decision only; it never executes, schedules, confirms through a service, or modifies the library.

```text
RuntimeRequestDTO.confirmation_request
              |
      AssistantRuntime
              |
   ConfirmationManager
              |
    ConfirmationPolicy
              |
 ConfirmationResultDTO
```

## Contracts and policy

`ConfirmationRequestDTO` identifies an action and carries a UTC request timestamp. `ConfirmationResultDTO` records whether a request was allowed and confirmed, the reason, and the UTC policy-check time. Both are immutable.

`ConfirmationPolicy` is a pure abstract contract. The initial `AlwaysRequireConfirmationPolicy` permits one confirmation only when the proposal is still present, has not been discarded, has not been confirmed before, and explicitly requires confirmation. Rejections explain whether the action is missing, discarded, duplicated, or invalid.

## Runtime relationship

`AssistantRuntime` optionally accepts a `ConfirmationManager` composed with the same `ActionPipeline` that holds its proposals. When a request provides `ConfirmationRequestDTO`, the Runtime returns the decision in `RuntimeResultDTO`. The original proposal remains unchanged and no action is invoked.

## Safety and future integration

The manager has no repository, ORM, SQLite, filesystem, network, UI, model, callback, or execution dependency. Its confirmed-ID record is in-memory session state solely for duplicate detection; it is not authorization, persistence, or an execution queue.

A later, separately approved write boundary must revalidate authorization and current application state after confirmation, then invoke a dedicated service. It must not treat this DTO as execution permission by itself.

## Risks

Confirmation history is ephemeral: restarting a process loses duplicate-detection state. Future persistence, authorization policies, expiration, retention, and audit logging require explicit design and must remain isolated from this decision-only layer.
