# CrossAudit North Star — Product and Engineering Constitution

> Authored by the project owner, 2026-08-12. This is the long-term product
> North Star and engineering constitution. It is not a checklist to implement
> in one pass: inspect the current system first, preserve working invariants,
> and implement through tested vertical slices. The first required response
> (§38) is recorded in the session that admitted this document; subsequent
> work cites this file.
>
> Precedence: protocol semantics in `DESIGN.md` still govern the audit
> protocol itself; visual judgement is governed by
> `design/VISUAL_DECISION_SYSTEM.md`; this document governs product scope,
> architecture direction, and quality bars. Where documents conflict at the
> same altitude, the newest dated amendment wins.

Mission: transform CrossAudit into a coherent, dependable, native-feeling
agentic desktop application — "everything users expect from a modern coding
and research agent, with an independent audit system built into its
foundation." Approachable to a first-time user, powerful for professional
developers, extensible for scientists on remote HPC.

Do not push, publish, delete user data, rewrite history, or make destructive
migrations without explicit authorization.

## 1. Product definition

CrossAudit is a local-first agentic workspace in which the user describes a
goal; the Generator performs the work; the Auditor independently evaluates it
against a visible, versioned constitution; CrossAudit controls the loop,
records evidence, handles failures, and determines admissibility; the user
sees the requested result first, not internal audit noise; human intervention
is requested only when the system cannot proceed safely or confidently.

It must not feel like: a CI dashboard, an enterprise admin panel, a terminal
wrapper, disconnected configuration forms, a SaaS card template, a chat UI
with audit logs pasted underneath, or a visual clone of any commercial agent
product. Personality: calm, precise, trustworthy, intelligent; minimal but not
empty; powerful but progressively disclosed; scientific without bureaucracy;
dark, focused, native-feeling.

## 2. Canonical vocabulary

**Workspace** a user-selected local root that may contain multiple projects ·
**Project** a durable unit of work with its own configuration, repositories,
constitution, provider routes, threads, files, runs, costs, and background
worker · **Thread** a conversation inside a project (rename, pin, archive,
search, duplicate, delete) · **Run** one user-requested execution from start
to terminal state · **Round** one Generator → deterministic checks → Auditor
iteration within a run · **Artifact** an input file, generated deliverable,
imported dataset, previewable output, or remote result · **Finding** a
structured issue from deterministic checks or the Auditor · **Decision** a
human intervention requested because CrossAudit cannot safely continue ·
**Receipt** a content-addressed record of a completed audit decision and its
evidence · **Constitution** a versioned collection of audit rules, policies,
exceptions, amendments · **Provider route** a model/provider configuration
for a role, including fallbacks and capabilities.

Do not overload "project", "cycle", "task", or "workspace".

## 3. Information architecture

Four levels: Application Home → Workspace → Project → Thread/Run.
Global navigation: Home, Projects, Search, Background activity, Usage,
Connections, Settings, Help/diagnostics. Project navigation: Threads, Files,
Runs, Audit, Compute, Integrations, Project settings. Rarely-used functions
live behind contextual entry points or "More", never permanent chrome.

Desktop shell: left sidebar (navigation, projects, pinned/recent threads);
main canvas; optional right inspector (audit evidence, file metadata, run
details, usage, compute), collapsible, never squeezing main content below
usable width; bottom composer persistent only inside a thread; compact global
status area. Small windows: sidebar becomes overlay, inspector becomes sheet,
composer stays reachable, no content hidden behind the composer, the last
line of every scroll container remains visible with correct bottom padding
and safe-area handling.

## 4. First launch

Usable within two minutes. Welcome ("Build with one agent. Verify with
another." — create first project / open existing / import / explore local
demo without credentials; no receipt-schema/DCL/isolation jargon up front).
System readiness runs Doctor in the background with outcomes (Ready / Needs
attention / Optional enhancement), plain-language explanation, why it
matters, automatic repair when safe, guided repair otherwise, re-check, and
expandable technical detail. Provider setup is capability-driven, not
hardcoded layout; verify current official documentation before implementing
or updating any provider. Authentication: API key, cloud credential profile,
official OAuth/device/account-linking flows where officially supported, local
endpoints when explicitly configured. Never scrape browser cookies, reuse
consumer subscription sessions as unofficial API credentials, imply consumer
subscriptions include API access, bypass provider rules, or store secrets in
plaintext by default; use the OS keychain. Key fields support paste,
shortcuts, password-manager paste, temporary reveal, clear, validate,
replace, explicit copy only, immediate log redaction. Generator/Auditor
selection defaults to automatic recommendation with one-sentence role
explanations; enforce provider independence when the constitution requires
it; model selectors show name, provider, context window, tool/vision/
structured-output support, reasoning controls, speed, availability, price,
auth status — and show only controls the selected model supports (parameter
translation such as max_tokens vs max_completion_tokens is resolved inside
adapters, never surfaced as user errors).

## 5. Project creation

Staged, reversible, visually calm; never one giant form. Basics (name,
description, path, new/existing folder, recent locations, native picker,
permission and disk checks) → Source control (local only / connect existing /
create working repo / create working + independent audit repos; OAuth/device
flow, gh session, PAT fallback; account, org, permissions, ownership shown;
editable names, owner, visibility, description, default branch main;
pre-creation validation, collision checks, permission explanation, exact
preview; deterministic resumable progress; on partial failure show what
succeeded, offer Retry / Change name / Use existing / Continue locally / Roll
back newly created empty repositories, never auto-delete a non-empty repo; a
dirty local folder gets safe choices — use as-is, isolated worktree, new
subfolder, commit, stash, choose another — never discarded) → Agents
(automatic recommendation; provider/model per role; fallbacks; effort;
budgets; max automatic audit rounds explained as "how many times CrossAudit
may revise and re-check before asking you to decide") → Audit policy presets
(Standard, Strict, Research, Software engineering, Regulated, Custom) with a
short summary and full constitution editing after creation → Review (path,
repo plan, roles, policy, privacy and cost) → Create, then enter the project
immediately with live setup progress.

## 6. Project home and multi-project runtime

Each project runs independently: separate state, event journal, worker
identity, cancellation token, provider configuration, budgets, working
directory, locks, SSH/HPC jobs, failure boundaries. One crashed project must
not block another. Project rows show name, plain-language activity, compact
live progress, role status, last meaningful result, pending decision,
connection health, usage, last-updated, pin, open, and a context menu
(rename, archive, duplicate, export, delete). Progress comes from durable
runtime state, never a decorative timer. Opening a project shows current run
state immediately. Live streams are backed by a persistent event journal; on
reconnect: snapshot, replay, deduplicate, resume, never regress. Deletion
distinguishes removing from CrossAudit / moving local files to Trash /
deleting GitHub repositories — never one ambiguous button; GitHub deletion
requires separate confirmation and authorization.

## 7. Project workspace

Header: back, project name, branch, sync status, background status, compact
audit state, search, project controls. One logical conversation for user,
Generator, Auditor, Controller, and system events — with unequal visual
weight: user request; final answer and deliverables; important Generator
progress; audit decision; technical evidence last. Internal audit activity
collapsed by default. Routing: no mention = CrossAudit routes; @Generator =
direct work instruction; @Auditor = independent analysis; @CrossAudit =
orchestration/system questions. Mentions autocomplete; users never need
orchestration syntax.

## 8. Composer

The centre of the product. Supports plain-language instructions, multiline,
drag-and-drop, add button, folder attachment, clipboard images, pasted text,
mention routing, voice where supported, model switching, effort switching,
stop, resume, retry, queue-after-current, schedule where supported,
local/remote execution context, context summary. Default controls stay
minimal (add, input, send, compact Auto indicator); advanced controls live in
a popover (models, effort, cost ceiling, execution location, audit
strictness, output preference). The Generator infers reversible preferences
(filename, emphasis, tone, structure, formatting, internal-vs-deliverable,
whether Markdown suffices) and asks only when a choice is irreversible,
expensive, security-sensitive, legally significant, materially ambiguous, or
has no safe default — as compact choice cards, never an interrogation form.
An explicit user choice is never re-asked.

## 9. File input

Effectively unrestricted without false promises: no arbitrary UI file-count
limits; multiple selection, folder upload, recursive import, drag-and-drop,
incremental attachment, background hashing and indexing, resumable copying,
duplicate detection, large-file streaming, cancellation, per-file recovery.
Real constraints (disk, filesystem, provider context, endpoint limits,
policies, security) are explained precisely. Never load an entire large file
into memory; stream, chunk, index, summarize, retrieve. Attachments show
name, type, size, progress, state, remove, preview, and how they will be
used. Security: detect executables, never execute uploads, guard archive
extraction against traversal and bombs, handle symlinks explicitly, warn on
sensitive patterns, require authorization outside the workspace.

## 10. File output and artifacts

Deliverables are visually separated from internal audit artifacts and appear
as polished cards: icon/type, human title, filename, size, time, description,
preview, open, reveal, save-as, export, copy path, version history, audit
status; multi-file deliverables group. Internal metadata, receipts, prompts
and scratch never masquerade as requested outputs — they live under audit
evidence / run details / advanced. Real generation for Markdown, text, PDF,
DOCX, HTML, JSON, CSV, XLSX, PPTX, images where appropriate, code repos, ZIP,
scientific formats where supported. PDF/DOCX must be real, validated,
previewable — never renamed placeholders.

## 11. Universal file preview

Native-feeling preview: text/code (highlighting, search, line numbers, wrap,
copy, diff, virtualization); Markdown (rendered + source, outline, tables,
math where supported); PDF (thumbnails, search, zoom, navigation, export);
DOCX (accurate render, structure, search, export); spreadsheets (tabs,
virtualized grid, frozen header, formatting, search, CSV export);
presentations (thumbnails, main preview, notes); images (zoom, pan, metadata,
transparency); audio/video (playback, timeline, metadata, transcript when
generated); archives (safe manifest, no execution, selective extraction);
notebooks (cells, outputs, safe static preview); scientific formats (CIF/PDB,
spectra, tabular results, scheduler logs) where practical; unknown formats
(metadata, safe hex/text, open externally, reveal).

## 12. Audit experience

Foundational but not dominant. Compact indicator: Working, Checking,
Revising, Passed, Needs your decision, Stopped, Failed safely. Progress in
meaningful stages (understanding, preparing, generating, deterministic
checks, independent audit, revising, preparing final result); no raw internal
event names in primary UI. Expanded Audit Inspector: round and limit,
constitution version, deterministic results, auditor conclusion, findings by
severity, evidence references, revision history, provider/model identities,
receipt status, admission status, cost, log export. Findings carry severity,
rule ID, plain title, explanation, evidence, affected artifact/line,
recommended correction, blocking status, resolution status and round. Users
must understand failure without reading source code.

## 13. Dynamic constitution

Editable, versioned, auditable, safe: view, search, filter, enable/disable
permitted rules, add, amend, deprecate, scoped exceptions, compare versions,
restore-via-new-amendment, export/import, natural-language editing assisted
by the Auditor, consistency validation, effect preview, testing against
historical runs. Every change records author, timestamp, reason, diff,
scope, effect on active runs, approval state. Active runs pin their
constitution version unless explicitly migrated. A model may propose
amendments but never silently weakens rules or approves its own amendment.

## 14. Loop and human decisions

An explicit durable state machine (queued, preparing, generating,
deterministic_checking, auditing, revising, passed, blocked, awaiting_human,
provider_unavailable, paused, cancelled, failed_safe, completed). Every
transition validated, persisted, idempotent, observable, recoverable.
"One cycle and then nothing happens" must be structurally impossible: use
heartbeats, lease ownership, stale-worker detection, watchdogs, durable
queues, retry budgets, idempotency keys, event sequence numbers, crash
recovery, clear terminal states. On exhaustion, a dedicated decision
interface titled "CrossAudit needs your decision" summarizes what was asked,
what completed, why revision stopped, remaining findings, what each round
tried, and whether the problem is content, provider, rule conflict, missing
information, tooling, cost, or infrastructure. Actions may include guidance +
one more round, answering a question, changing output requirements, amending
a rule, documented exception where policy permits, switching provider/model,
raising budget, pausing, or stopping without admission. Never show "0
findings" when the real problem is infrastructure. Human decisions enter the
permanent audit record. Models never approve their own blocked result.

## 15. Provider failure and fallback

Classify accurately: invalid credentials, permission denied, model
unavailable, rate limited, quota exhausted, billing, context limit,
unsupported parameter, empty/invalid completion, timeout, outage, tool
incompatibility, safety refusal, unknown. Adapters translate provider errors
into stable CrossAudit error types; unsupported parameters are prevented via
capability metadata. Fallbacks: only user-authorized routes, preserving
independence constraints, visibly activated, with recalculated cost and
capability implications; never silently move sensitive data across
providers; never retry indefinitely. Remediation actions: retry, validate
credential, replace key, select model, use fallback, reduce context, open
billing, continue later, stop safely. Expired credentials pause the project
safely under "Needs attention".

## 16. Model and reasoning control

Default Auto, considering task type, modalities, context size, tools,
constitution strictness, latency, budget, provider health, isolation.
Advanced overrides: models, effort, context strategy, fallback order, cost
ceiling, latency preference. Mid-run switches only at safe boundaries, with
the scope of effect (current round / next round / future runs / project)
explained. Never display a control the selected model does not support.

## 17. Usage and cost

A transparent usage centre: input/output/cached/reasoning tokens where
reported, tool usage where measurable, estimated vs confirmed cost, by
project/thread/run/model/role, daily/weekly/monthly, local compute, remote
HPC. Distinguish reported / calculated / estimated / unknown. Versioned
pricing metadata with effective dates. Budgets per run/project/month/
provider with soft warnings and hard stops; estimates before expensive
operations. Never represent tokens as CrossAudit-owned currency.

## 18. GitHub experience

Fully manageable in UI: connect/disconnect/switch account, organizations,
create working and audit repositories, link existing, edit names before
creation, clone/fetch/pull/push, branch, commit, diff, guided conflict
resolution, open on GitHub, sync status, auth-expiration detection, partial
setup recovery. Default branch main unless chosen otherwise. Working and
audit repositories have clearly distinct purposes. Never commit secrets;
before publishing run a secret scan, show changed files, tests, target; ask
for confirmation unless the user explicitly requested a push. Background Git
never freezes the UI.

## 19. SSH and HPC as Generator compute

A managed external calculator, not an SSH terminal. Connection profiles:
host, port, user, auth method, key, agent forwarding only when explicitly
authorized, jump host, known-host verification, remote working directory,
scheduler, environment/modules, container runtime, storage paths, transfer
preferences. Scheduler adapters: Slurm, PBS/Torque, LSF, SGE, custom command
templates. Generator workflow: determine usefulness → explain intended
computation → prepare inputs → job plan → approval if policy requires →
transfer → submit → record scheduler ID → monitor → stream logs → detect
outcome → retrieve declared outputs → validate hashes and provenance → feed
back into context → submit final result to audit. No unrestricted SSH
authority by default; policy-controlled actions (read, write within
authorized directories, submit, query, cancel owned jobs, retrieve, approved
commands); dangerous commands and out-of-scope access require explicit
approval. Compute UI: connection status, cluster, scheduler, partitions,
active/queued/completed/failed jobs, allocations, runtime, resource use; job
detail with purpose, related run, scheduler ID, script, artifacts, live
stdout/stderr, timeline, retry, cancel, retrieve, open remote directory.
Remote jobs survive local UI closure; on reopen reconnect, reconcile, resume
log offsets, retrieve outputs, never duplicate a submission.

## 20. MCP, skills, and tools

Integrations page: MCP servers, Skills, Local tools, Remote compute, Data
sources, Source control, Export targets. MCP: add stdio or HTTP/SSE servers,
OAuth where officially supported, environment variables, start/stop, health,
tool list, permission scope, per-project enablement, logs, test connection.
Skills: install, update, disable, remove, view instructions/source/
permissions, pin version, per-project enablement, detect incompatible or
suspicious skills. Tool permissions: always allow / ask each time / allow
for this run / deny / workspace-only / read-only / network restricted /
remote-compute restricted. The audit layer records material tool actions and
outputs without flooding the conversation. The Auditor evaluates
tool-derived evidence independently and never blindly trusts Generator
summaries.

## 21. Background operation

Continue safe work in the background: macOS background operation, menu-bar
status, native notifications, sleep/wake recovery, network-loss recovery,
update handoff, worker version compatibility, crash-safe persistence,
graceful shutdown, active-run warning on quit, "quit UI but continue
permitted background work" only when technically and transparently
supported. Notify meaningfully (result ready, decision required, auth
required, HPC job completed, budget threshold, failed safely) — never per
audit round.

## 22. Settings

Searchable architecture, never one long form: General (language, appearance,
startup, updates, notifications) · Providers (accounts, credentials, models,
fallbacks, validation) · Agent behavior (default roles, auto reasoning,
clarification policy, default rounds) · Audit (default constitution,
admission policy, evidence retention, independence policy) · Files (storage,
indexing, preview, temp files, large-file behavior) · GitHub (accounts,
default owner, repository defaults) · Compute (SSH profiles, scheduler
profiles, transfer policy) · Integrations (MCP, skills, tools) · Usage
(budgets, estimates, export) · Security and privacy (keychain, retention,
provider routing, redaction, logs) · Diagnostics (Doctor, versions, logs,
support bundle, per-subsystem reset) · Advanced (developer settings,
experiments, local endpoints, debug logging). Each page: concise heading,
one-sentence purpose, grouped controls, immediate validation, section reset,
no unnecessary cards.

## 23. Global search and commands

One global search/command interface across projects, threads, messages,
answers, files, artifact content, runs, findings, constitution rules,
branches, HPC jobs. Commands: new project/thread, open file, switch project,
run Doctor, open usage, connect provider/GitHub, add MCP server, open
settings, toggle inspector, stop current run. Complete, discoverable
keyboard navigation.

## 24. Localization

Global English and Simplified Chinese. No mixed-language screens except
proper nouns and provider/model identifiers; localized dates, numbers,
units, pluralization; long Chinese labels tested; no English-length layout
assumptions; live language change; user content never auto-translated; rule
IDs and error codes stable across languages. All new visible strings go
through the localization system.

## 25. Visual design system

Dark mode only unless direction changes. Apple-like hierarchy and material
discipline, native desktop precision, task focus, approachable artifact
presentation, CrossAudit's own scientific and evidentiary identity; no pixel
copying. Content surfaces mostly opaque; glass reserved for navigation,
floating controls, contextual overlays, transient layers; no blur on every
card, no neon gradients or glow, no dashboard grids, no excessive pills, no
border around every group; whitespace for grouping; typography before boxes;
risk colours only for real risk. Material layers 0-4 (canvas → content →
navigation → floating/sheets/decisions → modal focus). System-oriented sans
stack + dedicated mono for code, hashes, logs, tokens, model identifiers;
readable Chinese; controlled type scale; no marketing typography in-app.
Motion explains hierarchy, causality, state: fast feedback ~120-180ms,
panels ~200-280ms, spatial ~300-450ms, restrained springs, no
animate-everything-on-scroll, respect Reduce Motion, no blocking animation.

## 26. Empty, loading, error, recovery states

Every major screen designs: empty, first-use, loading, partial data,
offline, auth expired, permission denied, provider unavailable, worker
restarting, migration, corrupt-recoverable, terminal failure, retry
exhausted. Skeletons resemble real content; no unexplained infinite
spinners; after a meaningful timeout show what CrossAudit waits for, whether
work progresses, last heartbeat, safe actions. Every error answers: what
happened, was work lost, what is CrossAudit doing now, what can the user do,
where are technical details.

## 27. Data, security, trust

Local-first by default. Users can understand what stays local and what is
sent to each provider, GitHub, HPC, logs, and the audit repository. OS
keychain for secrets; redaction before logging; no secrets in event streams,
crash reports, or Git; loopback-only local server; strong session tokens;
Origin/Host validation; CSP; path authorization; symlink protections;
archive safety; atomic writes; file permissions; signed or
integrity-checked updates; dependency and secret scanning; support-bundle
redaction. Destructive actions explicit, scoped, recoverable where possible.

## 28. Enterprise and research extensions

Architecturally possible without compromising the local-first core: shared
constitutions, RBAC, SSO, team projects, signed policy distribution,
approval workflows, retention, org usage reporting, central routing, private
endpoints, air-gapped operation, compliance evidence export, reproducible
research bundles, dataset provenance, experiment lineage, e-signatures,
shared HPC profiles without shared credentials, policy-controlled tools.
Never exposed to individual users unless enabled.

## 29. Companion website and distribution

The website explains the core idea immediately, shows the real application,
demonstrates Generator → Audit → Revision → Verified Result, links GitHub,
downloads the latest signed release, shows release notes, system and
provider requirements honestly, install/update instructions, security
documentation; no mock functionality or false claims. Release artifacts:
DMG, app bundle, checksums, versioned notes, installation verification,
uninstall instructions, update strategy, compatibility matrix. main
represents the latest stable product. Website deploys only after build,
tests, visual verification, link/download validation, and version agreement.

## 30. Target technical architecture

Map the current system first; never rewrite for fashion. Boundaries: Desktop
shell (window lifecycle, menus, pickers, notifications, keychain,
background, updates) · UI application (view state, navigation,
accessibility, localization, preview, real-time rendering) · Application API
(typed commands, typed queries, structured errors, capability metadata,
authn/authz) · Runtime kernel (durable state machines, project workers,
event journal, leases, idempotency, crash recovery, scheduling,
cancellation) · Agent orchestration (intent, Generator, Auditor, Controller,
clarification policy, context, tool permissions) · Provider adapters
(capability normalization, auth, parameter translation, streaming, error
classification, usage) · Audit engine (constitution, checks, findings,
revision loop, decisions, receipts, admission) · Artifact system (content
addressing, versioning, preview, conversion, export, provenance) ·
Integration layer (Git/GitHub, MCP, skills, SSH/HPC, local tools) ·
Persistence (migrations, durable state, event journal, search index, usage
ledger, recovery checkpoints). No duplicated business logic between CLI and
UI, frontend and backend, workers, provider code, audit display and engine,
wizard and settings. CLI and UI invoke the same application services.

## 31. Reliability invariants

A Generator cannot approve its own result · required independence cannot be
silently disabled · an invalid or missing audit cannot produce PASS · a
failed provider call cannot be misrepresented as a content finding · a
receipt cannot be admitted twice · a blocked run cannot be admitted as
passed · a model cannot bypass human-required state · exhausted retries end
in an explicit state · restart cannot duplicate a run, job, repository, or
admission · a stale worker cannot silently own a project forever · one
project failure cannot corrupt another · user files cannot be deleted
because a run failed · uncommitted changes cannot be silently discarded ·
internal audit artifacts cannot be presented as deliverables · the UI cannot
claim real-time state unless backed by durable runtime state · the UI cannot
claim verified when only local structural validation occurred · estimates
cannot be presented as confirmed charges · unsupported controls are never
sent to a provider. Write invariant tests for these.

## 32. Performance targets

Measure on representative hardware before optimizing: fast shell
visibility; project list usable before deep indexing; composer never blocks
on background work; prompt real-time events; virtualized large logs; no
whole-file memory loads; cancellable throttled indexing; responsive
thousand-file projects; HPC log reconnect without full replay; progressive
search; negligible idle CPU; bounded background concurrency.

## 33. Testing standard

Unit (transitions, capability normalization, audit rules, cost, file
safety, localization, GitHub validation, scheduler parsing) ·
property-based (state-machine invariants, receipt integrity, event
ordering, retry idempotency, path authorization) · integration (adapters,
Git, GitHub mocked and live, keychain, conversions, MCP, SSH test server,
scheduler adapters, migrations) · end-to-end (first launch through delete
project, including partial repo failure, dirty workspace, restart,
background continuation) · real provider contract tests (opt-in, cheap,
parameter and streaming and error verification, never printing credentials)
· fault injection (worker kill between transitions, app kill during repo
creation, network loss, corrupt state file, provider timeout, SSH
disconnect, scheduler delay, disk full, permission denied, expired
credential, duplicate and out-of-order events, stale-worker upgrade) · UI
(all target sizes, 200% zoom, both languages, long content, thousands of
events, empty and ten-project states, Reduce Motion, Reduced Transparency,
keyboard-only, screen reader) · visual regression (all major screens) ·
packaging (clean install, upgrade, Gatekeeper, keychain persistence,
uninstall/reinstall, worker migration, DMG contents, checksum, version
consistency).

## 34. Release gate

A release is complete only when: required tests pass; no known critical/high
security issue; no data-loss bug; no reproducible stuck state; clean-machine
onboarding works; GitHub two-repository creation verified; key paste and
validation work; PDF and DOCX generation and preview work; background
isolation verified; human intervention appears after exhaustion; restart
recovery works; EN and ZH reviewed; accessibility passes; screenshots
reviewed at all sizes; website, app, package versions and release notes
agree; repository clean; secret scan passes; artifacts reproducible or
documented; final DMG installs and launches; a real user-flow report exists.

## 35. Implementation method

Per cycle: Inspect (read code, map behavior, find duplication, check
invariants and tests, inspect rendered UI, baseline screenshots) → Define
one vertical slice producing one complete user outcome → Simplify before
adding (redundant states, duplicate controls, shared logic, canonical data
model, stable error types, the state machine, what the user actually sees) →
Design (screen hierarchy, primary action, empty/loading/error/recovery,
desktop and narrow behavior, what stays hidden, no generic card grid) →
Implement (shared services, adapters, migrations, preserved data,
observability, localization, accessibility, no dead buttons) → Verify
(unit, integration, e2e, fault injection, rendered screenshots, keyboard,
both languages, restart recovery, real operation when safe) → Critique
visually (first focal point, obvious primary action, what can be removed,
unnecessary cards/borders, density, internal details vs outcomes, last line
visible, composer overlap, error comprehensibility, long Chinese) → Report
(outcome, simplifications, files, tests, screenshots, risks, real external
operations, pushes/deploys).

## 36. Priority roadmap

**P0 structurally reliable**: no stuck runs; explicit durable state machine;
crash recovery; worker version handling; provider error normalization;
unsupported-parameter prevention; human decision state; safe Git workspace
handling; file generation correctness; PDF/DOCX preview; complete first-run
diagnostics; UI scrolling and layout correctness.
**P1 coherent essential experience**: canonical IA; simplified Project Home,
New Project, Settings; agentic workspace; minimal composer; automatic intent
inference; clean artifact output; collapsed audit details; global EN/ZH;
real-time multi-project status.
**P2 core integrations**: GitHub UI; two-repository creation and recovery;
provider management; usage and cost; MCP; Skills; universal preview;
notifications; app updates.
**P3 professional and scientific**: SSH/HPC profiles; Slurm/PBS/LSF
adapters; remote job lifecycle; provenance; scientific previews;
reproducible bundles; templates; advanced constitution management.
**P4 enterprise**: shared policies; team projects; SSO; RBAC; retention;
central usage; air-gapped; compliance exports; managed integrations.
Never begin P3/P4 by weakening P0/P1.

## 37. Final product experience

A new user installs and opens the app; CrossAudit checks the machine
silently and explains only actionable problems; they connect GitHub and a
provider through guided UI; choose a folder, accept a recommended role
pairing, create the project; CrossAudit creates or connects both
repositories with every step visible. In a calm workspace they write
"Review this paper, identify methodological weaknesses, and return a
rigorous 1,500-word PDF report", drag in a PDF, press Send. CrossAudit
understands the task and output, asks nothing unnecessary; the Generator
works; the UI shows meaningful progress; the Auditor independently checks
rigor, evidence, coverage, format; revision rounds run automatically; the
user sees one final PDF artifact with preview, open, save, and audit
status; internal metadata stays in the Audit Inspector. Provider failures
are explained with the actual cause and a relevant fix. Exhausted rounds
pause safely into a concise decision screen. Scientific tasks may submit
approved HPC jobs that survive app restarts. At all times the user can
understand what CrossAudit is doing, why, what data goes where, what it may
cost, whether the result passed, what needs human action, and how to
recover. Independent audit must feel natural — never like bureaucracy.

## 38. First required response

Before changing code, return: (1) a concise current-state architecture map;
(2) the ten largest sources of redundancy or inconsistent state; (3) which
existing invariants already work and must be preserved; (4) a gap analysis
against this North Star; (5) a proposed target architecture; (6) the first
three vertical slices ordered by risk reduction; (7) for the first slice its
state machine, UI flow, data model changes, migration plan, test matrix,
acceptance criteria; (8) anything technically impossible, unsafe,
unsupported by official providers, or better implemented differently.

Do not claim a feature works until tested through the real user-facing
path. Do not use passing unit tests as sole evidence of readiness. Do not
optimize for feature count. Optimize for coherence, reliability,
recoverability, and user trust.
