"""`crossaudit build` — the closed loop (DESIGN.md §8, a3).

The user states a task once. The generator writes, the work is committed, the
auditor judges it, and if it was blocked the findings go back to the generator
for another round — until PASS, or until the round budget hands it to a human.

What the user sees is a narration. What the ledger receives is unchanged: every
round is a commit, every verdict a report and a receipt, every escalation a
decision waiting for a person. The box is opaque to interact with and glass on
the inside.

Two things this verb refuses to do, both deliberate:

* **It never lifts a rule to make progress.** A blocked round is returned to the
  generator, never to the rulebook. Loosening a rule is an amendment, which is a
  human's lane and takes effect only between cycles.
* **It stops at the round budget.** Three failed rounds mean the loop cannot
  resolve this itself, which is exactly what I5 is for: escalate rather than
  spin.
"""
from __future__ import annotations

import contextlib
import io
import os
import re

from .. import document_export, hpc, mcp
from .. import generator as gen_mod
from .. import skills as skills_mod
from ..config import Config, heterogeneity, load
from ..controller import StateStore
from ..dcl import describe as describe_checks
from ..errors import EXIT_ESCALATED, EXIT_OK, ConfigDenial, Denial, ProviderDenial
from ..gitio import git, is_repo
from ..providers import resilience as provider_resilience
from ..runtime import (
    PreparedRun,
    RunCommandService,
    RunEvent,
    RunState,
)
from ..usage import record_completion
from .main import ALLOW_CUSTOM_ENV, cmd_run

TASK_FILE = "TASK.md"
MAX_AGENT_JOBS_PER_BUILD = 20
MAX_MCP_CALLS_PER_BUILD = 40


def _generator_complete(cfg: Config, allow_custom: bool, on_event=None):
    """A `complete(system, prompt)` bound to the generator role.

    The generator role needs its own credential; falling back to the auditor's
    would put one key behind both ends of a loop whose whole premise is that the
    ends are separate.
    """
    primary = provider_resilience.generator_role(cfg)

    def complete(*, system: str, prompt: str):
        reply = provider_resilience.complete(
            cfg, "generator", primary, system=system, prompt=prompt,
            allow_custom=allow_custom, on_event=on_event)
        route = provider_resilience.route_from_reply(reply, primary)
        complete.last_route = route
        record_completion(root=cfg.root, state_dir=cfg.state_dir, role="generator",
                          phase="generation", vendor=route["vendor"],
                          provider=route["provider"], model=route["model"], reply=reply,
                          system=system, prompt=prompt, base_url=route.get("base_url"))
        return reply

    complete.last_route = None
    return complete


def _current_work(cfg: Config) -> dict[str, str]:
    """The work as it stands, read from the working tree inside the scope dirs."""
    out: dict[str, str] = {}
    for d in (cfg.scope_dirs or []):
        base = cfg.root / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if "TEMPLATE" in p.parts:
                continue
            if p.is_file() and not p.is_symlink():
                try:
                    out[p.relative_to(cfg.root).as_posix()] = p.read_text(
                        encoding="utf-8")
                except UnicodeDecodeError:
                    rendered = document_export.current_document_text(p)
                    if rendered is not None:
                        out[p.relative_to(cfg.root).as_posix()] = rendered
    return out


def _stage_generated(cfg: Config, written: list[str]) -> list[str]:
    """Stage exactly the files returned by the generator, and nothing else.

    A scope directory may contain a user's untracked work or the starter
    template. Staging the whole directory silently sweeps both into the model's
    commit and later audit. The apply boundary already returns the exact paths;
    use that boundary as the pathspec.
    """
    if not written:
        return []
    git("add", "--", *written, cwd=cfg.root)
    return git("diff", "--cached", "--name-only", cwd=cfg.root,
               check=False).splitlines()


def _last_report(cfg: Config) -> str:
    ledger = cfg.root / cfg.ledger_dir
    reports = sorted(ledger.glob("*/report.md"), key=lambda p: p.stat().st_mtime)
    return reports[-1].read_text(encoding="utf-8") if reports else ""


class _Args:
    """The argument shape `cmd_run` expects, when the loop calls it rather than a user."""

    json = False
    sha = None
    yes = True

    def __init__(self) -> None:
        # Sending a key to a non-builtin origin is opt-in — flag or environment
        # — and the loop may not be a quieter path than the verb. A hardcoded
        # True here waived, for every auditor call the build loop makes, the
        # very consent `crossaudit run` demands; the loop has no flags, so the
        # environment gate the generator already uses is the whole opt-in.
        self.allow_custom_endpoint = bool(os.environ.get(ALLOW_CUSTOM_ENV))


def run_loop(cfg, task: str, *, on_event=None, attachments: str = "",
             chat_id: str = "", continuation_cycle: str = "") -> int:
    """The build loop itself emits typed operational facts.

    Kept separate from cmd_build so the console can watch the same loop the CLI
    runs, rather than a reimplementation of it that could drift on the one thing
    that matters: when the loop stops.
    """
    current_round = 0
    operational_state = RunState.QUEUED

    def emit(kind: str, actor: str, text: str, detail: str = "", *,
             state: RunState | None = None) -> None:
        nonlocal operational_state
        operational_state = state or operational_state
        if on_event is not None:
            on_event(RunEvent(
                kind=kind, actor=actor, text=text, detail=detail,
                state=operational_state, round_no=current_round,
                round_limit=cfg.max_rounds))

    def generator_provider_event(actor: str, text: str, detail: str = "") -> None:
        emit("provider_recovery", actor, text, detail,
             state=RunState.GENERATING)

    if chat_id and not re.fullmatch(r"(?:history|[a-f0-9]{16})", chat_id):
        raise ConfigDenial("chat id is invalid")
    allow_custom = bool(os.environ.get(ALLOW_CUSTOM_ENV))
    complete = _generator_complete(cfg, allow_custom, generator_provider_event)
    constitution = (cfg.root / cfg.constitution).read_text(encoding="utf-8")
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    house = skills_mod.load(cfg.root)
    findings = ""
    deterministic_contract = describe_checks(cfg.checks)
    compute_hosts = hpc.MANAGER.agent_context(cfg)
    compute_results: list[dict] = []
    compute_counts: dict[str, int] = {}
    total_compute_jobs = 0
    mcp_servers = mcp.MANAGER.agent_context(cfg)
    tool_results: list[dict] = []
    tool_counts: dict[str, int] = {}
    total_tool_calls = 0
    build_cycle_id: str | None = continuation_cycle or None
    termination_reason = f"build round budget spent ({cfg.max_rounds})"
    last_round = 0

    for round_no in range(1, cfg.max_rounds + 1):
        current_round = round_no
        last_round = round_no
        emit("round_started", "loop", f"round {round_no} of {cfg.max_rounds}",
             state=RunState.GENERATING)
        emit("generation_started", "generator", "writing",
             state=RunState.GENERATING)
        current = _current_work(cfg)
        in_force = skills_mod.select(house, list(current) or cfg.scope_dirs)
        try:
            while True:
                outcome = gen_mod.generate(
                    task=task, constitution=constitution, current=current,
                    complete=complete, findings=findings,
                    allowed_dirs=cfg.scope_dirs,
                    skills=skills_mod.render(in_force),
                    deterministic_contract=deterministic_contract,
                    attachments=attachments, compute_hosts=compute_hosts,
                    compute_results=compute_results, mcp_servers=mcp_servers,
                    tool_results=tool_results)
                if isinstance(outcome, gen_mod.Work):
                    work = outcome
                    break
                if isinstance(outcome, gen_mod.ToolRequest):
                    total_tool_calls += 1
                    if total_tool_calls > MAX_MCP_CALLS_PER_BUILD:
                        raise ProviderDenial(
                            "the Generator exceeded the automatic MCP call limit")
                    server_id = str(outcome.request.get("server_id", ""))
                    tool_counts[server_id] = tool_counts.get(server_id, 0) + 1
                    tool_name = str(outcome.request.get("tool", "MCP tool"))
                    emit("capability_requested", "tool", "calling MCP tool",
                         tool_name[:200], state=RunState.WAITING_FOR_CAPABILITY)
                    try:
                        result = mcp.MANAGER.call_agent(
                            cfg, outcome.request, chat_id=chat_id,
                            ordinal=tool_counts[server_id],
                            notify=lambda status, detail: emit(
                                "capability_progress", "tool", status, detail,
                                state=RunState.WAITING_FOR_CAPABILITY))
                    except Denial as exc:
                        result = {"status": "refused", "message": exc.reason,
                                  "server_id": server_id, "tool": tool_name}
                        emit("capability_refused", "tool", "refused",
                             exc.reason[:300], state=RunState.WAITING_FOR_CAPABILITY)
                    tool_results.append(result)
                    current = _current_work(cfg)
                    emit("generation_resumed", "generator", "resuming with tool result",
                         state=RunState.GENERATING)
                    continue
                total_compute_jobs += 1
                if total_compute_jobs > MAX_AGENT_JOBS_PER_BUILD:
                    raise ProviderDenial(
                        "the Generator exceeded the automatic remote-compute call limit")
                host_id = str(outcome.request.get("host_id", ""))
                compute_counts[host_id] = compute_counts.get(host_id, 0) + 1
                emit("capability_requested", "compute",
                     "requesting remote calculation",
                     str(outcome.request.get("name", "Generator compute"))[:200],
                     state=RunState.WAITING_FOR_CAPABILITY)
                try:
                    result = hpc.MANAGER.run_agent(
                        cfg, outcome.request, chat_id=chat_id,
                        ordinal=compute_counts[host_id],
                        notify=lambda status, detail: emit(
                            "capability_progress", "compute", status, detail,
                            state=RunState.WAITING_FOR_CAPABILITY))
                except Denial as exc:
                    result = {"status": "refused", "message": exc.reason,
                              "host_id": host_id}
                    emit("capability_refused", "compute", "refused",
                         exc.reason[:300], state=RunState.WAITING_FOR_CAPABILITY)
                compute_results.append(result)
                current = _current_work(cfg)
                emit("generation_resumed", "generator",
                     "resuming with compute result", state=RunState.GENERATING)
        except ProviderDenial as exc:
            # An overreaching or malformed round is a refused round, not a
            # crashed loop: the generator is told what the guard refused and
            # gets its next attempt inside the same budget.
            emit("generation_refused", "generator", "refused", exc.reason,
                 state=RunState.GENERATING)
            findings = (f"[BLOCKER] Your last round was refused before it reached "
                        f"the auditor: {exc.reason}\nReturn only files inside "
                        f"{', '.join(cfg.scope_dirs)}/ and try again.")
            # Authentication, permission, endpoint and invalid-model HTTP
            # failures cannot improve by sending the same request for every
            # remaining round. Stop once, retain the provider's actionable
            # explanation, and expose a human decision in the UI. Retryable
            # transport/rate-limit failures and malformed model output may use
            # the remaining automatic revision budget.
            if (exc.detail.get("status") is not None and
                    not exc.detail.get("retryable", False)):
                termination_reason = (
                    f"generator provider failure in round {round_no}: "
                    f"{exc.reason[:400]}")
                break
            if round_no == cfg.max_rounds:
                break
            continue

        try:
            document_export.validate_export_work(cfg.root, work.files, task)
            written = gen_mod.apply(work, cfg.root)
            if document_export.parse_export_task(task) is not None:
                emit("document_rendering", "generator",
                     "rendering final document locally", state=RunState.GENERATING)
            written = document_export.render_export(cfg.root, written, task)
        except ProviderDenial as exc:
            emit("document_refused", "generator", "document export refused",
                 exc.reason, state=RunState.GENERATING)
            findings = ("[BLOCKER] The local document export boundary refused the "
                        f"last round: {exc.reason}\nReturn exactly one valid "
                        f"*{document_export.SOURCE_SUFFIX} Markdown source and try again.")
            if round_no == cfg.max_rounds:
                termination_reason = (
                    f"document export failed in round {round_no}: {exc.reason[:400]}")
                break
            continue
        emit("generation_completed", "generator", work.summary,
             ", ".join(written[:4]), state=RunState.GENERATING)
        if work.notes:
            emit("generation_note", "generator", "note", work.notes[:200],
                 state=RunState.GENERATING)

        # Dirtiness is judged over what will actually be committed. Asking about
        # the whole tree lets an untracked file elsewhere fake a change, and then
        # the commit has nothing staged and fails.
        staged = _stage_generated(cfg, written)
        if not staged:
            emit("revision_unchanged", "loop",
                 "the round reproduced the previous one; nothing new to audit",
                 state=RunState.GENERATING)
            termination_reason = (
                f"generator produced no new auditable revision in round {round_no}")
            break
        try:
            commit_args = ["commit", "-q", "-m",
                           f"{work.summary} (round {round_no})"]
            route = getattr(complete, "last_route", None)
            if isinstance(route, dict):
                commit_args += ["-m", ("CrossAudit-Generator: "
                                f"{route['vendor']}/{route['provider']}:{route['model']}; "
                                f"fallback={str(bool(route.get('fallback'))).lower()}")]
            if chat_id:
                # A commit trailer associates durable work/audit evidence with
                # its UI chat without putting conversation metadata in files.
                commit_args += ["-m", f"CrossAudit-Chat: {chat_id}"]
            git(*commit_args, cwd=cfg.root)
        except ConfigDenial as exc:
            # git refusing is a refused round, like any other: the loop reports it
            # and stops cleanly rather than tearing down a run the ledger already
            # has rounds for.
            emit("commit_refused", "loop", "the round could not be committed",
                 exc.reason[:200], state=RunState.GENERATING)
            termination_reason = (
                f"generator revision could not be committed in round {round_no}")
            break

        audit_sha = git("rev-parse", "HEAD", cwd=cfg.root)
        emit("audit_started", "auditor", "reviewing the commit",
             state=RunState.AUDITING)
        buffer = io.StringIO()
        run_args = _Args()
        run_args.continue_cycle = build_cycle_id
        run_args.on_step = lambda actor, text, detail="": emit(
            "provider_recovery", actor, text, detail, state=RunState.AUDITING)
        with contextlib.redirect_stdout(buffer):
            code = cmd_run(run_args)
        inner = buffer.getvalue()
        cycles = store.snapshot().get("cycles", {})
        matched = [(cid, c) for cid, c in cycles.items()
                   if c.get("active_sha") == audit_sha]
        if matched:
            build_cycle_id, latest = matched[0]
        else:
            latest = {}
        status = latest.get("status", "?")

        if code == EXIT_OK:
            emit("audit_passed", "auditor", "PASS", state=RunState.AUDITING)
            return EXIT_OK
        if status == "ESCALATED":
            emit("audit_escalated", "auditor", "ESCALATED",
                 "the loop cannot settle this itself", state=RunState.AUDITING)
            return EXIT_ESCALATED
        blocking = [ln.strip("- ").strip() for ln in inner.splitlines()
                    if ln.strip().startswith("- [")]
        emit("audit_blocked", "auditor", "BLOCKED",
             "; ".join(blocking[:2])[:300], state=RunState.AUDITING)
        findings = gen_mod.render_findings(_last_report(cfg))
        emit("revision_requested", "loop", "findings returned to the generator",
             state=RunState.REVISING)

    reason = termination_reason
    if build_cycle_id:
        store.escalate(build_cycle_id, reason, task=task)
        emit("audit_escalated", "auditor", "ESCALATED",
             f"cycle {build_cycle_id} is waiting for a human")
    else:
        # A provider can refuse every generator attempt before there is a work
        # commit for cmd_run to open. Anchor that stop to the current durable
        # task/routing commit so the UI exposes an actual human decision instead
        # of an ephemeral "needs input" banner with nothing to resolve.
        anchor = git("rev-parse", "HEAD", cwd=cfg.root)
        cycle = store.record_build_escalation(
            cfg.science_repo, anchor, reason, last_round, chat_id, task)
        emit("audit_escalated", "auditor", "ESCALATED",
             f"cycle {cycle['cycle_id']} is waiting for a human")
    emit("loop_stopped", "loop", reason)
    return EXIT_ESCALATED


def resolve_task(cfg, words: list[str]) -> str:
    """The task, from the command line or from the committed TASK.md."""
    task = " ".join(words).strip()
    task_path = cfg.root / TASK_FILE
    if not task:
        if not task_path.is_file():
            raise ConfigDenial('say what to build: crossaudit build "..."')
        return task_path.read_text(encoding="utf-8")
    # The task joins the ledger too: a reader asking "why does this exist"
    # should find the answer in the repository, not in someone's terminal.
    # Restating the same task is not a change, and git has nothing to commit.
    unchanged = (task_path.is_file() and
                 task_path.read_text(encoding="utf-8").strip() == task.strip())
    task_path.write_text(task + "\n", encoding="utf-8", newline="\n")
    if not unchanged:
        git("add", "--", TASK_FILE, cwd=cfg.root)
        git("commit", "-q", "-m", f"task: {task.splitlines()[0][:68]}", cwd=cfg.root)
    return task


def preflight(cfg) -> None:
    """What must hold before either caller starts a loop."""
    if not is_repo(cfg.root):
        raise ConfigDenial(f"{cfg.root} is not a git repository; the ledger is git")
    if not cfg.scope_dirs:
        raise ConfigDenial(
            "scope.dirs is not set: the generator must be told where it may write, "
            "or it could rewrite the rules it is judged by")
    het_ok, why = heterogeneity(cfg)
    if not het_ok:
        raise ConfigDenial(why)


def cmd_build(args) -> int:
    cfg = load()
    preflight(cfg)
    service = RunCommandService(cfg)

    def prepare() -> PreparedRun:
        return PreparedRun(task=resolve_task(cfg, args.words))

    def worker(prepared: PreparedRun, emit) -> int:
        constitution = (cfg.root / cfg.constitution).read_text(encoding="utf-8")
        house = skills_mod.load(cfg.root)
        print("\nCrossAudit — building under audit")
        print("=" * 60)
        print(f"  task     {prepared.task.splitlines()[0][:60]}")
        print(f"  rules    {cfg.constitution} "
              f"({constitution.count(chr(10) + '### ')} rules)")
        print(f"  writing  {', '.join(cfg.scope_dirs)}/")
        if house:
            print(f"  skills   {', '.join(s.name for s in house)}")
        print(f"  rounds   up to {cfg.max_rounds}, then it goes to you")

        def on_event(event: RunEvent) -> None:
            emit(event)
            if event.kind == "round_started":
                label = f"round {event.round_no} of {event.round_limit}"
                print(f"\n  ── {label} " + "─" * max(0, 44 - len(label)))
                return
            line = f"  {event.actor:10s} {event.text}"
            print(line if not event.detail
                  else f"{line}\n  {'':10s} {event.detail[:96]}")

        return run_loop(cfg, prepared.task, on_event=on_event)

    code = service.start(prepare, worker, background=False)
    assert isinstance(code, int)
    if code == EXIT_OK:
        print("\n  Done. The work passed audit and the ledger has the whole exchange.")
        print("  Read it:  crossaudit watch   ·   Watch live:  crossaudit console")
    else:
        print("\n  It is yours now: `crossaudit watch` to read the exchange, or say "
              "what should happen next.")
    return code
