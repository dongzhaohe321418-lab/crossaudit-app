# CrossAudit — Product Vision and Delivery Map
# 产品愿景与交付映射

> 定位一句话：**一个自带独立质量监督体系的 Codex** —— 用户只描述目标，系统自主
> 完成工作、验证、修订和交付；只有真正需要人类判断时才打断用户。
>
> In one line: **a Codex that carries its own independent quality-supervision
> system.** The user states a goal; the system works, verifies, revises and
> delivers on its own, and interrupts a human only when a human judgement is
> genuinely required.

**Status.** This document records the product vision (2026-08-12) and maps each
part of it onto the codebase: what already exists, what the `v5-redesign`
branch delivers, and what belongs to later phases. Where this file and
`DESIGN.md` disagree on protocol semantics, `DESIGN.md` wins; where they
disagree on product direction, this file wins.

The success criterion, stated once and reused below:

> 用户像使用 Codex 一样自然地完成工作，却能在需要时证明结果由谁生成、检查了
> 什么、为何通过，以及最终交付物是否与审计证据完全一致。
>
> The user works as naturally as they would with Codex — yet can prove, on
> demand, who generated the result, what was checked, why it passed, and that
> the delivered artifact is exactly what the audit evidence binds.

---

## 1. Six user-visible states · 六个用户可见状态

Users must never need the internal vocabulary (Generator, Auditor, Receipt,
Cycle, DCL). The conversation surface shows exactly six states:

| User state 用户状态 | Internal states it projects (runtime/runs.py) |
|---|---|
| 正在理解 Understanding | `DRAFT`, `QUEUED` |
| 正在工作 Working | `GENERATING`, `WAITING_FOR_PROVIDER`, `WAITING_FOR_CAPABILITY` |
| 正在检查 Checking | `AUDITING` |
| 正在修订 Revising | `REVISING` |
| 已完成 Done | `PASSED` |
| 需要你决定 Needs your decision | `WAITING_FOR_HUMAN` |

`CANCELLED` / `INTERRUPTED` / `FAILED` are not a seventh state; they surface as
an explicit banner, because a stopped task is an event to explain, not a mode
to dwell in. Provider retries, routing confidence, receipt ids, commit SHAs and
check ids live behind "audit details" — recorded always, shown on demand.

**Delivered on this branch:** the console UI renders these six states from the
typed run-journal events (never by parsing narration text — the projection rule
from `runtime/events.py` already forbids that), and the audit surface follows
"invisible by default, expandable in full" (`docs/design/UI_DESIGN_SPEC.md §3.1,
§3.2`).

## 2. Autonomy boundaries · 自主性边界

Three classes of decision, one principle:

> 不按"系统是否不确定"决定是否询问，而按"错误决定的后果是否重大且难以撤销"
> 决定。 Ask not when the system is unsure, but when a wrong decision would be
> consequential and hard to undo.

- **Decide automatically** (reversible, low-risk): focus, tone, structure,
  filenames, default formats, step decomposition, authorised skills, in-scope
  file reads, effort within budget, ordinary post-audit revision. Today:
  `autonomy.py` (format intent), `router.apply_safe_default` (reversible lanes
  proceed below the confidence floor), the revision loop itself.
- **Execute under standing policy** (external effect, pre-authorised at project
  level): approved MCP tools (`mcp.py` allowlists + per-task budgets), HPC
  within saved host policy (`hpc.py` hard ceilings), connected GitHub repos,
  fallback models within cost caps (`resilience.py`), retry on transient
  provider failure. The UI must show these live and allow cancel — never
  re-confirm each call.
- **Must ask a human**: constitution amendments, unresolvable audit disputes,
  deletions, new remote resources, widened MCP/HPC/GitHub scopes, budget
  overruns, materially divergent alternatives, overwriting user work, exhausted
  audit rounds. Today: the amendment/dispute/resolve lanes, escalation lock in
  `controller/state.py`, the deletion typed-confirmation flow.

The boundary classes exist in code already; what this branch changes is the
*presentation*: policy-covered activity is narrated in the six-state stream,
and only the must-ask class produces a decision screen.

## 3. The console · 控制台形态

One centre: **conversation and deliverables**. Everything else orbits it.
Layout, glass boundaries, component specs, motion and degradation rules are in
`docs/design/UI_DESIGN_SPEC.md`; the load-bearing choices:

- Left rail: projects, pins, recent chats, search. Centre: one chronological
  run. Right: context panel on demand (sheet under 720px, never squeezing the
  centre). Bottom: one composer (+ files, text, @role, model chip, send/stop).
  Command palette on ⌘K.
- Glass only on navigation, floating controls, menus, transient panels.
  Messages, code, audit evidence, forms stay opaque — protocol state may never
  be hidden by visual hierarchy (`DESIGN.md §2.1` still governs).
- The human-decision screen answers four questions: what the task wanted, what
  was tried, what is still blocked, what we suggest. Never a bare `ESCALATED`,
  provider errno, or rule id.
- Audit presentation: three ✓ lines and a round summary; constitution version,
  findings, diffs, model identities, commits and receipts one click deeper.

**Delivered on this branch:** the redesigned `console/page.py` implementing the
above against the unchanged `console/server.py` API. **Later:** command palette
actions beyond navigation; per-chat background queueing UI.

## 4. Files · 文件体验

Already true today and preserved: unlimited-by-CrossAudit uploads (streamed
chunks, honest about disk/context limits), deliverables gated on
`passed`/`consumed` ledger status, sandboxed previews, PDF/DOCX as complete
delivery formats rendered locally and semantically recovered before commit.
**This branch:** deliverable groups (multi-file results fold into one card),
final-artifact-first presentation. **Later:** local indexing and chunked
retrieval so large files never need to fit a context window; diff/version
history/restore for edited files.

## 5. Scientists · 科学家模式

Same interface, progressively disclosed depth — never a second product.
Compute cards already stream scheduler state, logs and outputs (`hpc.py`,
`console/page.py` compute view); the generator already uses enabled hosts as a
policy-bounded external calculator. **This branch:** plain-language surface
("正在进行远程计算") with the full node/queue/log detail behind disclosure.
**Later:** compute graphs, dataset/notebook previews, provenance views.

## 6. Architecture convergence · 架构收敛（第 9 节）

The deepest item in the vision is not a page — it is finishing the strangler
migration `docs/V5_KERNEL_ARCHITECTURE.md` already specifies: one Project
Actor, one event store as the sole source of run truth, one Command Service
shared by UI/CLI/background, private git worktrees per agent run, a durable
outbox with idempotency keys for every external effect, structured errors
end-to-end, typed projections for the front end, versioned workers.

Honest ledger of where that stands:

- **Already converged (shipped before this branch):** `runtime/runs.py` SQLite
  WAL journal with an explicit transition table; `RunCommandService` as the
  single command path; durable idempotent cancellation that outlives worker
  death; crash recovery as a command-side responsibility.
- **This branch:** removes a class of string/vocabulary drift (LANES, doc
  drift, typed six-state projection consumed by the UI), and repairs the
  integrity seams found in review (audit/verify blob-policy symmetry, plugin
  code bound into the DCL digest, amendment log honesty, egress gate parity).
- **Phase 1 (next):** private run worktrees; durable outbox for provider/
  GitHub/MCP/HPC effects; delete legacy compatibility paths; structured errors
  replacing the remaining string parsing.
- **Phase 2:** automatic task planning; project file indexing; multi-chat
  background queues; richer diff/preview/delivery bundles; notifications.
- **Phase 3:** HPC compute graphs; MCP capability marketplace; scientific data
  provenance; team collaboration and enterprise policy; remote runners.

## 7. Models and cost · 模型与成本

Three intents — Automatic / Fast / Deep — as shortcuts over the existing
role+model+effort machinery, never replacing exact provider control. Usage
stays local-first with labelled API-value estimates (`usage.py`); budget
warnings and fail-closed hard limits already exist and remain the authority.
When every route fails, the UI offers change-model / fix-credentials / wait /
stop — the raw HTTP taxonomy stays in diagnostics.
