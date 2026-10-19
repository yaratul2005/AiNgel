# Aingel Project Plan

## Project understanding

Aingel is intended to be a model-agnostic Python framework for persistent agents. Its core is the state that must survive model swaps (identity, memory, drives, and functional affect), surrounded by a heartbeat, pluggable model adapters, tools, and a strict conscience layer for permissions, budgets, approvals, emergency stop, and auditability.

At the baseline commit, the repository was a design document containing only `Readme.md`, with no package, configuration, test suite, CI, license file, contributor policy file, constitution, or executable quickstart. The README remains the product specification. Its intended safeguards and honest framing should be treated as requirements, not as implemented capabilities.

## Current implementation status

The offline foundation and first soul slice are now present: package metadata, TOML config validation, brain/tool contracts, a registry, a tick runner, step budget, kill switch, conscience decisions, JSONL audit, identity, bounded affect, SQLite memory, and action reflection. The CLI carries memory across two fake-brain ticks. Tests cover the safety boundary and soul state; CI is configured to run Ruff and pytest on Python 3.11 through 3.13. A live model adapter, external tool, approval UI, and OS sandbox remain unimplemented.

## Success criteria

The first useful release should let a developer run a deterministic, offline agent tick with a fake brain and fake tools; inspect exactly what happened; and prove that denied, unknown, or over-budget actions never execute. Beyond that foundation, a user should be able to opt into a configured model adapter and workspace-scoped tools without changing the soul or bypassing the conscience.

Track progress with these observable outcomes:

- A clean Python 3.11+ environment can install the package and run the documented sandbox quickstart.
- Core behavior is deterministic and tested without network access or a live model.
- Every proposed tool call is validated, checked by the conscience, and audited before execution; denied calls have no side effects.
- Kill switch and each configured budget stop work promptly, including between tool calls.
- Memory persists across process restarts and model-adapter changes.
- External tools remain unavailable by default; expansion requires explicit configuration and documented safety tests.

## Recommended delivery sequence

### 0. Resolve the project contract

- Choose and record the license before accepting contributions; the README currently only recommends options.
- Add concise contributor/agent guidance and a human-reviewed constitution, or adjust the README until those files exist.
- Decide the public API and initial supported runtime/dependency policy. Keep the core standard-library-heavy.
- Clarify operating modes and defaults: `sandbox` must be enforceable by code, not just a prompt or a configuration label.

**Exit:** repository instructions and quickstart refer only to files and behavior that exist, and safety defaults are unambiguous.

### 1. Create a runnable, offline foundation

- Add package metadata, module entry point, configuration parsing/validation, and a minimal CLI.
- Define typed contracts for brain responses/tool calls, tools, events, and conscience verdicts.
- Implement a scripted fake brain, in-memory/fake tools, structured audit events, and a single-step runner.
- Establish formatting/linting and a fast unit-test workflow; no network or model service should be needed.

**Exit:** a fresh environment can install and run one deterministic tick; malformed config and malformed model responses fail clearly.

### 2. Implement conscience before executable capabilities

- Build permission decisions from tool identity, declared risk, validated arguments, mode, and explicit policy.
- Add hard step/time/token/cost/request budgets with clear exhaustion behavior.
- Add a kill switch checked at startup and between every action.
- Make audit records append-only, structured, and sufficient to reconstruct decisions and outcomes; define how sensitive arguments/results are redacted.
- Ensure unknown tools, invalid arguments, policy errors, and approval timeouts fail closed.

**Exit:** tests demonstrate that denied, unknown, malformed, over-budget, and stopped actions never invoke a tool; every decision is auditable.

### 3. Complete the safe vertical slice

- Implement the heartbeat around dependency-injected brain, soul, body, conscience, clock, and sleep behavior.
- Add identity/constitution loading and bounded affect with explicit event rules.
- Add SQLite episodic memory with deterministic recency/keyword recall and migrations/schema versioning.
- Add reflection as a bounded, inspectable update; separate model-generated claims from trusted system state.
- Define how untrusted tool output is represented and passed back to the brain.

**Exit:** an end-to-end offline scenario runs multiple ticks, persists memory, emits an auditable trace, honors stop/budget controls, and is reproducible in tests.

### 4. Add a model adapter as an optional integration

- Implement Ollama behind the brain interface with timeouts, response validation, and actionable connection errors.
- Keep adapter tests mocked; add a manual integration check that is clearly optional.
- Ensure model output can only propose calls; it cannot grant itself permissions or modify trusted policy/state.

**Exit:** swapping fake brain for Ollama changes no soul, tool, or conscience APIs; default sandbox operation remains offline and tool-free.

### 5. Add narrowly scoped tools

- Start with workspace-only file read/write tools, path normalization, symlink/traversal defenses, size limits, and explicit risk labels.
- Add approval handling for medium/high risk actions only after a real human approval channel is defined.
- Add isolated execution only after choosing and verifying an actual OS/container sandbox boundary; do not describe a subprocess as a sandbox.
- Add web access last, behind domain allowlists, request/time/size limits, and untrusted-content handling.

**Exit:** each tool has argument, authorization, allowed-path/domain, failure, and side-effect tests; no tool can escape its configured boundary.

### 6. Release and grow from evidence

- Add CI for supported Python versions, lint, type checks if adopted, and tests; document installation and configuration from a clean checkout.
- Add examples and threat-model notes; benchmark reliability, latency, memory behavior, and safety outcomes before adding autonomy features.
- Defer embeddings, self-directed goal planning, MCP, multi-agent communication, and C++ until core behavior and isolation needs are demonstrated.
- Keep autonomous mode disabled until promotion criteria, monitoring, rollback, and operator controls are specified and exercised.

**Exit:** a tagged release has reproducible installation, documented limitations, CI evidence, and a reviewed threat model.

## First implementation milestone

Build only the offline foundation plus conscience and a single-tick runner. Suggested first vertical scenario: a scripted brain proposes one allowed low-risk fake action followed by one denied high-risk action; the runner records both verdicts, executes only the allowed action, then stops when the configured step budget is reached. This proves the most important architecture boundary before adding persistence, a live model, or external tools.

## Risks and decisions to resolve early

| Risk or ambiguity | Why it matters | Recommended handling |
|---|---|---|
| README lists body tools before conscience is complete | Creates pressure to expose capabilities before enforcement exists | Reorder roadmap so policy, budgets, kill switch, and audit gates precede any executable tool |
| Sandbox is described as a mode but enforcement boundary is unspecified | Configuration or prompt rules alone cannot contain host effects | Keep initial runner tool-free; later document and verify OS/container isolation explicitly |
| Ollama example accepts `tools` but does not pass them to the API | Example implies tool calling that it does not implement | Treat as text-only adapter initially or implement and validate provider tool-call mapping |
| `MemoryStore.recall(query)` has no retrieval contract | Results and performance will be hard to test or evolve | Specify deterministic initial ordering/filtering and keep embeddings behind the same contract |
| “Append-only” audit and replay lack storage/tamper model | Logs may be incomplete, mutable, or leak sensitive data | Define event schema, durability, redaction, and replay guarantees before tools are enabled |
| Autonomous mode and approval flow are underspecified | Operators need to know what runs and how to stop it | Leave autonomous mode unavailable until explicit policy and approval UX exist |
| README references missing files and quickstart assets | New contributors cannot follow setup or governance instructions | Keep docs synchronized with implemented artifacts; add example config and constitution as part of foundation |

## Working rules

- Treat this plan and README as intended direction; verify repository state before implementation.
- Keep changes small and layer-focused, with tests around behavior and especially denied paths.
- Never make a tool executable outside the conscience path.
- Do not claim subjective feelings or safety properties that have not been implemented and verified.
- Keep secrets, untrusted input, and model-generated text out of trusted policy decisions.
