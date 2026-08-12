"""A stuck run is structurally impossible.

Four properties hold together: every worker write renews a heartbeat and a
lease; a run starved of providers parks in an explicit PROVIDER_UNAVAILABLE
state instead of masquerading as a content refusal; a watchdog sweep is
idempotent and narrates silence without inventing failures; and the two-store
"needs a human" write reconciles from either torn half.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from crossaudit.console import daemon
from crossaudit.console.server import serve
from crossaudit.controller import StateStore
from crossaudit.errors import EXIT_ESCALATED, ConfigDenial, ProviderDenial
from crossaudit.runtime import (
    ACTIVE_STATES,
    LEASE_SECONDS,
    PARKED_STATES,
    TERMINAL_STATES,
    PreparedRun,
    RunCommandService,
    RunEvent,
    RunJournal,
    RunState,
    journal_path,
)
from crossaudit.runtime.runs import (
    _TRANSITIONS,
    SCHEMA_VERSION,
    STALL_AFTER_SECONDS,
)

#: A pid that can never be alive on macOS or Linux (both cap well below it),
#: so liveness probes are deterministic without spawning processes.
DEAD_PID = 999999


def event(actor: str, text: str, state: RunState, *, detail: str = "",
          kind: str = "activity", waiting_reason: dict | None = None) -> RunEvent:
    return RunEvent(actor=actor, text=text, state=state, detail=detail,
                    kind=kind, waiting_reason=waiting_reason)


def ticking(start: float = 1000.0):
    """A controllable clock: liveness must be testable without real minutes."""
    state = {"now": start}

    def clock() -> float:
        return state["now"]

    clock.advance = lambda seconds: state.__setitem__(
        "now", state["now"] + seconds)
    return clock


# ------------------------------------------------------------- state machine
def test_provider_unavailable_transitions_follow_the_table(tmp_path):
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    run_id = journal.start("park and retry")
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))
    journal.append(run_id, event(
        "loop", "waiting for provider", RunState.PROVIDER_UNAVAILABLE,
        kind="provider_unavailable",
        waiting_reason={"kind": "provider", "category": "routes_exhausted",
                        "detail": "all routes failed"}))
    assert journal.state(run_id) == RunState.PROVIDER_UNAVAILABLE
    # A human retry resumes the starved phase; nothing resumes it silently.
    journal.append(run_id, event("generator", "retrying", RunState.GENERATING))
    assert journal.state(run_id) == RunState.GENERATING


def test_provider_unavailable_is_not_enterable_from_queued(tmp_path):
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    run_id = journal.start("no provider phase yet")
    with pytest.raises(RuntimeError, match="invalid run transition"):
        journal.append(run_id, event(
            "loop", "waiting", RunState.PROVIDER_UNAVAILABLE))


def test_terminal_states_do_not_reopen_into_a_provider_wait(tmp_path):
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    run_id = journal.start("finished")
    journal.finish(run_id, "passed")
    with pytest.raises(RuntimeError, match="invalid run transition"):
        journal.append(run_id, event(
            "loop", "waiting", RunState.PROVIDER_UNAVAILABLE))


def test_every_nonterminal_state_reaches_a_terminal_state():
    """No absorbing non-terminal exists anywhere in the transition table."""
    for origin in RunState:
        if origin in TERMINAL_STATES:
            continue
        seen, frontier = {origin}, [origin]
        while frontier:
            reached = _TRANSITIONS[frontier.pop()]
            if reached & TERMINAL_STATES:
                break
            for state in reached - seen:
                seen.add(state)
                frontier.append(state)
        else:
            raise AssertionError(
                f"{origin.value} cannot reach any terminal state")


def test_parked_runs_do_not_hold_the_single_run_slot(tmp_path):
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    run_id = journal.start("parks")
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))
    journal.append(run_id, event(
        "loop", "waiting for provider", RunState.PROVIDER_UNAVAILABLE,
        kind="provider_unavailable"))
    assert journal.latest()["finished"] is True
    assert RunState.PROVIDER_UNAVAILABLE in PARKED_STATES
    assert journal.start("next task") != run_id


# ---------------------------------------------------------- waiting reasons
def test_waiting_reason_round_trips_and_clears_on_the_next_transition(tmp_path):
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    run_id = journal.start("why am I waiting")
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))
    reason = {"kind": "provider", "category": "circuit_open",
              "detail": "routes cooling down"}
    journal.append(run_id, event(
        "loop", "waiting for provider", RunState.PROVIDER_UNAVAILABLE,
        kind="provider_unavailable", waiting_reason=reason))
    assert journal.latest()["waiting_reason"] == reason
    journal.append(run_id, event("generator", "retrying", RunState.GENERATING))
    assert journal.latest()["waiting_reason"] is None


# ---------------------------------------------------------------- migration
def test_pre_liveness_database_migrates_in_place(tmp_path):
    path = tmp_path / "runtime.sqlite3"
    with sqlite3.connect(path) as db:
        db.executescript(
            """
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
            INSERT INTO runs VALUES(
                'old-run','legacy task','','','PASSED','passed','',1,1,2,2
            );
            """
        )

    journal = RunJournal(path)
    row = journal.latest()
    assert row["task"] == "legacy task"
    assert row["heartbeat_at"] is None
    assert row["lease_expires_at"] is None
    assert row["waiting_reason"] is None
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    # New rows written through the migrated file carry live leases.
    run_id = journal.start("post-migration work")
    fresh = journal.latest()
    assert fresh["run_id"] == run_id and fresh["lease_expires_at"] is not None


# --------------------------------------------------------- heartbeat & lease
def test_every_journal_write_renews_the_heartbeat_and_lease(tmp_path):
    clock = ticking()
    journal = RunJournal(tmp_path / "runtime.sqlite3", clock=clock)
    run_id = journal.start("stay visible")
    first = journal.latest()
    assert first["heartbeat_at"] == 1000.0
    assert first["lease_expires_at"] == 1000.0 + LEASE_SECONDS
    clock.advance(50)
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))
    renewed = journal.latest()
    assert renewed["heartbeat_at"] == 1050.0
    assert renewed["lease_expires_at"] == 1050.0 + LEASE_SECONDS


def test_provider_boundary_heartbeat_adds_no_narration_event(tmp_path):
    clock = ticking()
    journal = RunJournal(tmp_path / "runtime.sqlite3", clock=clock)
    run_id = journal.start("quiet provider turn")
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))
    before = journal.latest()
    clock.advance(90)
    assert journal.heartbeat(run_id) is True
    after = journal.latest()
    assert len(after["steps"]) == len(before["steps"])
    assert after["heartbeat_at"] == 1090.0
    assert after["state"] == "GENERATING"


def test_heartbeat_refuses_runs_no_worker_owns(tmp_path):
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    run_id = journal.start("done")
    journal.finish(run_id, "passed")
    assert journal.heartbeat(run_id) is False


def test_active_rows_always_carry_a_live_lease_at_write_time(tmp_path):
    clock = ticking()
    journal = RunJournal(tmp_path / "runtime.sqlite3", clock=clock)
    run_id = journal.start("invariant")
    for state in (RunState.GENERATING, RunState.AUDITING, RunState.REVISING):
        journal.append(run_id, event("loop", "moving", state))
        row = journal.latest()
        assert RunState(row["state"]) in ACTIVE_STATES
        assert row["lease_expires_at"] > clock()


# ------------------------------------------------------------------ watchdog
def test_stall_notes_are_idempotent_and_change_no_state(tmp_path):
    clock = ticking()
    journal = RunJournal(tmp_path / "runtime.sqlite3", clock=clock)
    run_id = journal.start("goes quiet")
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))
    clock.advance(STALL_AFTER_SECONDS + 30)

    noted = journal.mark_stalled_runs(alive=lambda _pid: True)
    assert noted == [run_id]
    row = journal.latest()
    assert row["state"] == "GENERATING"                 # display-only
    assert row["steps"][-1]["kind"] == "run_stalled"
    assert (f"no heartbeat for {int(STALL_AFTER_SECONDS) + 30}s"
            in row["steps"][-1]["detail"])
    # The note must not renew the very heartbeat it reports on.
    assert row["heartbeat_at"] == 1000.0

    # Idempotent until the worker speaks again.
    assert journal.mark_stalled_runs(alive=lambda _pid: True) == []
    clock.advance(1)
    journal.append(run_id, event("generator", "resumed", RunState.GENERATING))
    clock.advance(STALL_AFTER_SECONDS + 1)
    assert journal.mark_stalled_runs(alive=lambda _pid: True) == [run_id]


def test_a_live_lease_is_never_reported_stalled(tmp_path):
    clock = ticking()
    journal = RunJournal(tmp_path / "runtime.sqlite3", clock=clock)
    journal.start("healthy")
    clock.advance(LEASE_SECONDS / 2)
    assert journal.mark_stalled_runs(alive=lambda _pid: True) == []


def test_one_expired_lease_is_not_yet_narrated_stalled(tmp_path):
    """A single healthy provider turn can outlive one lease (it heartbeats
    only at its call boundaries); the stall narration must wait for the
    separate STALL_AFTER threshold rather than the lease itself."""
    clock = ticking()
    journal = RunJournal(tmp_path / "runtime.sqlite3", clock=clock)
    run_id = journal.start("long clean provider turn")
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))
    assert journal.heartbeat(run_id)              # provider-call entry
    clock.advance(LEASE_SECONDS + 30)             # mid-call: lease expired
    assert journal.mark_stalled_runs(alive=lambda _pid: True) == []
    row = journal.latest()
    assert all(s["kind"] != "run_stalled" for s in row["steps"])
    clock.advance(LEASE_SECONDS - 60)             # call exit at 180 s
    assert journal.heartbeat(run_id)
    assert journal.mark_stalled_runs(alive=lambda _pid: True) == []


def test_watchdog_sweep_recovers_dead_owners_and_stays_idempotent(cfg):
    journal = RunJournal(journal_path(cfg))
    run_id = journal.start("killed between transitions", owner_pid=DEAD_PID)
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))

    swept = daemon.watchdog_sweep(cfg)
    assert swept["changed"] is True and swept["recovered"] == [run_id]
    assert journal.latest()["state"] == "INTERRUPTED"
    again = daemon.watchdog_sweep(cfg)
    assert again["changed"] is False and again["recovered"] == []


def test_watchdog_preserves_cancelling_to_cancelled_authority(cfg):
    journal = RunJournal(journal_path(cfg))
    run_id = journal.start("cancel then die", owner_pid=DEAD_PID)
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))
    journal.request_cancel(run_id)

    swept = daemon.watchdog_sweep(cfg)
    assert swept["recovered"] == [run_id]
    row = journal.latest()
    assert row["state"] == "CANCELLED" and row["outcome"] == "cancelled"


def test_watchdog_notes_an_expired_lease_under_a_living_owner(cfg):
    journal = RunJournal(journal_path(cfg))
    run_id = journal.start("alive but silent")
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))
    with sqlite3.connect(journal.path) as db:      # age the lease, not the pid
        db.execute("UPDATE runs SET lease_expires_at=1 WHERE run_id=?",
                   (run_id,))

    swept = daemon.watchdog_sweep(cfg)
    assert swept["stalled"] == [run_id]
    row = journal.latest()
    assert row["state"] == "GENERATING"
    assert row["steps"][-1]["kind"] == "run_stalled"
    assert daemon.watchdog_sweep(cfg)["stalled"] == []


def test_console_watchdog_thread_starts_and_stops_with_the_server(cfg):
    _url, httpd = serve(cfg, port=0)
    try:
        assert httpd.watchdog_thread is not None
        assert httpd.watchdog_thread.is_alive()
    finally:
        httpd.server_close()
    assert not httpd.watchdog_thread.is_alive()


# --------------------------------------------- provider failure classification
def run_service(cfg, worker):
    service = RunCommandService(cfg)
    code = service.start(
        lambda: PreparedRun(task="classify this stop"), worker,
        background=False)
    return service, code


@pytest.mark.parametrize("category", ["routes_exhausted", "circuit_open"])
def test_route_exhaustion_parks_the_run_instead_of_refusing_it(cfg, category):
    def worker(_prepared, emit):
        emit(event("generator", "writing", RunState.GENERATING))
        emit(event("auditor", "reviewing", RunState.AUDITING, kind="audit_started"))
        raise ProviderDenial(
            "all configured auditor provider routes failed",
            category=category, retryable=False, status=503)

    service = RunCommandService(cfg)
    with pytest.raises(ProviderDenial):
        service.start(lambda: PreparedRun(task="audit under outage"), worker,
                      background=False)
    row = service.journal.latest()
    assert row["state"] == "PROVIDER_UNAVAILABLE"
    assert row["outcome"] == "provider_unavailable"
    assert row["waiting_reason"] == {
        "kind": "provider", "category": category,
        "detail": "all configured auditor provider routes failed"}
    assert [s["kind"] for s in row["steps"]][-2:] == [
        "provider_unavailable", "run_finished"]


def test_a_content_refusal_is_not_dressed_up_as_a_provider_outage(cfg):
    def worker(_prepared, emit):
        emit(event("generator", "writing", RunState.GENERATING))
        raise ConfigDenial("the task asked for something the rules forbid")

    service = RunCommandService(cfg)
    with pytest.raises(ConfigDenial):
        service.start(lambda: PreparedRun(task="refused on content"), worker,
                      background=False)
    row = service.journal.latest()
    assert row["state"] == "WAITING_FOR_HUMAN"
    assert row["outcome"] == "refused"
    assert row["waiting_reason"] is None


def test_route_exhaustion_before_any_provider_phase_fails_closed(cfg):
    def worker(_prepared, _emit):
        raise ProviderDenial("routes gone before work began",
                             category="routes_exhausted", retryable=False)

    service = RunCommandService(cfg)
    with pytest.raises(ProviderDenial):
        service.start(lambda: PreparedRun(task="early outage"), worker,
                      background=False)
    # QUEUED has no edge into the parked state; the run still ends waiting
    # for a person rather than crashing or passing.
    row = service.journal.latest()
    assert row["state"] == "WAITING_FOR_HUMAN" and row["outcome"] == "refused"


# ----------------------------------------------------------- reconciliation
def test_reconcile_completes_the_run_side_of_a_torn_escalation(science, cfg):
    """Direction A: cycle ESCALATED, worker died before the run recorded it."""
    journal = RunJournal(journal_path(cfg))
    run_id = journal.start("die after escalating", owner_pid=DEAD_PID,
                           chat_id="history")
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    store.record_build_escalation(
        cfg.science_repo, "a" * 40,
        "generator provider failure in round 1: connection refused", 1,
        "history", "die after escalating")
    journal.recover_abandoned(current_pid=os.getpid(), alive=lambda _pid: False)
    assert journal.latest()["state"] == "INTERRUPTED"

    result = daemon.reconcile_human_wait(cfg, journal)
    assert result["run_completed"] == run_id
    row = journal.latest()
    assert row["state"] == "WAITING_FOR_HUMAN"
    assert row["outcome"] == "escalated"
    assert row["steps"][-1]["kind"] == "human_wait_reconciled"
    assert daemon.interrupted(cfg) is None      # no longer presented as a crash
    repeat = daemon.reconcile_human_wait(cfg, journal)
    assert repeat["run_completed"] is None and repeat["cycle_recorded"] is None


def test_reconcile_records_the_cycle_side_of_a_torn_human_wait(science, cfg):
    """Direction B: run waits for a human, but no decision object exists."""
    journal = RunJournal(journal_path(cfg))
    run_id = journal.start("refused without a cycle", chat_id="history")
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))
    journal.finish(run_id, "refused", "the auditor endpoint rejected the key")

    result = daemon.reconcile_human_wait(cfg, journal)
    assert result["cycle_recorded"]
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    cycle = store.cycle(result["cycle_recorded"])
    assert cycle["status"] == "ESCALATED"
    assert "rejected the key" in cycle["escalation_reason"]
    assert cycle["task"] == "refused without a cycle"
    repeat = daemon.reconcile_human_wait(cfg, journal)
    assert repeat["cycle_recorded"] is None


def test_reconcile_routes_a_parked_run_to_the_provider_remedies(science, cfg):
    from crossaudit.console import overview

    journal = RunJournal(journal_path(cfg))
    run_id = journal.start("parked without a cycle", chat_id="history")
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))
    journal.append(run_id, event(
        "loop", "waiting for provider", RunState.PROVIDER_UNAVAILABLE,
        kind="provider_unavailable",
        waiting_reason={"kind": "provider", "category": "routes_exhausted",
                        "detail": "every auditor route failed"}))
    journal.finish(run_id, "provider_unavailable",
                   "every auditor route failed")

    result = daemon.reconcile_human_wait(cfg, journal)
    assert result["cycle_recorded"]
    rows = [row for row in overview.escalations(cfg)
            if row["cycle_id"] == result["cycle_recorded"]]
    assert rows and rows[0]["kind"] == "provider"
    assert "provider failure" in rows[0]["stop_reason"]


def test_reconcile_leaves_a_resolved_escalation_alone(science, cfg):
    """A ruling already given must never be re-escalated by the watchdog."""
    journal = RunJournal(journal_path(cfg))
    run_id = journal.start("already ruled on", chat_id="history")
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))
    journal.finish(run_id, "escalated")
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    cycle = store.record_build_escalation(
        cfg.science_repo, "b" * 40,
        "generator provider failure in round 1: outage", 1,
        "history", "already ruled on")
    store.resolve_escalation(cycle["cycle_id"], "close", "not worth retrying")

    result = daemon.reconcile_human_wait(cfg, journal)
    assert result["run_completed"] is None
    assert result["cycle_recorded"] is None
    assert store.cycle(cycle["cycle_id"])["status"] == "BLOCKED"


# ------------------------------------------------------------------- E2E
def test_routes_exhausted_build_parks_with_a_decision_object(
        science, cfg, monkeypatch):
    from dataclasses import replace

    from crossaudit.cli import build as build_mod
    from crossaudit.console import overview
    from crossaudit.console import server as server_mod

    def exhausted(**_kwargs):
        raise ProviderDenial(
            "all configured generator provider routes failed. "
            "anthropic:claude - invalid key",
            category="routes_exhausted", retryable=False, status=401)

    monkeypatch.setattr(build_mod, "_generator_complete",
                        lambda *_a, **_k: object())
    monkeypatch.setattr(build_mod.gen_mod, "generate", exhausted)
    monkeypatch.chdir(science)
    cfg = replace(cfg, scope_dirs=["experiments"])

    service = RunCommandService(cfg)
    code = service.start(
        lambda: PreparedRun(task="produce the experiment", chat_id="history"),
        lambda prepared, emit: build_mod.run_loop(
            cfg, prepared.task, on_event=emit, chat_id="history"),
        background=False)

    assert code == EXIT_ESCALATED
    row = service.journal.latest()
    assert row["state"] == "PROVIDER_UNAVAILABLE"
    assert row["finished"] is True
    assert row["outcome"] == "provider_unavailable"
    assert row["waiting_reason"]["kind"] == "provider"
    assert row["waiting_reason"]["category"] == "routes_exhausted"
    assert row["heartbeat_at"] is not None

    # The cycle side was written first: the four provider remedies hang off it.
    rows = overview.escalations(cfg)
    assert rows and rows[-1]["kind"] == "provider"
    assert "provider failure" in rows[-1]["stop_reason"]

    snapshot = server_mod.snapshot(cfg)
    assert snapshot["progress"]["state"] == "PROVIDER_UNAVAILABLE"
    assert snapshot["progress"]["waiting_reason"]["category"] == "routes_exhausted"
    assert snapshot["progress"]["heartbeat_at"] is not None
    assert snapshot["escalations"][-1]["kind"] == "provider"


def test_the_page_carries_the_provider_wait_vocabulary():
    from crossaudit.console.page import PAGE

    # The parked state feeds the six-state pill and the existing provider
    # escalation pipeline; the remedies themselves are A40 contract strings.
    assert "PROVIDER_UNAVAILABLE:'decide'" in PAGE
    assert "Waiting for provider" in PAGE
    assert "等待 provider" in PAGE
    assert "last heartbeat " in PAGE
    assert "最后心跳 " in PAGE
    assert "run_stalled" in PAGE
    for remedy in ("Retry provider now", "Review provider connection",
                   "Change model or fallback", "Stop this task",
                   "retry_provider"):
        assert remedy in PAGE
