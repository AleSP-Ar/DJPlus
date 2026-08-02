# AI Assistant Foundation Design — v0.7 Proposal

## Goal

Add an assistant boundary that can answer questions about the library and prepare explainable drafts without granting an AI model direct access to SQLite, filesystem paths, application services, or UI widgets.

## Architecture

```text
User / future chat UI
        |
        v
AssistantFacade
  | policy, identity, audit, confirmation
  v
Tool registry (allowlisted DTO contracts)
  |                 |
  v                 v
LibraryQueryFacade  RecommendationFacade
  |                 |
  +---- existing application services ----+
```

`AssistantFacade` is provider-neutral. A local model, remote API, or deterministic test double receives only tool schemas and bounded tool results. Provider credentials and network calls remain in a dedicated adapter, never in the core library services.

## Tool classes

| Class | Examples | Permission |
|---|---|---|
| Read-only library | search tracks, summarize BPM/key/energy ranges, inspect playlists | allowlisted, paginated, redacted DTOs |
| Read-only history | session summaries, recent selections, usage patterns | opt-in and time-bounded |
| Draft generation | playlist proposal, smart-crate proposal, transition candidates | returns a draft with rationale; no write |
| Confirmed action | create playlist, save crate rules | explicit user confirmation, validated service command, audit event |

The first implementation must include only read-only tools and draft generation. Confirmed actions are a later increment after command validation and audit storage are approved.

## Data minimization and privacy

- Tools return only fields needed for the request; filepath, raw error text, and unrelated history are excluded by default.
- Results are capped, paginated, and summarized before leaving the process.
- Remote providers require an explicit opt-in, clear provider disclosure, and a policy for retention and transmission.
- Prompt content, tool calls, and model output need a configurable audit/redaction policy before persistent logging.
- Credentials use an environment or OS-secret adapter, never SQLite rows, source control, or model prompts.

## Safety and correctness

- The model cannot issue SQL, invoke repository methods, access files, run shell commands, or create background work directly.
- Tool arguments are validated as typed DTOs and translated to existing service contracts.
- Every recommendation includes its inputs, constraints, and confidence/uncertainty where available.
- Ambiguous requests trigger clarification or conservative read-only results; the assistant must not infer consent for a write.
- Drafts expire when referenced tracks, analysis snapshots, or library query versions change.

## DJ use cases

- “Find 20 tracks near 124 BPM and compatible with this key.”
- “Draft a warm-up playlist with gradually increasing energy.”
- “Summarize this session’s selections and identify repeated artists.”
- “Explain why these transition candidates are compatible.”

Outputs are recommendations, not assertions of musical truth. They must remain explainable through deterministic filters and the future DJ Intelligence scores.

## Integration with analysis and intelligence

The assistant consumes analysis and intelligence through DTOs. It never invokes a DSP provider, chooses an algorithm version, or persists derived analysis directly. If analysis is absent or stale, tool output must state that limitation rather than fabricate BPM, key, energy, or waveform knowledge.

## Risks and gates

| Risk | Mitigation before implementation |
|---|---|
| Data disclosure to a remote provider | opt-in, field-level minimization, redaction review |
| Hallucinated or unsafe action | read-only first, typed tools, explicit confirmation |
| Opaque recommendations | rationale, deterministic score inputs, user-visible constraints |
| Cost and latency | quotas, cancellation, provider timeout, local test double |
| Prompt injection in tags/metadata | treat library text as untrusted data, isolate tool instructions |

## Deferred decisions

- Model/provider selection and whether a local option is required.
- Authentication, usage budgets, and retention policy.
- Audit persistence migration.
- Any autonomous playlist write, sync action, or playback control.
