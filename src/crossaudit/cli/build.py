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
from pathlib import Path

from .. import generator as gen_mod
from .. import hpc
from .. import mcp
from .. import skills as skills_mod
from ..config import Config, heterogeneity, load
from ..controller import StateStore
from ..dcl import describe as describe_checks
from ..errors import (EXIT_ESCALATED, EXIT_OK, ConfigDenial, Denial,
                      ProviderDenial)
from ..gitio import git, is_repo
from ..providers import get_provider
from ..providers.registry import NEEDS_KEY
from ..usage import record_completion
from .main import cmd_run
from .talk import _routing_path

TASK_FILE = "TASK.md"
MAX_AGENT_JOBS_PER_BUILD = 20
MAX_MCP_CALLS_PER_BUILD = 40


def _generator_complete(cfg: Config, allow_custom: bool):
    """A `complete(system, prompt)` bound to the generator role.

    The generator role needs its own credential; falling back to the auditor's
    would put one key behind both ends of a loop whose whole premise is that the
    ends are separate.
    """
    if (cfg.generator_vendor or "").lower() == "human":
        raise ConfigDenial(
            "this project selected a human generator: make and commit the change, "
            "then run `crossaudit run`")
    provider = (
        os.environ.get("CROSSAUDIT_GENERATOR_PROVIDER")
        or cfg.generator_provider
        or ("anthropic" if (cfg.generator_vendor or "").lower() == "anthropic"
            else "openai_compat")
    )
    model = os.environ.get("CROSSAUDIT_GENERATOR_MODEL") or cfg.generator_model or ""
    if not model:
        raise ConfigDenial(
            "the generator's model is not set: export CROSSAUDIT_GENERATOR_MODEL "
            "(and CROSSAUDIT_GENERATOR_PROVIDER if it is not the vendor default)")
    key_env = cfg.generator_key_env or "CROSSAUDIT_GENERATOR_KEY"
    if NEEDS_KEY.get(provider, True) and not os.environ.get(key_env, "").strip():
        raise ConfigDenial(
            f"the generator has no key in ${key_env}. The auditor's key is not "
            f"reused: one credential behind both ends would collapse the "
            f"separation the loop depends on")
    base_url = (os.environ.get("CROSSAUDIT_GENERATOR_BASE_URL")
                or cfg.generator_base_url or None)
    fn = get_provider(provider)

    def complete(*, system: str, prompt: str):
        reply = fn(model=model, system=system, prompt=prompt, key_env=key_env,
                   base_url=base_url, allow_custom=allow_custom,
                   reasoning_effort=cfg.generator_reasoning_effort)
        record_completion(root=cfg.root, state_dir=cfg.state_dir, role="generator",
                          phase="generation", vendor=cfg.generator_vendor or "unknown",
                          provider=provider, model=model, reply=reply, system=system,
                          prompt=prompt, base_url=base_url)
        return reply

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
                    continue
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
    allow_custom_endpoint = True


def run_loop(cfg, task: str, *, on_step=None, attachments: str = "",
             chat_id: str = "", continuation_cycle: str = "") -> int:
    """The build loop itself. `on_step(actor, text, detail)` narrates it.

    Kept separate from cmd_build so the console can watch the same loop the CLI
    runs, rather than a reimplementation of it that could drift on the one thing
    that matters: when the loop stops.
    """
    def report(actor: str, text: str, detail: str = "") -> None:
        if on_step is not None:
            on_step(actor, text, detail)

    if chat_id and not re.fullmatch(r"(?:history|[a-f0-9]{16})", chat_id):
        raise ConfigDenial("chat id is invalid")
    allow_custom = bool(os.environ.get("CROSSAUDIT_ALLOW_CUSTOM_ENDPOINT"))
    complete = _generator_complete(cfg, allow_custom)
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
        last_round = round_no
        report("loop", f"round {round_no} of {cfg.max_rounds}")
        report("generator", "writing")
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
                    report("tool", "calling MCP tool", tool_name[:200])
                    try:
                        result = mcp.MANAGER.call_agent(
                            cfg, outcome.request, chat_id=chat_id,
                            ordinal=tool_counts[server_id],
                            notify=lambda state, detail: report("tool", state, detail))
                    except Denial as exc:
                        result = {"status": "refused", "message": exc.reason,
                                  "server_id": server_id, "tool": tool_name}
                        report("tool", "refused", exc.reason[:300])
                    tool_results.append(result)
                    current = _current_work(cfg)
                    continue
                total_compute_jobs += 1
                if total_compute_jobs > MAX_AGENT_JOBS_PER_BUILD:
                    raise ProviderDenial(
                        "the Generator exceeded the automatic remote-compute call limit")
                host_id = str(outcome.request.get("host_id", ""))
                compute_counts[host_id] = compute_counts.get(host_id, 0) + 1
                report("compute", "requesting remote calculation",
                       str(outcome.request.get("name", "Generator compute"))[:200])
                try:
                    result = hpc.MANAGER.run_agent(
                        cfg, outcome.request, chat_id=chat_id,
                        ordinal=compute_counts[host_id],
                        notify=lambda state, detail: report(
                            "compute", state, detail))
                except Denial as exc:
                    result = {"status": "refused", "message": exc.reason,
                              "host_id": host_id}
                    report("compute", "refused", exc.reason[:300])
                compute_results.append(result)
                current = _current_work(cfg)
        except ProviderDenial as exc:
            # An overreaching or malformed round is a refused round, not a
            # crashed loop: the generator is told what the guard refused and
            # gets its next attempt inside the same budget.
            report("generator", "refused", exc.reason)
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

        written = gen_mod.apply(work, cfg.root)
        report("generator", work.summary, ", ".join(written[:4]))
        if work.notes:
            report("generator", "note", work.notes[:200])

        # Dirtiness is judged over what will actually be committed. Asking about
        # the whole tree lets an untracked file elsewhere fake a change, and then
        # the commit has nothing staged and fails.
        staged = _stage_generated(cfg, written)
        if not staged:
            report("loop", "the round reproduced the previous one; nothing new to "
                           "audit")
            termination_reason = (
                f"generator produced no new auditable revision in round {round_no}")
            break
        try:
            commit_args = ["commit", "-q", "-m",
                           f"{work.summary} (round {round_no})"]
            if chat_id:
                # A commit trailer associates durable work/audit evidence with
                # its UI chat without putting conversation metadata in files.
                commit_args += ["-m", f"CrossAudit-Chat: {chat_id}"]
            git(*commit_args, cwd=cfg.root)
        except ConfigDenial as exc:
            # git refusing is a refused round, like any other: the loop reports it
            # and stops cleanly rather than tearing down a run the ledger already
            # has rounds for.
            report("loop", "the round could not be committed", exc.reason[:200])
            termination_reason = (
                f"generator revision could not be committed in round {round_no}")
            break

        audit_sha = git("rev-parse", "HEAD", cwd=cfg.root)
        report("auditor", "reviewing the commit")
        buffer = io.StringIO()
        run_args = _Args()
        run_args.continue_cycle = build_cycle_id
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
            report("auditor", "PASS")
            return EXIT_OK
        if status == "ESCALATED":
            report("auditor", "ESCALATED", "the loop cannot settle this itself")
            return EXIT_ESCALATED
        blocking = [ln.strip("- ").strip() for ln in inner.splitlines()
                    if ln.strip().startswith("- [")]
        report("auditor", "BLOCKED", "; ".join(blocking[:2])[:300])
        findings = gen_mod.render_findings(_last_report(cfg))
        report("loop", "findings returned to the generator")

    reason = termination_reason
    if build_cycle_id:
        store.escalate(build_cycle_id, reason)
        report("auditor", "ESCALATED", f"cycle {build_cycle_id} is waiting for a human")
    else:
        # A provider can refuse every generator attempt before there is a work
        # commit for cmd_run to open. Anchor that stop to the current durable
        # task/routing commit so the UI exposes an actual human decision instead
        # of an ephemeral "needs input" banner with nothing to resolve.
        anchor = git("rev-parse", "HEAD", cwd=cfg.root)
        cycle = store.record_build_escalation(
            cfg.science_repo, anchor, reason, last_round, chat_id)
        report("auditor", "ESCALATED",
               f"cycle {cycle['cycle_id']} is waiting for a human")
    report("loop", reason)
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
    task = resolve_task(cfg, args.words)
    constitution = (cfg.root / cfg.constitution).read_text(encoding="utf-8")
    house = skills_mod.load(cfg.root)

    print("\nCrossAudit — building under audit")
    print("=" * 60)
    print(f"  task     {task.splitlines()[0][:60]}")
    print(f"  rules    {cfg.constitution} ({constitution.count(chr(10) + '### ')} rules)")
    print(f"  writing  {', '.join(cfg.scope_dirs)}/")
    if house:
        print(f"  skills   {', '.join(s.name for s in house)}")
    print(f"  rounds   up to {cfg.max_rounds}, then it goes to you")

    def on_step(actor: str, text: str, detail: str) -> None:
        if actor == "loop" and text.startswith("round "):
            print(f"\n  ── {text} " + "─" * max(0, 44 - len(text)))
            return
        line = f"  {actor:10s} {text}"
        print(line if not detail else f"{line}\n  {'':10s} {detail[:96]}")

    code = run_loop(cfg, task, on_step=on_step)
    if code == EXIT_OK:
        print("\n  Done. The work passed audit and the ledger has the whole exchange.")
        print("  Read it:  crossaudit watch   ·   Watch live:  crossaudit console")
    else:
        print("\n  It is yours now: `crossaudit watch` to read the exchange, or say "
              "what should happen next.")
    return code
