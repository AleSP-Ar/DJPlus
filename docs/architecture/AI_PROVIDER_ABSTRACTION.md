# AI Provider Abstraction - Epic 2, Phases A-G

## Objective

This phase introduces the provider boundary for future assistant model integrations without changing `AssistantRuntime`. It is local, deterministic, and contains no network client, credentials, model SDK, persistence access, or UI dependency.

## Public contract

`AssistantProvider` declares two operations:

- `capabilities()` returns `ProviderCapabilitiesDTO`.
- `complete(request)` accepts `ProviderRequestDTO` and returns `ProviderResponseDTO`.

`ProviderRequestDTO` carries a generated provider-neutral `PromptDTO` and a caller-owned request identifier. `ProviderResponseDTO` includes the response text, provenance, and optional planned `ToolCallDTO` values. A response cannot execute tools; future orchestration must continue to route those calls through `ToolDispatcher` and preserve confirmation rules.

`ProviderCapabilitiesDTO` declares provider name and version plus tool-call, streaming, and context-limit support. All three DTOs are frozen and validate their boundary inputs.

## Mock provider

`MockAssistantProvider` is the Phase A implementation. It selects a configured response by exact `PromptDTO.user_prompt`, otherwise returns its configured fallback. It does not make I/O, does not inspect application state, and returns the same output for the same request configuration. Its recorded `calls` list is intentionally test-only in-memory observation.

## Registry and selection

Phase B adds `ProviderRegistry`, an in-memory owner of already-created `AssistantProvider` instances. `register(provider, make_default=False)` rejects duplicate names after trim and case-insensitive normalization. `get_provider(name)` returns a registered instance, while `get_default_provider()` returns an explicitly configured default only. Missing names, including a missing default, raise `ProviderNotFoundError`.

`selection(name=None)` returns `ProviderSelectionDTO`, an immutable snapshot containing the canonical provider name, its `ProviderCapabilitiesDTO`, and whether it is the current default. `set_default(name)` changes only registry-local selection; it never invokes the provider or calls a model.

## Runtime integration

Phase C makes `ProviderRegistry` an optional `AssistantRuntime` dependency. A `RuntimeRequestDTO` can select a registered provider with `provider_name`; otherwise an injected registry must have an explicit default. The runtime converts the generated `PromptDTO` into `ProviderRequestDTO`, invokes `AssistantProvider.complete()`, validates the result, and exposes the resulting `ProviderResponseDTO` as `RuntimeResultDTO.assistant_response`.

`request_id` is optional on `RuntimeRequestDTO`. If omitted, the runtime derives a deterministic ID from the session ID and UTC timestamp. If no registry is injected, the existing provider-free behavior is preserved and `assistant_response` remains `None`. Provider tool calls remain planned data in `ProviderResponseDTO`; Phase C does not dispatch or execute them.

## Configuration and resilience

Phases D-E add `ProviderConfigDTO` and `RetryPolicyDTO` to every `ProviderRequestDTO`. They validate model, temperature (0 to 2), maximum output tokens, timeout, bounded retries (0 to 5), and virtual delay between retries. `AssistantRuntime` passes its validated request configuration to the provider request unchanged.

`ProviderPolicy` is the sole execution wrapper. It invokes one selected provider only, checks `ProviderCancellationToken` before each attempt, retries only typed retryable errors, and never sleeps or performs transport I/O. Timeout is cooperative and deterministic: the mock reports a simulated duration and the policy compares it with `timeout_ms`.

Every policy execution returns `ProviderExecutionResultDTO`. Successful results include `ProviderUsageDTO`, derived deterministically from whitespace-separated prompt and response words, plus virtual duration. Failures include `ProviderErrorDTO` with a stable code (`timeout`, `rate_limit`, `unavailable`, `invalid_response`, `cancelled`, or `provider_error`) and no response. The runtime exposes this result as `RuntimeResultDTO.provider_execution`; it maps a successful response to `assistant_response` and leaves it null on failure.

`MockAssistantProvider` supports deterministic `success`, `timeout`, `rate_limit`, `unavailable`, `invalid_response`, and `retry_success` scenarios. It has no network, SDK, real credentials, streaming, delay, or fallback behavior.

## Credentials and secret redaction

Phase F adds a separate credential boundary. `ProviderCredentialRefDTO` contains only a provider name and credential ID; it never contains the secret. `CredentialProvider` is abstract, while `InMemoryCredentialProvider` is a volatile test implementation with no environment lookup, network, or persistent storage. Missing references raise `CredentialNotFoundError` without including any credential value.

`ProviderConfigDTO` has no secret field. `ProviderRequestDTO` can carry only `credential_ref`, never a credential value. `AssistantRuntime` copies that reference into the provider request and never receives or resolves the secret. `MockAssistantProvider` can resolve a fake reference through `InMemoryCredentialProvider`, but retains only a resolution count for tests.

`SecretRedactor` removes configured values and common sensitive assignment shapes from strings and nested display data. `ProviderErrorDTO` applies the default redactor before exposing its message. The policy and mock use stable public error messages, so execution results, logs, and DTO representations do not reveal fake secret values.

## Transport abstraction

Phase G adds `ProviderTransport`, a separate contract for future provider adapters. `TransportRequestDTO` models method, URL, timeout, optional JSON or text body, a cooperative cancellation token, and normalized redacted headers. `TransportResponseDTO` carries status code, deterministic duration, redacted headers, and either JSON or text. `TransportErrorDTO` carries a stable typed error, retryability, optional status code, and duration.

`MockProviderTransport` is the only implementation in this phase. It returns deterministic success, timeout, unavailable, generic-error, or cancelled DTOs, performs no connection, and imports no HTTP library or SDK. The transport is intentionally not connected to `AssistantRuntime` yet; a later adapter phase must map provider serialization, credential resolution, and transport errors under explicit policy.

## Provider adapter completion

The Epic 2 sprint final adds `OpenAIProvider`, `OllamaProvider`, and `LMStudioProvider`. They are contract adapters only: each sends a normalized DTO to an injected `ProviderTransport` using a `mock://` endpoint, validates transport results, and maps text or supported JSON shapes to `ProviderResponseDTO`. `ProviderFactory` selects the adapter by normalized name. `ProviderCapabilityResolver` validates declared limits before transport dispatch.

Only `MockProviderTransport` is used by the test suite. No provider adapter connects to a real service, imports an SDK, reads a key, or supports provider fallback. The final Epic 2 architecture is summarized in `EPIC_2_PROVIDER_INFRASTRUCTURE.md`.

## Integration boundary

`AssistantRuntime` now resolves only already-registered local providers. A later phase may define how planned provider tool calls are validated and routed through the existing allowlist. That phase must set transport, redaction, authorization, timeout, error-handling, audit, and streaming policies explicitly.

## Risks

The abstraction does not yet enforce transport security, context-size truncation, schema validation for model-generated tool calls, cancellation, retries, or provider error normalization. No real provider should be connected before those policies are designed and tested.
