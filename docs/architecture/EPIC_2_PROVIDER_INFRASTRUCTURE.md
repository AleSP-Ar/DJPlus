# Epic 2 - Provider Infrastructure Completion

Epic 2 establishes a provider-neutral assistant integration boundary without enabling real connectivity.

## Delivered layers

1. Provider DTOs, deterministic mock provider, registry, default selection, configuration, retries, cancellation, metrics, typed errors, and credential references.
2. In-memory credential testing and secret redaction for headers, payloads, errors, and public DTOs.
3. Transport DTOs for redacted headers, timeout, cooperative cancellation, status code, duration, and JSON or text bodies; only `MockProviderTransport` is implemented.
4. `OpenAIProvider`, `OllamaProvider`, and `LMStudioProvider` contract adapters. They serialize a provider-neutral request to a `mock://` transport endpoint, validate `ProviderCapabilitiesDTO`, and map only transport DTOs back to `ProviderResponseDTO` or typed provider errors.
5. `ProviderFactory` selects adapters by normalized provider name. `ProviderCapabilityResolver` rejects requests whose `max_tokens` exceed the declared capacity and rejects registered tools for providers that do not declare tool-call support.

## Safety boundary

There is no network client, SDK, environment lookup, persistent credential store, real endpoint, real key, streaming implementation, or provider fallback. `AssistantRuntime` selects registered providers and passes only validated DTOs, configuration, and credential references. It has no transport client and never resolves a secret.

## Deferred work

Before a real adapter is permitted, define explicit transport allowlists, endpoint ownership, TLS/proxy policy, request serialization schemas, actual timeout and cancellation semantics, rate-limit policy, audit retention, usage reconciliation, model capability discovery, and end-to-end security review.
