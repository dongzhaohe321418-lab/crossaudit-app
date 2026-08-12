# CrossAudit Kernel — Product and Architecture Target

## Product promise

CrossAudit should feel like a first-class coding agent with independent audit,
not like an audit dashboard wrapped around a collection of commands.

The user creates a workspace, speaks to one assistant, grants capabilities when
needed, watches concise live progress, receives useful files or code, and can
leave the application running. A Generator performs the work. An independently
sourced Auditor reviews immutable snapshots before they may be admitted. The
user sees the work, the decision, and the actions that require them; protocol
internals remain available for inspection but never become the primary product.

The ideal product has the working surface expected of a modern agentic desktop
application:

- projects containing persistent conversations, files, instructions and tools;
- local workspaces plus optional GitHub publication;
- model, reasoning-effort and provider switching without restarting a task;
- streamed progress, cancellation, crash recovery and reliable background work;
- file input by picker or drag-and-drop and first-class file previews/exports;
- explicit permission for MCP, remote compute and other consequential actions;
- independent, fail-closed audit with bounded automatic revision;
- a clear human-decision surface when automation cannot proceed safely;
- bilingual, accessible, native-feeling interaction without exposing internal
  receipts, routing rows or implementation signals by default.

## Protocol invariants

An architectural rewrite may replace any implementation except these properties:

1. Generator and Auditor remain vendor-independent under the configured policy.
2. The Auditor reviews an immutable artifact snapshot, never a moving worktree.
3. Invalid or unavailable audit cannot produce PASS.
4. Every admitted result is bound to its exact artifact, rules and audit evidence.
5. Automatic revision is bounded; unresolved work becomes an explicit human task.
6. Generator narrative and private reasoning never enter the Auditor context.
7. External effects are attributable, permissioned and replayable from metadata.
8. Credentials never enter project files, prompts, logs, events or the UI response.

## Architectural rule

There is one operational fact model:

> Commands request change, Events record facts, a pure reducer derives RunState,
> and UI/CLI read projections of that state.

Git remains the immutable evidence and artifact substrate. It is not the live
process database. SQLite WAL is the local operational store. Operational events
are explicitly not audit verdicts; evidence-bearing milestones are anchored to
the signed receipt and Git object identifiers.

## Target components

```text
Native shell / UI / CLI
          |
       Local API
          |
      Command bus
          |
    Project actor  ----- one serialized mutation lane per project
          |
      Run reducer  ----- deterministic transition table
          |
  Event store + outbox - atomic state and pending external effects
          |
  Provider / Git / GitHub / Capability adapters
```

### Run state

The canonical states are:

```text
DRAFT -> QUEUED -> GENERATING -> AUDITING -> PASSED
                       |             |
                       |             +-> REVISING -> GENERATING
                       +-> WAITING_FOR_CAPABILITY
                       +-> WAITING_FOR_PROVIDER
                       +-> WAITING_FOR_HUMAN

Any active state -> CANCELLING -> CANCELLED
Any active state -> FAILED
```

Provider exhaustion, audit round exhaustion, capability approval and a crashed
worker are states or events, not special error strings interpreted by the UI.

### Workspaces and Git

An agent run never writes or commits through the user's checked-out branch.
It receives a private worktree and `refs/crossaudit/runs/<run-id>` ref. Every
audit reviews one commit from that ref. PASS may publish through an explicit
policy (export files, create a commit/branch, open a PR, or update a configured
branch). Dirty user files cannot contaminate or block an audit run.

### External effects

Provider calls, GitHub repository creation, MCP calls and HPC submissions use a
durable outbox. Each effect has an idempotency key and typed result. Multi-step
project provisioning is a resumable saga; restarting the app continues or
compensates an incomplete setup instead of leaving an opaque failed job.

### Capabilities

MCP, HPC and future tools share one capability protocol:

```text
CapabilityRequested -> PolicyEvaluated -> Approved/Denied
Approved -> ExecutionStarted -> Progress* -> Completed/Failed
Completed -> ArtifactImported
```

Provider adapters similarly return a closed result vocabulary rather than text
that callers must parse: completion, tool request, authentication required,
model unavailable, rate limited, context exceeded, subscription unavailable or
transport unavailable.

### UI projections

The UI receives a stable, typed read model. It never reconstructs status from
Git, controller JSON, in-memory progress and crash flags. Live events carry a
monotonic sequence number so reconnect resumes without polling gaps. Durable
facts are localized by message key, not by replacing rendered English text.

### Safe autonomy policy

Autonomy is classified by consequence rather than exposed as a growing set of
user-facing modes:

- The Generator owns reversible delivery choices: focus, tone, structure,
  filename, and a sensible default format.
- The controller deterministically binds explicit PDF/DOCX intent to the local
  auditable renderer. It does not ask the model to decide a security boundary.
- A low-confidence work request or read-only query uses a recorded safe default
  instead of interrupting the user. The original confidence remains observable.
- Pressing Send authorizes the current instruction and its visibly attached
  files in one action; the server still refuses attachment payloads whose
  explicit authorization bit is absent.
- Constitution amendments, audit disputes and resolutions, destructive actions,
  new GitHub/MCP/HPC authority, credentials, and unresolved audit outcomes stay
  human-owned. The Generator can never approve its own work.

The product should ask only when a decision is consequential, ambiguous, and
cannot be safely reversed. Asking for ordinary presentation preferences is a
failure of task planning, not a safety feature.

## Complexity budget

The migration is successful when the product reaches all of these conditions:

- one RunState reducer and transition table;
- one local operational database per workspace;
- one background supervisor for the application;
- one command path shared by UI and CLI;
- zero durable jobs held only in process memory;
- zero UI actions selected by parsing exception text;
- zero regex-based edits of project configuration;
- zero agent commits through a user's active worktree;
- crash recovery tested at every external-effect boundary;
- every provider passes the same adapter contract suite;
- every visible task state is derivable from one event sequence.

## Migration strategy

This is a strangler migration, not a second product beside the first:

1. Introduce the canonical run model and durable event journal behind the
   existing progress API. Remove the in-memory/crash-marker split once parity is
   proven.
2. Route UI and CLI start/retry/cancel commands through one application service.
3. Add a durable effect outbox and convert provider calls first, then GitHub,
   MCP and HPC.
4. Move generation into private worktrees and make publication a separate step.
5. Convert project provisioning to a saga and migrate configuration to a typed,
   atomic store with a human-readable export.
6. Replace the embedded page with a typed frontend consuming projections.
7. Delete compatibility paths after migration and measure the reduction in
   state sources, branches and recovery-specific code.

Every slice must preserve the protocol invariants, include crash/concurrency
tests, and leave a shippable application. A feature is not accepted merely
because its happy path works.

## Implemented foundation (2026-08-12)

The first strangler slice is now in the V4 product rather than living only in
this design document:

- `runtime.sqlite3` is the canonical operational store for run lifecycle and
  resumable project-provisioning jobs. It uses WAL, full synchronous commits,
  process ownership and an explicit transition table.
- The console tracker is a projection of that journal. New runs no longer
  create `build-in-flight.json`; the old marker is read only to recover projects
  created by earlier builds.
- Project setup stores a credential-free specification, safe UI draft, steps,
  issue and result. A dead owner becomes a retryable task after restart instead
  of leaving an unowned in-memory closure.
- A forced-kill test against the installed frozen application preserved the
  task, Chat, last working actor and last useful detail. Dismissal changed only
  the operational notice and did not alter project files or evidence.
- The official Codex subscription adapter denies tool requests in its isolated,
  read-only, network-disabled thread but now lets the model recover to a valid
  text answer. A blocked tool with no valid text still fails closed.
- CLI builds, UI starts, human-authorized retries and cancellation now cross one
  `RunCommandService`. That service alone acquires the project mutation lease,
  creates the durable Run, appends typed events, classifies failures, records the
  terminal outcome and releases the lease.
- Cancellation is an atomic `cancel_requested` fact rather than an in-memory
  flag. It is idempotent, visible through the live projection and wins a race
  with a late provider result; the UI exposes it only while the selected Chat
  has active work.
- The console `Tracker` has no start/step/finish/dismiss lifecycle and performs
  no recovery while binding. It only reads SQLite and wakes subscribers after a
  command-side transaction. The <=4.14 JSON crash marker remains a read-once
  migration input, not a second current state source.

This is deliberately not declared a completed rewrite. The compatibility
surface is substantially smaller, but generation still mutates the user's
active worktree, provider/GitHub/MCP/HPC effects do not yet share a transactional
outbox, configuration updates still contain line-oriented edits, and the
embedded UI, HTTP server and project service remain large modules. Cancellation
is cooperative at typed event boundaries; it cannot preempt a blocked provider
socket safely. Project provisioning has a durable journal but is not yet a
general saga actor. The next highest-leverage slice is therefore the private Run
worktree plus publication boundary, followed by the effect outbox. Adding more
top-level controls before those seams exist would increase, not reduce, product
complexity.
