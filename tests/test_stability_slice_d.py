"""Stability hardening Slice D: long sessions must not grow without bound.

Two MEDIUM findings from the long-thread / long-lived-project scenario, each
closed with a regression test that uses the REAL RunJournal and the REAL
StateStore — not a synthetic seam:

* D1 — three operational stores grew monotonically. ``state.json`` history
  appended on every controller event; the ``runs``/``run_events`` tables were
  INSERT-only. Retention now caps history on write (keeping each cycle's own
  ``updated_at`` so a trimmed cycle still renders a correct time), and a bounded
  journal sweep prunes TERMINAL runs older than a horizon AND outside the
  recent/reconciler window — never an active or parked run, never a row the
  reconciler still references, all in one BEGIN IMMEDIATE transaction.

* D2 — every SSE frame re-serialized a run's WHOLE step-log and the WHOLE cycle
  map (O(N^2) over a long run). Each frame now carries only a bounded recent
  tail of steps and the most-recent cycles; the latest state (last event,
  latest round marker, newest cycle) stays correct, and the full history stays
  queryable in the journal and controller store.

Evidence is never touched: git, receipts and the audit ledger are not pruned.
"""
from __future__ import annotations

import sqlite3

from crossaudit.console import daemon
from crossaudit.console.server import CYCLES_WINDOW, _ordered_cycles
from crossaudit.controller.state import HISTORY_LIMIT, StateStore
from crossaudit.runtime import (
    LATEST_STEP_LIMIT,
    RETAIN_RECENT_RUNS,
    RunEvent,
    RunJournal,
    RunState,
)


class _Clock:
    """A hand-cranked time source so retention horizons are deterministic."""

    def __init__(self, t: float) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


def _event(kind: str, *, round_no: int = 0, round_limit: int = 0) -> RunEvent:
    return RunEvent(kind=kind, actor="loop", text="x", state=RunState.GENERATING,
                    round_no=round_no, round_limit=round_limit)


# ------------------------------------------------------------------- D1: runs
def test_retention_prunes_old_terminal_runs_but_keeps_the_live_and_recent(tmp_path):
    """Old finished runs are reclaimed; active/recent/windowed rows survive."""
    now = 1_700_000_000.0
    day = 86_400.0
    clock = _Clock(now)
    journal = RunJournal(tmp_path / "runtime.sqlite3", clock=clock)

    # 30 terminal runs finished 40 days ago: old enough to be eligible.
    clock.t = now - 40 * day
    old_ids: list[str] = []
    for i in range(30):
        rid = journal.start(f"old {i}")
        journal.append(rid, _event("round_started", round_no=1, round_limit=3))
        journal.finish(rid, "passed")
        old_ids.append(rid)

    # 5 terminal runs finished 1 day ago: inside the horizon, always kept. One
    # rests WAITING_FOR_HUMAN — a state an escalation references — proving a
    # recent decision row is never pruned.
    clock.t = now - day
    recent_ids: list[str] = []
    for i in range(5):
        rid = journal.start(f"recent {i}")
        journal.finish(rid, "escalated" if i == 0 else "passed")
        recent_ids.append(rid)

    # One ACTIVE run, deliberately given an OLD started time and left in flight:
    # it is old AND outside the recent window, yet must NEVER be a candidate,
    # because a non-terminal run is what a worker still owns.
    clock.t = now - 40 * day
    active_id = journal.start("still working")
    journal.append(active_id, _event("round_started", round_no=1, round_limit=3))

    clock.t = now
    result = journal.prune_terminal_runs(keep_days=14, keep_recent=10, vacuum=True)

    # The recent-10 window = 5 recent + active + the 4 newest old runs, so 26
    # old runs (older than the horizon AND outside the window) are pruned.
    assert result["runs_deleted"] == 26
    assert result["events_deleted"] == 26 * 3        # started + round + finished
    assert result["kept_recent"] == 10

    # The active run survives untouched, with its events.
    assert journal.state(active_id) == RunState.GENERATING
    assert len(journal.latest()["steps"]) >= 1

    # Every recent terminal run survives (a KeyError would mean it was pruned).
    for rid in recent_ids:
        journal.state(rid)

    # The 4 newest old runs are kept by the recent window; the 26 oldest gone.
    for rid in old_ids[:26]:
        try:
            journal.state(rid)
            raise AssertionError(f"{rid} should have been pruned")
        except KeyError:
            pass
    for rid in old_ids[26:]:
        journal.state(rid)                            # still present

    # Pruned runs take their events with them; the FK is respected.
    with sqlite3.connect(journal.path) as db:
        orphan = db.execute(
            "SELECT COUNT(*) FROM run_events WHERE run_id=?", (old_ids[0],),
        ).fetchone()[0]
        assert orphan == 0
        # The VACUUM/checkpoint left a consistent database.
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    # 36 runs written, 26 removed, 10 remain — nothing referenced was lost.
    assert len(journal.recent(1000)) == 10


def test_retention_is_a_noop_for_a_short_recent_journal(tmp_path):
    """A normal session prunes nothing: public behavior is unchanged."""
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    rid = journal.start("just now")
    journal.finish(rid, "passed")
    result = journal.prune_terminal_runs(keep_days=14, keep_recent=RETAIN_RECENT_RUNS)
    assert result["runs_deleted"] == 0 and result["events_deleted"] == 0
    journal.state(rid)                                # still present


def test_watchdog_retention_is_throttled_and_keeps_the_reconciler_window(tmp_path):
    """The daemon wiring prunes at most hourly and never inside the recon window."""
    daemon._LAST_RETENTION.clear()
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    rid = journal.start("x")
    journal.finish(rid, "passed")

    first = daemon._maybe_prune(journal, now=1000.0)
    assert first is not None
    # The retained window always covers the reconciler's scan window, so a row
    # cross-store reconciliation could reference is never removed.
    assert first["kept_recent"] == max(RETAIN_RECENT_RUNS, daemon.RECONCILE_SCAN_LIMIT)
    assert first["kept_recent"] >= daemon.RECONCILE_SCAN_LIMIT

    # A second sweep inside the interval is throttled to a no-op.
    assert daemon._maybe_prune(journal, now=1000.0 + 5) is None
    # Past the interval it is eligible again.
    later = daemon._maybe_prune(
        journal, now=1000.0 + daemon.RETENTION_SWEEP_INTERVAL_S + 1)
    assert later is not None
    daemon._LAST_RETENTION.clear()


# --------------------------------------------------------------- D1: history
def test_state_history_is_capped_and_old_cycles_keep_a_correct_timestamp(tmp_path):
    """History is bounded on write; a trimmed cycle still renders its own time."""
    store = StateStore(tmp_path / "state.json")

    # Cycle A is opened first and then left alone. Its single history event will
    # be flooded out of the retained tail by cycle B below.
    a = store.open_or_advance("repo/a", "a" * 40, None)
    cid_a = a["cycle_id"]
    a_updated_at = store.snapshot()["cycles"][cid_a]["updated_at"]
    assert a_updated_at > 0

    # Flood the history with far more than HISTORY_LIMIT events, all on cycle B
    # (a re-entered OPEN round logs one resume event without changing state).
    store.open_or_advance("repo/b", "b" * 40, None)
    for _ in range(HISTORY_LIMIT + 100):
        store.open_or_advance("repo/b", "b" * 40, None)

    snap = store.snapshot()
    history = snap["history"]
    # The store is bounded, not unbounded, after a very long session.
    assert len(history) == HISTORY_LIMIT
    # Cycle A's own event has aged out of the retained tail entirely.
    assert not any(h.get("cycle") == cid_a for h in history)
    # But its recorded time is preserved ON THE CYCLE, so it is never lost.
    assert snap["cycles"][cid_a]["updated_at"] == a_updated_at

    # The projection falls back to that recorded time instead of showing 0/blank
    # for a cycle whose events were trimmed.
    rows = _ordered_cycles(snap)
    row_a = next(r for r in rows if r["id"] == cid_a)
    assert row_a["updated"] == a_updated_at


# ------------------------------------------------------------------- D2: steps
def test_progress_steps_are_capped_to_a_recent_tail_but_latest_stays_correct(tmp_path):
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    run_id = journal.start("a very chatty run")
    # An early round marker that will fall outside the retained tail...
    journal.append(run_id, _event("round_started", round_no=1, round_limit=3))
    for i in range(LATEST_STEP_LIMIT + 50):
        journal.append(run_id, _event("activity"))
    # ...and a recent one that must survive so the live view shows round 2.
    journal.append(run_id, _event("round_started", round_no=2, round_limit=3))

    row = journal.latest()
    # The frame carries only the bounded tail, not the whole log.
    assert len(row["steps"]) == LATEST_STEP_LIMIT
    # The latest state is intact: last_event_id is the true max sequence, and
    # the state reflects the newest event.
    total_events = LATEST_STEP_LIMIT + 50 + 3          # +run_started +2 rounds
    assert row["last_event_id"] == total_events
    assert row["state"] == "GENERATING"
    # The most-recent round marker survives the cap (the stale round 1 does not).
    rounds = [s for s in row["steps"] if s["kind"] == "round_started"]
    assert rounds and rounds[-1]["round_no"] == 2
    assert all(s["round_no"] != 1 or s["kind"] != "round_started" for s in row["steps"])


def test_short_runs_still_carry_their_whole_step_log(tmp_path):
    """The cap only bites long runs; a normal run is byte-for-byte unchanged."""
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    run_id = journal.start("short")
    journal.append(run_id, _event("round_started", round_no=1, round_limit=3))
    journal.append(run_id, _event("activity"))
    journal.finish(run_id, "passed")
    steps = journal.latest()["steps"]
    assert [s["kind"] for s in steps] == ["round_started", "activity", "run_finished"]


# ------------------------------------------------------------------ D2: cycles
def test_snapshot_cycles_are_capped_to_the_recent_window():
    """Only the newest cycles ride in a frame; the latest state is preserved."""
    count = CYCLES_WINDOW + 20
    cycles = {f"{i:016x}": {"status": "PASSED", "round": 1,
                            "active_sha": f"sha{i}"} for i in range(count)}
    history = [{"cycle": f"{i:016x}", "event": "open", "t": 100 + i}
               for i in range(count)]

    rows = _ordered_cycles({"cycles": cycles, "history": history})

    # The frame is bounded even though the store holds far more cycles.
    assert len(rows) == CYCLES_WINDOW
    ids = {r["id"] for r in rows}
    # The newest cycle (the live view's subject) is present and last; the
    # oldest have been dropped.
    assert rows[-1]["id"] == f"{count - 1:016x}"
    assert f"{count - 1:016x}" in ids
    assert f"{0:016x}" not in ids
    # The retained rows are exactly the newest CYCLES_WINDOW, in order.
    assert [r["id"] for r in rows] == [f"{i:016x}" for i in
                                       range(count - CYCLES_WINDOW, count)]
