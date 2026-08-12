"""Adversarial run-liveness probes, migrated into the suite as contracts.

Each test here began as a refuter's reproduction of a real hole in the
run-liveness hardening claim. They are kept as formal assertions of the
repaired behavior:

* the cycle ledger's recorded verdicts outrank every supervisor — a watchdog
  or reconciler can never rewrite a PASS into an escalation;
* an auditor-side provider outage parks the run instead of being synthesized
  into a content-flavored verdict and report;
* the lease, not the pid, is the recovery authority (pid reuse cannot mask a
  dead owner forever);
* schema-v1 rows migrate into supervision instead of a silent limbo;
* torn needs-a-human writes heal from either side, at the source first and by
  a bounded reconciliation scan second;
* the parked state has a real command surface, and the CLI status verb shows
  the run journal's truth.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from dataclasses import replace

import pytest

from crossaudit.console import daemon
from crossaudit.controller import StateStore
from crossaudit.errors import (EXIT_ESCALATED, EXIT_PROVIDER, IntegrityDenial,
                               ProviderDenial)
from crossaudit.runtime import (
    LEASE_SECONDS,
    PreparedRun,
    RunCommandService,
    RunEvent,
    RunJournal,
    RunState,
    journal_path,
)
from crossaudit.runtime.runs import STALL_AFTER_SECONDS

#: A pid that can never be alive on macOS or Linux (both cap well below it).
DEAD_PID = 999999
#: pid 1 (launchd/init) is alive forever and is not this process: the exact
#: shape of a recycled pid masking a dead worker.
RECYCLED_PID = 1

V1_SCHEMA = """
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY, task TEXT NOT NULL, chat_id TEXT NOT NULL,
    continuation_cycle TEXT NOT NULL, state TEXT NOT NULL,
    outcome TEXT NOT NULL, error TEXT NOT NULL, owner_pid INTEGER NOT NULL,
    started REAL NOT NULL, updated REAL NOT NULL, finished REAL
);
CREATE TABLE run_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(run_id), t REAL NOT NULL,
    kind TEXT NOT NULL, actor TEXT NOT NULL, text TEXT NOT NULL,
    detail TEXT NOT NULL, state TEXT NOT NULL
);
"""


def event(actor: str, text: str, state: RunState, *, detail: str = "",
          kind: str = "activity", waiting_reason: dict | None = None) -> RunEvent:
    return RunEvent(actor=actor, text=text, state=state, detail=detail,
                    kind=kind, waiting_reason=waiting_reason)


def age_lease(journal: RunJournal, run_id: str, expires_at: float) -> None:
    with sqlite3.connect(journal.path) as db:
        db.execute("UPDATE runs SET lease_expires_at=? WHERE run_id=?",
                   (expires_at, run_id))


def park_via_service(cfg, task: str) -> RunJournal:
    """The genuine _drive path: a wait-category denial escapes the worker."""
    def worker(_prepared, emit):
        emit(event("generator", "writing", RunState.GENERATING))
        emit(event("auditor", "reviewing", RunState.AUDITING,
                   kind="audit_started"))
        raise ProviderDenial("all configured auditor provider routes failed",
                             category="routes_exhausted", retryable=False,
                             status=503)

    service = RunCommandService(cfg)
    with pytest.raises(ProviderDenial):
        service.start(lambda: PreparedRun(task=task, chat_id="history"),
                      worker, background=False)
    return service.journal


def park_budget_via_service(cfg, task: str) -> RunJournal:
    """The genuine _drive park path for a usage-guardrail (budget) pause.

    A budget denial parks a run exactly like any provider wait (it is in
    PROVIDER_WAIT_CATEGORIES), but its remedy is billing, not a connection
    review — so the cycle side must record kind 'budget', not 'provider'.
    """
    def worker(_prepared, emit):
        emit(event("generator", "writing", RunState.GENERATING))
        raise ProviderDenial(
            "Local usage guardrail paused provider calls. Daily cost limit "
            "reached. Open Project controls to raise or clear the limit, "
            "then retry.",
            category="budget", retryable=False, budget={"state": "blocked"})

    service = RunCommandService(cfg)
    with pytest.raises(ProviderDenial):
        service.start(lambda: PreparedRun(task=task, chat_id="history"),
                      worker, background=False)
    return service.journal


# ------------------------------------------------- verdicts outrank watchdogs
def test_record_build_escalation_refuses_to_overwrite_a_recorded_pass(tmp_path):
    store = StateStore(tmp_path / "state.json")
    cycle = store.open_or_advance("lab/science", "a" * 40, None)
    store.record_verdict(cycle["cycle_id"], "a" * 40, "PASS", "f" * 64, 3)
    with pytest.raises(IntegrityDenial, match="cannot be overwritten"):
        store.record_build_escalation("lab/science", "a" * 40,
                                      "provider failure after the fact", 1)
    assert store.cycle(cycle["cycle_id"])["status"] == "PASSED"


def test_escalate_refuses_passed_and_consumed_cycles(tmp_path):
    store = StateStore(tmp_path / "state.json")
    cycle = store.open_or_advance("lab/science", "b" * 40, None)
    store.record_verdict(cycle["cycle_id"], "b" * 40, "PASS", "f" * 64, 3)
    with pytest.raises(IntegrityDenial, match="cannot be escalated"):
        store.escalate(cycle["cycle_id"], "watchdog says otherwise")
    store.admit(cycle["cycle_id"], "b" * 40, "f" * 64)
    with pytest.raises(IntegrityDenial, match="cannot be escalated"):
        store.escalate(cycle["cycle_id"], "watchdog says otherwise")


def test_reconcile_direction_b_never_flips_a_passed_cycle(science, cfg):
    """A stale human-wait run beside HEAD's PASSED cycle records nothing."""
    from crossaudit.gitio import git

    head = git("rev-parse", "HEAD", cwd=science)
    journal = RunJournal(journal_path(cfg))
    run_id = journal.start("refused long ago", chat_id="history")
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))
    journal.finish(run_id, "refused", "the auditor endpoint rejected the key")

    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    cycle = store.open_or_advance(cfg.science_repo, head, None)
    store.record_verdict(cycle["cycle_id"], head, "PASS", "f" * 64, 3)

    result = daemon.reconcile_human_wait(cfg, journal)
    assert result == {"run_completed": None, "cycle_recorded": None}
    assert store.cycle(cycle["cycle_id"])["status"] == "PASSED"
    # Idempotent: repeating the sweep still refuses to invent an escalation.
    again = daemon.reconcile_human_wait(cfg, journal)
    assert again == {"run_completed": None, "cycle_recorded": None}


# ----------------------------------------------- auditor-side provider outage
CLEAN_INCREMENT = {
    "experiments/demo/metadata.yml": (
        b"code_version: a1b2c3d\ninputs:\n  - scripts/run_demo.py@a1b2c3d\n"),
    "experiments/demo/results.json": json.dumps({
        "quantities": [
            {"name": "binding_energy", "value": -3.65, "unit": "kcal/mol",
             "source": "scripts/run_demo.py@a1b2c3d"},
            {"name": "distance", "value": 2.73, "unit": "angstrom",
             "source": "scripts/run_demo.py@a1b2c3d"},
        ],
        "convergence": {"converged": True, "achieved": 7.4e-07,
                        "threshold": 1e-06}}).encode(),
    "experiments/demo/SUMMARY.md": b"# Demo\nA converged binding energy.\n",
}


@pytest.mark.parametrize("category", ["routes_exhausted", "circuit_open"])
def test_run_audit_reraises_wait_category_denials(science, cfg, monkeypatch,
                                                  category):
    """A provider circuit break is an outage, not an audit opinion: when the
    missing model reply is the only thing that could decide the round, the
    denial is re-raised instead of being synthesized into a verdict."""
    from crossaudit.auditor.run import run_audit
    from crossaudit.providers import resilience

    def exhausted(*_a, **_k):
        raise ProviderDenial("all configured auditor provider routes failed",
                             category=category, retryable=False, status=503)

    monkeypatch.setattr(resilience, "complete", exhausted)
    constitution = (science / "AUDIT_RULES.md").read_text()
    with pytest.raises(ProviderDenial) as caught:
        run_audit(cfg=cfg, sha="c" * 40, round_=1, files=dict(CLEAN_INCREMENT),
                  notes=[], constitution=constitution,
                  constitution_commit="d" * 40)
    # The direct `crossaudit audit` verb maps this to EXIT_PROVIDER via the
    # CLI's Denial handler.
    assert caught.value.exit_code == EXIT_PROVIDER


def test_run_audit_keeps_a_deterministic_block_through_an_outage(
        science, cfg, monkeypatch):
    """When the deterministic tier already hard-blocked the round, the verdict
    is code's own and the outage decides nothing: the round keeps its real
    content findings instead of stalling the loop."""
    from crossaudit.auditor.run import run_audit
    from crossaudit.providers import resilience

    def exhausted(*_a, **_k):
        raise ProviderDenial("all configured auditor provider routes failed",
                             category="routes_exhausted", retryable=False,
                             status=503)

    monkeypatch.setattr(resilience, "complete", exhausted)
    constitution = (science / "AUDIT_RULES.md").read_text()
    outcome = run_audit(
        cfg=cfg, sha="c" * 40, round_=1,
        files={"experiments/demo/SUMMARY.md": b"missing everything\n"},
        notes=[], constitution=constitution, constitution_commit="d" * 40)
    assert outcome.verdict == "BLOCKED"
    assert outcome.dcl["total_hard_failures"] > 0
    assert outcome.integrity == "PROVIDER_FAILURE"


def test_run_audit_still_synthesizes_for_non_wait_provider_failures(
        science, cfg, monkeypatch):
    from crossaudit.auditor.run import run_audit
    from crossaudit.providers import resilience

    def flaky(*_a, **_k):
        raise ProviderDenial("provider returned HTTP 500",
                             category="transport", retryable=True, status=500)

    monkeypatch.setattr(resilience, "complete", flaky)
    constitution = (science / "AUDIT_RULES.md").read_text()
    outcome = run_audit(cfg=cfg, sha="c" * 40, round_=1, files={}, notes=[],
                        constitution=constitution,
                        constitution_commit="d" * 40)
    assert outcome.integrity == "PROVIDER_FAILURE"
    assert outcome.verdict != "PASS"


@pytest.mark.parametrize("category,expected_kind", [
    ("routes_exhausted", "provider"),
    ("circuit_open", "provider"),
    # A budget (usage-guardrail) pause parks through the SAME build.run_loop
    # tail, but its cycle kind must be 'budget', not the blanket 'provider' —
    # the build.py write point derives it from the park category, so run and
    # cycle name one stop one way.
    ("budget", "budget"),
])
def test_auditor_route_exhaustion_parks_the_real_build_loop(
        science, cfg, monkeypatch, category, expected_kind):
    """The full run_loop stack: generator succeeds, every auditor route is
    down. The run must park with a typed waiting reason, the cycle must carry
    an auditor-provider-failure decision object written before the park, and
    no synthesized report may present the outage as a content problem."""
    from crossaudit import generator as gen_mod
    from crossaudit.cli import build as build_mod
    from crossaudit.console import overview
    from crossaudit.providers import resilience

    scoped = replace(cfg, scope_dirs=["experiments"])
    work = gen_mod.Work(summary="demo increment", files={
        "experiments/demo/metadata.yml": (
            "code_version: a1b2c3d\ninputs:\n  - scripts/run_demo.py@a1b2c3d\n"),
        "experiments/demo/results.json": json.dumps({
            "quantities": [
                {"name": "binding_energy", "value": -3.65, "unit": "kcal/mol",
                 "source": "scripts/run_demo.py@a1b2c3d"},
                {"name": "distance", "value": 2.73, "unit": "angstrom",
                 "source": "scripts/run_demo.py@a1b2c3d"},
            ],
            "convergence": {"converged": True, "achieved": 7.4e-07,
                            "threshold": 1e-06}}, indent=1),
        "experiments/demo/SUMMARY.md": "# Demo\nA converged binding energy.\n",
    })
    monkeypatch.setattr(build_mod, "_generator_complete",
                        lambda *_a, **_k: object())
    monkeypatch.setattr(build_mod.gen_mod, "generate", lambda **_k: work)

    def exhausted(*_a, **_k):
        reason = ("Local usage guardrail paused provider calls. Daily cost "
                  "limit reached. Open Project controls to raise or clear the "
                  "limit, then retry." if category == "budget"
                  else "all configured auditor provider routes failed. "
                       "anthropic:claude — provider returned HTTP 503")
        raise ProviderDenial(reason, category=category, retryable=False,
                             status=503)

    monkeypatch.setattr(resilience, "complete", exhausted)
    monkeypatch.chdir(science)

    service = RunCommandService(scoped)
    code = service.start(
        lambda: PreparedRun(task="produce the experiment"),
        lambda prepared, emit: build_mod.run_loop(
            scoped, prepared.task, on_event=emit),
        background=False)

    assert code == EXIT_ESCALATED
    row = service.journal.latest()
    assert row["state"] == "PROVIDER_UNAVAILABLE"
    assert row["outcome"] == "provider_unavailable"
    # Run side (slice one) and cycle side (slice three) name one park one way.
    assert row["waiting_reason"]["kind"] == expected_kind
    assert row["waiting_reason"]["category"] == category

    # The cycle decision object was written by the loop tail (cycle first,
    # park second) and names the auditor as the failing role.
    store = StateStore(scoped.root / scoped.state_dir / "state.json")
    escalated = [c for c in store.snapshot()["cycles"].values()
                 if c["status"] == "ESCALATED"]
    assert escalated
    assert "auditor provider failure" in escalated[-1]["escalation_reason"]
    assert escalated[-1]["escalation_kind"] == expected_kind

    # No synthesized report: writing one with "invalid Auditor reply"
    # findings was the misrepresentation this test exists to forbid.
    assert not sorted((scoped.root / "cycles").glob("*/report.md"))

    rows = overview.escalations(scoped)
    assert rows and rows[-1]["kind"] == expected_kind
    assert rows[-1]["issues"] == []


# ------------------------------------------- identity > pid (pid reuse)
def test_recycled_pid_cannot_mask_a_dead_owner(cfg):
    """An unverifiable owner past its lease is reclaimed; pid 1 being
    "alive" proves nothing about the worker (no identity token exists for a
    foreign-pid row, so it can never be verified as this run's worker)."""
    journal = RunJournal(journal_path(cfg))
    run_id = journal.start("owner pid was recycled", owner_pid=RECYCLED_PID)
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))
    age_lease(journal, run_id, 1)          # the lease, its only claim, expired

    swept = daemon.watchdog_sweep(cfg)
    assert swept["recovered"] == [run_id]
    assert journal.state(run_id) == RunState.INTERRUPTED
    row = journal.latest()
    assert row["lease_expires_at"] is None
    # The narration states only what is known: unverified, not "ended".
    assert "could not be verified" in row["error"]
    assert "process ended" not in row["error"]
    # The slot is free again; no permanent limbo.
    assert journal.start("next task")


def test_identity_mismatch_reclaims_immediately_with_honest_narration(cfg):
    """A recorded token that no longer matches the live pid proves the pid
    was recycled: reclaim happens on the next sweep — no time gamble — and
    the narration says what is known instead of inventing a process death."""
    journal = RunJournal(journal_path(cfg))
    run_id = journal.start("worker died; pid recycled")     # self token
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))
    with sqlite3.connect(journal.path) as db:               # the recycle
        db.execute("UPDATE runs SET owner_pid=? WHERE run_id=?",
                   (RECYCLED_PID, run_id))

    swept = daemon.watchdog_sweep(cfg)
    assert swept["recovered"] == [run_id]
    row = journal.latest()
    assert row["state"] == "INTERRUPTED"
    assert "recycled" in row["error"]
    assert "no heartbeat" in row["error"]
    assert "process ended" not in row["error"]              # never fabricated


def test_a_verified_alive_owner_is_never_reclaimed(cfg):
    """The principle itself: however silent (lid close, SIGSTOP, clock
    jump), an owner whose identity token still matches is narrated as
    stalled — never recovered, and no false death is written."""
    journal = RunJournal(journal_path(cfg))
    run_id = journal.start("suspended mid provider call",
                           owner_pid=RECYCLED_PID)
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))
    token = f"v2:{RECYCLED_PID}:verified"       # current, comparable format
    with sqlite3.connect(journal.path) as db:   # silent for a very long time
        db.execute("UPDATE runs SET owner_token=?, lease_expires_at=1, "
                   "heartbeat_at=1 WHERE run_id=?", (token, run_id))

    recovered = journal.recover_abandoned(current_pid=os.getpid(),
                                          alive=lambda _pid: True,
                                          identity=lambda _pid: token)
    assert recovered == []
    assert journal.state(run_id) == RunState.GENERATING
    # The silence is still narrated for the UI, honestly.
    assert journal.mark_stalled_runs(alive=lambda _pid: True) == [run_id]


def test_cancelling_with_a_dead_reused_owner_completes_to_cancelled(cfg):
    """A durable cancellation is never absorbed forever by a recycled pid."""
    journal = RunJournal(journal_path(cfg))
    run_id = journal.start("cancel me", owner_pid=RECYCLED_PID)
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))
    journal.request_cancel(run_id)
    # The cancel request itself set a lease, so CANCELLING is supervisable.
    assert journal.latest()["lease_expires_at"] is not None
    age_lease(journal, run_id, 1)
    swept = daemon.watchdog_sweep(cfg)
    assert swept["recovered"] == [run_id]
    row = journal.latest()
    assert row["state"] == "CANCELLED" and row["outcome"] == "cancelled"
    assert journal.start("next task")


# ------------------------------------------------------- schema v1 migration
def test_v1_active_row_migrates_into_supervision(cfg):
    """A legacy ACTIVE row is backfilled with a lease at migration time and
    from then on stalls, reclaims and cancels like any other row — no more
    silent limbo blocking the single run slot forever."""
    path = journal_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.executescript(V1_SCHEMA)
        db.execute(
            "INSERT INTO runs VALUES('legacy-active','old build','','',"
            "'GENERATING','','',?,1.0,2.0,NULL)", (RECYCLED_PID,))
        db.execute(
            "INSERT INTO run_events(run_id,t,kind,actor,text,detail,state) "
            "VALUES('legacy-active',1.0,'run_started','controller','queued','',"
            "'QUEUED')")

    journal = RunJournal(path)
    row = journal.latest()
    assert row["lease_expires_at"] is not None      # backfilled at migration
    assert row["heartbeat_at"] is not None
    # Immediately after migration the row has one full lease of grace.
    swept = daemon.watchdog_sweep(cfg)
    assert swept["stalled"] == [] and swept["recovered"] == []
    # The legacy owner never heartbeats; once its grace runs out the row is
    # narrated stalled and then reclaimed despite pid 1 being "alive".
    age_lease(journal, "legacy-active", 1)
    swept = daemon.watchdog_sweep(cfg)
    assert swept["recovered"] == ["legacy-active"]
    assert journal.state("legacy-active") == RunState.INTERRUPTED
    assert journal.start("next task")               # the slot came back


def test_v1_cancel_sets_a_lease_so_cancelling_is_supervisable(cfg):
    path = journal_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.executescript(V1_SCHEMA)
        db.execute(
            "INSERT INTO runs VALUES('legacy-active','old build','','',"
            "'GENERATING','','',?,1.0,2.0,NULL)", (RECYCLED_PID,))

    journal = RunJournal(path)
    journal.request_cancel("legacy-active")
    assert journal.state("legacy-active") == RunState.CANCELLING
    assert journal.latest()["lease_expires_at"] is not None
    age_lease(journal, "legacy-active", 1)
    assert daemon.watchdog_sweep(cfg)["recovered"] == ["legacy-active"]
    assert journal.state("legacy-active") == RunState.CANCELLED


def test_v1_resting_rows_stay_unfilled_by_the_migration(tmp_path):
    """Only ACTIVE rows get liveness backfill; finished v1 rows keep making
    no liveness claim (same contract as the original migration test)."""
    path = tmp_path / "runtime.sqlite3"
    with sqlite3.connect(path) as db:
        db.executescript(V1_SCHEMA)
        db.execute(
            "INSERT INTO runs VALUES('old-run','legacy task','','','PASSED',"
            "'passed','',1,1,2,2)")
    row = RunJournal(path).latest()
    assert row["lease_expires_at"] is None
    assert row["heartbeat_at"] is None


# ------------------------------------------------- parked command surface
def test_request_cancel_takes_the_parked_out_edge(tmp_path):
    """PROVIDER_UNAVAILABLE -> CANCELLED is a real command surface, not a
    declared-but-dead edge: no worker owns a parked run, so Stop lands
    directly in CANCELLED."""
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    run_id = journal.start("parks")
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))
    journal.append(run_id, event(
        "loop", "waiting", RunState.PROVIDER_UNAVAILABLE,
        kind="provider_unavailable"))
    result = journal.request_cancel(run_id)
    assert result == {"run_id": run_id, "state": "CANCELLED",
                      "requested": True}
    row = journal.latest()
    assert row["state"] == "CANCELLED" and row["outcome"] == "cancelled"
    assert row["lease_expires_at"] is None
    # Idempotent-adjacent: a second stop has nothing to cancel.
    with pytest.raises(RuntimeError):
        journal.request_cancel(run_id)


def test_request_cancel_without_id_falls_back_to_the_parked_run(tmp_path):
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    run_id = journal.start("parks")
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))
    journal.append(run_id, event(
        "loop", "waiting", RunState.PROVIDER_UNAVAILABLE,
        kind="provider_unavailable"))
    assert journal.request_cancel()["run_id"] == run_id


# --------------------------------------------- torn writes heal at the source
def test_park_writes_the_cycle_decision_object_first(science, cfg):
    """The _drive park path itself records the decision object (cycle first,
    run second): a parked run never exists without something to rule on, and
    the reconciler is only a backstop."""
    journal = park_via_service(cfg, "first outage")
    row = journal.latest()
    assert row["state"] == "PROVIDER_UNAVAILABLE"
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    escalated = [dict(c, cycle_id=cid) for cid, c in
                 store.snapshot()["cycles"].items()
                 if c["status"] == "ESCALATED"]
    assert len(escalated) == 1
    assert "provider failure" in escalated[0]["escalation_reason"]
    # The backstop has nothing left to do.
    assert daemon.reconcile_human_wait(cfg) == {
        "run_completed": None, "cycle_recorded": None}


def test_budget_park_names_one_kind_on_both_slices(science, cfg):
    """The cross-slice contract this fix restores. A budget (usage-guardrail)
    pause parks the run with waiting_reason.kind == 'budget' (slice one), and
    the cycle decision object for the SAME stop carries escalation_kind ==
    'budget' too (slice three) — not the blanket 'provider' that would offer a
    person connection remedies for a spending cap. The escalation surface then
    routes to the billing remedies, never the audit fallback."""
    from crossaudit.console import overview
    from crossaudit.errors import escalation_remediations

    journal = park_budget_via_service(cfg, "spendy task")
    row = journal.latest()
    assert row["state"] == "PROVIDER_UNAVAILABLE"
    assert row["waiting_reason"]["kind"] == "budget"          # slice one
    assert row["waiting_reason"]["category"] == "budget"

    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    escalated = [c for c in store.snapshot()["cycles"].values()
                 if c["status"] == "ESCALATED"]
    assert len(escalated) == 1
    assert escalated[0]["escalation_kind"] == "budget"        # slice three agrees

    rows = overview.escalations(cfg)
    assert rows and rows[-1]["kind"] == "budget"
    # Billing remedies reach the escalation surface — the whole point of the
    # 'budget' kind. The old bug fell back to the content ("audit") set.
    assert rows[-1]["remediations"] == ["open_billing", "continue_later", "stop"]
    assert (escalation_remediations("budget")
            != escalation_remediations("audit"))


def test_reconcile_records_a_torn_budget_park_as_budget_kind(science, cfg):
    """Direction-B backstop stays kind-consistent: a budget park whose cycle
    write was torn (worker died before the source-first write landed) is
    reconciled with escalation_kind == 'budget', read from the run's own
    waiting kind — not re-flattened to 'provider'."""
    from crossaudit.console import overview

    journal = RunJournal(journal_path(cfg))
    run_id = journal.start("spendy task", chat_id="history")
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))
    journal.append(run_id, event(
        "loop", "waiting for provider", RunState.PROVIDER_UNAVAILABLE,
        kind="provider_unavailable",
        detail="Local usage guardrail paused provider calls.",
        waiting_reason={"kind": "budget", "category": "budget",
                        "detail": "Local usage guardrail paused provider calls."}))

    result = daemon.reconcile_human_wait(cfg, journal)
    assert result["cycle_recorded"]
    rows = overview.escalations(cfg)
    assert rows and rows[-1]["kind"] == "budget"
    assert rows[-1]["remediations"] == ["open_billing", "continue_later", "stop"]


def test_retry_after_resolution_reescalates_the_next_outage(science, cfg):
    """The refuter's suppression trap: resolve+retry inside one integer
    second, then a second outage. The new stop must produce a new pending
    decision — never an OPEN cycle beside a parked run with no remedy."""
    journal = park_via_service(cfg, "first outage")
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    cid = next(cid for cid, c in store.snapshot()["cycles"].items()
               if c["status"] == "ESCALATED")
    store.resolve_escalation(
        cid, "reopen", "Retry after reviewing the provider connection.")
    assert store.cycle(cid)["status"] == "OPEN"

    park_via_service(cfg, "second outage")          # same second is fine
    assert store.cycle(cid)["status"] == "ESCALATED"
    assert journal.latest()["state"] == "PROVIDER_UNAVAILABLE"
    # Reconcile stays a no-op: nothing is torn.
    assert daemon.reconcile_human_wait(cfg) == {
        "run_completed": None, "cycle_recorded": None}


def test_reconcile_leaves_a_closed_ruling_closed(science, cfg):
    """After a human closes the provider escalation, neither the sweep nor a
    later reconcile may resurrect it (probe: resolved escalation returning as
    'needs your decision')."""
    from crossaudit.console import server as server_mod

    journal = park_via_service(cfg, "parked task")
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    cid = next(cid for cid, c in store.snapshot()["cycles"].items()
               if c["status"] == "ESCALATED")
    store.resolve_escalation(cid, "close", "not worth retrying")

    snap = server_mod.snapshot(cfg)
    assert all(r["cycle_id"] != cid for r in snap["escalations"])
    assert daemon.reconcile_human_wait(cfg) == {
        "run_completed": None, "cycle_recorded": None}
    assert store.cycle(cid)["status"] == "BLOCKED"
    # The parked row does not hold the slot.
    assert journal.start("new task")


# ------------------------------------------ direction A scans, not just latest
def test_direction_a_completes_an_older_torn_row_past_a_newer_run(science, cfg):
    """A retry racing ahead of the sweep must not orphan the torn half."""
    journal = RunJournal(journal_path(cfg))
    r1 = journal.start("die after escalating", owner_pid=DEAD_PID,
                       chat_id="history")
    journal.append(r1, event("generator", "writing", RunState.GENERATING))
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    store.record_build_escalation(
        cfg.science_repo, "a" * 40,
        "generator provider failure in round 1: connection refused", 1,
        "history", "die after escalating")
    journal.recover_abandoned(current_pid=os.getpid(), alive=lambda _pid: False)
    assert journal.state(r1) == RunState.INTERRUPTED

    r2 = journal.start("retry")                      # newer run exists
    result = daemon.reconcile_human_wait(cfg, journal)
    assert result["run_completed"] == r1
    row_states = {r["run_id"]: r["state"] for r in journal.recent()}
    assert row_states[r1] == "WAITING_FOR_HUMAN"
    assert row_states[r2] == "QUEUED"                # untouched
    # Idempotent once completed.
    journal.finish(r2, "passed")
    assert daemon.reconcile_human_wait(cfg, journal) == {
        "run_completed": None, "cycle_recorded": None}


# ---------------------------------------------------------- CLI visibility
def test_cmd_status_reports_the_abandoned_run(science, cfg, capsys,
                                              monkeypatch):
    from crossaudit.cli import main as cli_main

    journal = RunJournal(journal_path(cfg))
    run_id = journal.start("killed -9", owner_pid=DEAD_PID)
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))

    monkeypatch.chdir(science)
    cli_main.cmd_status(argparse.Namespace(json=True))
    data = json.loads(capsys.readouterr().out)
    assert data["run"]["run_id"] == run_id
    assert data["run"]["state"] == "GENERATING"
    assert "recovery pending" in data["run"]["note"]

    cli_main.cmd_status(argparse.Namespace(json=False))
    human = capsys.readouterr().out
    assert "run: GENERATING" in human and "killed -9" in human


def test_cmd_status_reports_a_parked_run(science, cfg, capsys, monkeypatch):
    from crossaudit.cli import main as cli_main

    journal = RunJournal(journal_path(cfg))
    run_id = journal.start("parked")
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))
    journal.append(run_id, event(
        "loop", "waiting", RunState.PROVIDER_UNAVAILABLE,
        kind="provider_unavailable",
        waiting_reason={"kind": "provider", "category": "routes_exhausted",
                        "detail": "all routes failed"}))
    monkeypatch.chdir(science)
    cli_main.cmd_status(argparse.Namespace(json=True))
    data = json.loads(capsys.readouterr().out)
    assert data["run"]["state"] == "PROVIDER_UNAVAILABLE"
    assert "all routes failed" in data["run"]["note"]


# ===================================================================== R2
# Second adversarial round: owner identity, evidence-linked reconciliation,
# run-first park order, and "a provider failure is never a finding".

def test_stall_threshold_covers_the_longest_shipped_provider_timeout():
    """A single clean first-attempt call must never be narrated as a stall:
    the threshold is pinned against the largest shipped adapter timeout so a
    future timeout bump fails here instead of silently re-opening the gap."""
    from crossaudit.providers.codex_subscription import DEFAULT_TIMEOUT_S

    assert STALL_AFTER_SECONDS >= DEFAULT_TIMEOUT_S + 60


def test_resilience_renews_the_lease_before_each_attempt(science, cfg,
                                                         monkeypatch):
    """Retry sequences are healthy work: every attempt renews the lease
    through the on_event.heartbeat handle so backoff cannot read as silence."""
    from crossaudit.providers import resilience

    beats = []

    def flaky(**_kwargs):
        raise ProviderDenial("HTTP 500", category="transport", retryable=True,
                             status=500)

    monkeypatch.setattr(resilience, "get_provider", lambda _p: flaky)
    monkeypatch.setattr(resilience, "_sleep", lambda _s: None)
    monkeypatch.setenv(cfg.auditor.key_env, "test-key")

    def on_event(*_args):
        pass

    on_event.heartbeat = lambda: beats.append(1)
    with pytest.raises(ProviderDenial):
        resilience.complete(cfg, "auditor", cfg.auditor, system="s",
                            prompt="p", on_event=on_event)
    assert len(beats) >= 2          # one renewal per attempt, not per call


def test_reconcile_never_rewrites_an_unrelated_old_crash(science, cfg):
    """A fresh escalation is evidence about its own stop: an old, genuinely
    crashed INTERRUPTED row with no association (no run_id reference, no
    chat/task match, not the newest row) keeps its crash surface."""
    journal = RunJournal(journal_path(cfg))
    r_old = journal.start("old crashed task", chat_id="a" * 16,
                          owner_pid=DEAD_PID)
    journal.append(r_old, event("generator", "writing", RunState.GENERATING))
    journal.recover_abandoned(current_pid=os.getpid(), alive=lambda _pid: False)
    r_new = journal.start("newer unrelated task", chat_id="b" * 16)
    journal.append(r_new, event("generator", "writing", RunState.GENERATING))
    journal.finish(r_new, "passed")

    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    store.record_build_escalation(
        cfg.science_repo, "c" * 40,
        "provider failure left THE OTHER TASK waiting for a person", 1,
        chat_id="c" * 16, task="the other task")

    result = daemon.reconcile_human_wait(cfg, journal)
    assert result["run_completed"] is None
    states = {r["run_id"]: r["state"] for r in journal.recent()}
    assert states[r_old] == "INTERRUPTED"
    # The crash-recovery surface (dismiss) still works — the flip that would
    # have removed it never happened.
    assert journal.dismiss_interruption(r_old) is True


def test_direction_a_heals_exactly_the_referenced_run(science, cfg):
    """With a run_id on the escalation, the heal lands on that run even when
    it is neither the newest row nor a chat/task match — and only there."""
    journal = RunJournal(journal_path(cfg))
    r_old = journal.start("unrelated old crash", chat_id="a" * 16,
                          owner_pid=DEAD_PID)
    journal.append(r_old, event("generator", "writing", RunState.GENERATING))
    journal.recover_abandoned(current_pid=os.getpid(), alive=lambda _pid: False)

    r_torn = journal.start("die after escalating", chat_id="b" * 16,
                           owner_pid=DEAD_PID)
    journal.append(r_torn, event("generator", "writing", RunState.GENERATING))
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    store.record_build_escalation(
        cfg.science_repo, "a" * 40,
        "generator provider failure in round 1: connection refused", 1,
        chat_id="", task="different words entirely", run_id=r_torn)
    journal.recover_abandoned(current_pid=os.getpid(), alive=lambda _pid: False)
    r_latest = journal.start("retry")            # neither torn row is newest

    result = daemon.reconcile_human_wait(cfg, journal)
    assert result["run_completed"] == r_torn
    states = {r["run_id"]: r["state"] for r in journal.recent()}
    assert states[r_torn] == "WAITING_FOR_HUMAN"
    assert states[r_old] == "INTERRUPTED"        # untouched
    assert states[r_latest] == "QUEUED"


def test_cancel_racing_the_park_mints_no_orphan_escalation(science, cfg):
    """Run-first order: the user's Stop landing between the park append and
    the cycle write must not leave an ESCALATED decision object demanding a
    ruling on a task the user just stopped."""
    service = RunCommandService(cfg)
    journal = service.journal
    run_id = journal.start("parked task")
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))

    original = service._record_park_cycle

    def cancel_then_record(rid, exc):
        journal.request_cancel(rid)      # the Stop wins the interleave
        original(rid, exc)

    service._record_park_cycle = cancel_then_record
    outage = ProviderDenial("all configured generator provider routes failed",
                            category="routes_exhausted", retryable=False,
                            status=503)
    assert service._park_provider_unavailable(run_id, outage) is True
    assert journal.state(run_id) == RunState.CANCELLED
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    cycles = store.snapshot().get("cycles", {})
    assert all(c.get("status") != "ESCALATED" for c in cycles.values())


def test_stopping_a_parked_run_closes_its_referenced_escalation(science, cfg):
    """Stop on a parked run is the human ruling: the pending decision object
    that references this run is closed with it, not left demanding a
    decision nobody is waiting on."""
    journal = park_via_service(cfg, "parked task")
    run_id = journal.latest()["run_id"]
    service = RunCommandService(cfg)
    result = service.request_cancel(run_id)
    assert result["state"] == "CANCELLED"
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    cycles = store.snapshot().get("cycles", {})
    assert all(c.get("status") != "ESCALATED" for c in cycles.values())
    assert any(c.get("closed_by_human") for c in cycles.values())


def test_close_ruling_settles_the_referenced_parked_run(science, cfg):
    journal = park_via_service(cfg, "parked task")
    run_id = journal.latest()["run_id"]
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    cid = next(cid for cid, c in store.snapshot()["cycles"].items()
               if c["status"] == "ESCALATED")
    ruled = store.resolve_escalation(cid, "close", "not worth retrying")
    assert daemon.settle_closed_escalation(cfg, ruled) is True
    assert journal.state(run_id) == RunState.CANCELLED


def test_a_cancel_racing_a_refused_denial_still_lands_cancelled(cfg):
    """The Denial fallback converts the expected cancellation race instead of
    stranding the row CANCELLING with a dead worker."""
    service = RunCommandService(cfg)
    journal = service.journal
    real_finish = journal.finish
    raced = {"done": False}

    def racing_finish(run_id, outcome, error=""):
        if outcome == "refused" and not raced["done"]:
            raced["done"] = True
            journal.request_cancel(run_id)     # the Stop wins the race now
        return real_finish(run_id, outcome, error)

    journal.finish = racing_finish

    def worker(_prepared, emit):
        emit(event("generator", "writing", RunState.GENERATING))
        raise ProviderDenial("endpoint rejected the key",
                             category="authentication", retryable=False,
                             status=401)

    with pytest.raises(ProviderDenial):
        service.start(lambda: PreparedRun(task="refused mid-cancel"), worker,
                      background=False)
    row = journal.latest()
    assert row["state"] == "CANCELLED"
    assert row["outcome"] == "cancelled"


def test_generator_outage_at_a_passed_head_still_parks(science, cfg,
                                                       monkeypatch):
    """The verdict-protection guard must never detonate the loop: with a
    PASSED cycle at HEAD the cycle write is refused (fail-closed), the run
    still parks with its waiting reason — the run-side signal carries the
    human surface — and nothing is presented as a content refusal."""
    from crossaudit.cli import build as build_mod
    from crossaudit.gitio import git

    head = git("rev-parse", "HEAD", cwd=science)
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    cycle = store.open_or_advance(cfg.science_repo, head, None)
    store.record_verdict(cycle["cycle_id"], head, "PASS", "e" * 64, 3)

    def outage(**_kwargs):
        raise ProviderDenial("all configured generator provider routes failed",
                             category="routes_exhausted", retryable=False,
                             status=503)

    monkeypatch.setattr(build_mod, "_generator_complete",
                        lambda *_a, **_k: object())
    monkeypatch.setattr(build_mod.gen_mod, "generate", outage)
    monkeypatch.chdir(science)
    scoped = replace(cfg, scope_dirs=["experiments"])

    service = RunCommandService(scoped)
    code = service.start(
        lambda: PreparedRun(task="demo task", chat_id="history"),
        lambda prepared, emit: build_mod.run_loop(
            scoped, prepared.task, on_event=emit, chat_id="history"),
        background=False)

    assert code == EXIT_ESCALATED                  # no unhandled Denial
    row = service.journal.latest()
    assert row["state"] == "PROVIDER_UNAVAILABLE"
    assert row["outcome"] == "provider_unavailable"
    assert row["waiting_reason"]["category"] == "routes_exhausted"
    # The recorded PASS is intact and no escalation was minted over it.
    assert store.cycle(cycle["cycle_id"])["status"] == "PASSED"
    # The reconciler stays fail-closed rather than guessing.
    assert daemon.reconcile_human_wait(cfg, service.journal) == {
        "run_completed": None, "cycle_recorded": None}


# ------------------------------------------ provider failure is not a finding
def test_provider_failure_is_never_rendered_as_a_finding(science, cfg,
                                                         monkeypatch):
    """The absorbed branch (deterministic tier already decisive) writes a
    plain-prose unavailability note, never a CA-META-002 BLOCKER: everything
    in the finding shape is machine-parsed as audit content and would be fed
    to the generator to 'fix' and listed in the decision modal."""
    from crossaudit.auditor.run import run_audit
    from crossaudit.dispute import parse_findings
    from crossaudit.generator import render_findings
    from crossaudit.providers import resilience

    def exhausted(*_a, **_k):
        raise ProviderDenial(
            "all configured auditor provider routes failed. HTTP 401",
            category="routes_exhausted", retryable=False, status=401)

    monkeypatch.setattr(resilience, "complete", exhausted)
    constitution = (science / "AUDIT_RULES.md").read_text()
    outcome = run_audit(
        cfg=cfg, sha="c" * 40, round_=3,
        files={"experiments/demo/SUMMARY.md": b"missing everything\n"},
        notes=[], constitution=constitution, constitution_commit="d" * 40)
    assert outcome.verdict == "BLOCKED"            # the DCL tier's own verdict
    assert outcome.integrity == "PROVIDER_FAILURE" # the receipt stays truthful
    assert "CA-META-002" not in outcome.report
    assert "Model audit unavailable (provider failure:" in outcome.report
    assert all(f.rule != "CA-META-002" for f in parse_findings(outcome.report))
    assert "auditor call failed" not in render_findings(outcome.report)


def test_provider_failure_escalation_routes_to_provider_remedies(science, cfg):
    """Round-budget exhaustion on provider-failure rounds must reach the
    decision modal as kind='provider' with provider remedies, not as audit
    content asking for generator guidance."""
    from crossaudit.console import overview

    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    cycle = store.open_or_advance(cfg.science_repo, "c" * 40, None)
    status = store.record_verdict(
        cycle["cycle_id"], "c" * 40, "BLOCKED", "e" * 64, 1,
        escalation_reason="provider failure: the model audit could not run "
                          "— HTTP 401")
    assert status == "ESCALATED"
    rows = overview.escalations(cfg)
    assert rows and rows[0]["kind"] == "provider"
    assert not rows[0]["requested"].startswith("Tell the generator")


@pytest.mark.parametrize("files", [dict(CLEAN_INCREMENT)])
def test_budget_guardrail_parks_the_audit_round(science, cfg, monkeypatch,
                                                files):
    """category='budget' (enforce_budget refuses before any route is tried)
    is a guardrail stop, not audit content: a clean round re-raises it to the
    park path exactly like an outage."""
    from crossaudit.auditor.run import run_audit
    from crossaudit.providers import resilience

    def guardrail(*_a, **_k):
        raise ProviderDenial(
            "Local usage guardrail paused provider calls. The next request "
            "is estimated to exceed the daily token limit.",
            category="budget", retryable=False)

    monkeypatch.setattr(resilience, "complete", guardrail)
    constitution = (science / "AUDIT_RULES.md").read_text()
    with pytest.raises(ProviderDenial) as caught:
        run_audit(cfg=cfg, sha="c" * 40, round_=1, files=files, notes=[],
                  constitution=constitution, constitution_commit="d" * 40)
    assert caught.value.detail.get("category") == "budget"


def test_budget_guardrail_parks_the_build_loop_without_burning_rounds(
        science, cfg, monkeypatch):
    """The generator-side twin: a non-retryable guardrail stop parks after
    ONE attempt with a budget-typed waiting reason — never a zero-call loop
    that burns the whole round budget and escalates as spent revisions."""
    from crossaudit.cli import build as build_mod

    calls = []

    def guardrail(**_kwargs):
        calls.append(1)
        raise ProviderDenial(
            "Local usage guardrail paused provider calls. The next request "
            "is estimated to exceed the daily token limit.",
            category="budget", retryable=False)

    monkeypatch.setattr(build_mod, "_generator_complete",
                        lambda *_a, **_k: object())
    monkeypatch.setattr(build_mod.gen_mod, "generate", guardrail)
    monkeypatch.chdir(science)
    scoped = replace(cfg, scope_dirs=["experiments"])

    service = RunCommandService(scoped)
    code = service.start(
        lambda: PreparedRun(task="produce the experiment"),
        lambda prepared, emit: build_mod.run_loop(
            scoped, prepared.task, on_event=emit),
        background=False)

    assert code == EXIT_ESCALATED
    assert len(calls) == 1                       # one attempt, no burn loop
    row = service.journal.latest()
    assert row["state"] == "PROVIDER_UNAVAILABLE"
    assert row["waiting_reason"] == {
        "kind": "budget", "category": "budget",
        "detail": row["waiting_reason"]["detail"]}
    assert "guardrail" in row["waiting_reason"]["detail"]


# --------------------------------------------------------------- page pill
def test_the_decide_pill_rides_on_escalation_or_run_side_signal():
    from crossaudit.console.page import PAGE

    # A parked run maps to "decide" while an escalation is pending OR while
    # its own waiting reason stands (the run-side signal must carry the ask
    # even when fail-closed verdict protection refused the decision object).
    # Close rulings settle the referenced run, so the signal cannot outlive
    # its decision.
    assert ("if(currentEscalations(d).length||p.waiting_reason)"
            "return {key:'decide'") in PAGE
    assert ("if(p&&p.state==='PROVIDER_UNAVAILABLE')return {key:'decide'"
            not in PAGE)
    # The banner counts a parked-alone run as needing attention.
    assert "parkedAlone" in PAGE
    # The A-contract vocabulary stays.
    assert "PROVIDER_UNAVAILABLE:'decide'" in PAGE
