"""Canonical, durable state for one project's agent runs.

Git commits and receipts are immutable audit evidence.  They are deliberately
not asked to double as a live process database.  This journal records only
operational facts (started, visible phase, completion or interruption) in a
small SQLite WAL database so a process restart cannot erase what the UI needs
to recover safely.

The transition table is the authority.  Callers may narrate a run in different
ways, but they may not invent another lifecycle.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from collections.abc import Callable
from enum import Enum
from pathlib import Path

DATABASE_NAME = "runtime.sqlite3"

#: Databases from earlier builds report 0; version 2 added the liveness
#: columns (heartbeat_at, lease_expires_at, waiting_reason). The number only
#: rises; opening an old file migrates additively and never rewrites rows.
SCHEMA_VERSION = 2

#: A worker renews its lease at every journal write and at every provider-call
#: boundary. 120 s is several multiples of the normal gap between those
#: writes, so an expired lease means a silent worker, not merely a busy one.
#: The lease is display authority only: an expired lease with a living owner
#: is narrated as staleness ("last heartbeat Ns ago"), never auto-killed, so a
#: slow provider turn is at worst described as quiet rather than destroyed.
LEASE_SECONDS = 120.0

#: Resilience-layer failure categories that mean "no configured provider can
#: take the next request". Only these park a run as PROVIDER_UNAVAILABLE;
#: retryable failures inside one provider turn stay inside that turn.
PROVIDER_WAIT_CATEGORIES = frozenset({"routes_exhausted", "circuit_open"})


def journal_path(cfg) -> Path:
    """The operational database for a project Config-like object."""
    return Path(cfg.root) / str(cfg.state_dir) / DATABASE_NAME


class RunState(str, Enum):
    QUEUED = "QUEUED"
    GENERATING = "GENERATING"
    WAITING_FOR_CAPABILITY = "WAITING_FOR_CAPABILITY"
    AUDITING = "AUDITING"
    REVISING = "REVISING"
    WAITING_FOR_PROVIDER = "WAITING_FOR_PROVIDER"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PASSED = "PASSED"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"


ACTIVE_STATES = frozenset({
    RunState.QUEUED,
    RunState.GENERATING,
    RunState.WAITING_FOR_CAPABILITY,
    RunState.AUDITING,
    RunState.REVISING,
    RunState.CANCELLING,
})
TERMINAL_STATES = frozenset({
    RunState.WAITING_FOR_PROVIDER,
    RunState.WAITING_FOR_HUMAN,
    RunState.PASSED,
    RunState.CANCELLED,
    RunState.FAILED,
    RunState.INTERRUPTED,
})
#: Parked for a human remedy: no worker owns the run, so the projection
#: reports it as finished, but the transition table still permits an explicit
#: resume — unlike the truly terminal states, which absorb.
PARKED_STATES = frozenset({RunState.PROVIDER_UNAVAILABLE})

_TRANSITIONS: dict[RunState, frozenset[RunState]] = {
    RunState.QUEUED: frozenset({
        RunState.GENERATING, RunState.PASSED, RunState.CANCELLING,
        RunState.CANCELLED, RunState.FAILED,
        RunState.INTERRUPTED, RunState.WAITING_FOR_PROVIDER,
        RunState.WAITING_FOR_HUMAN,
    }),
    RunState.GENERATING: frozenset({
        RunState.WAITING_FOR_CAPABILITY, RunState.AUDITING,
        RunState.PASSED,
        RunState.WAITING_FOR_PROVIDER, RunState.WAITING_FOR_HUMAN,
        RunState.PROVIDER_UNAVAILABLE,
        RunState.CANCELLING, RunState.CANCELLED, RunState.FAILED,
        RunState.INTERRUPTED,
    }),
    RunState.WAITING_FOR_CAPABILITY: frozenset({
        RunState.GENERATING, RunState.PASSED, RunState.WAITING_FOR_PROVIDER,
        RunState.WAITING_FOR_HUMAN, RunState.CANCELLING,
        RunState.CANCELLED, RunState.FAILED, RunState.INTERRUPTED,
    }),
    RunState.AUDITING: frozenset({
        RunState.REVISING, RunState.PASSED, RunState.WAITING_FOR_PROVIDER,
        RunState.WAITING_FOR_HUMAN, RunState.PROVIDER_UNAVAILABLE,
        RunState.CANCELLING,
        RunState.CANCELLED, RunState.FAILED, RunState.INTERRUPTED,
    }),
    RunState.REVISING: frozenset({
        RunState.GENERATING, RunState.WAITING_FOR_CAPABILITY, RunState.PASSED,
        RunState.WAITING_FOR_PROVIDER, RunState.WAITING_FOR_HUMAN,
        RunState.PROVIDER_UNAVAILABLE,
        RunState.CANCELLING, RunState.CANCELLED, RunState.FAILED,
        RunState.INTERRUPTED,
    }),
    RunState.CANCELLING: frozenset({
        RunState.CANCELLED, RunState.FAILED, RunState.INTERRUPTED,
    }),
    # A human remedy may resume the phase that was starved (retry), stop the
    # run, or record a hard failure. It never silently self-heals: every out
    # edge is taken by an explicit command, not a timer.
    RunState.PROVIDER_UNAVAILABLE: frozenset({
        RunState.GENERATING, RunState.AUDITING, RunState.REVISING,
        RunState.CANCELLING, RunState.CANCELLED, RunState.FAILED,
    }),
    RunState.WAITING_FOR_PROVIDER: frozenset({RunState.CANCELLED}),
    RunState.WAITING_FOR_HUMAN: frozenset({RunState.CANCELLED}),
    # WAITING_FOR_HUMAN is reachable from INTERRUPTED only by recovery
    # re-narration: the worker died after the cycle store already recorded the
    # escalation, so the truthful resting state is "needs a person".
    RunState.INTERRUPTED: frozenset({
        RunState.CANCELLED, RunState.WAITING_FOR_HUMAN,
    }),
    RunState.PASSED: frozenset(),
    RunState.CANCELLED: frozenset(),
    RunState.FAILED: frozenset({RunState.CANCELLED}),
}


def _state(value: str | RunState) -> RunState:
    return value if isinstance(value, RunState) else RunState(value)


def _can_move(current: RunState, target: RunState) -> bool:
    return current == target or target in _TRANSITIONS[current]


class RunJournal:
    """SQLite-backed event journal and current-state projection.

    Connections are short-lived so worker and HTTP threads never share a
    sqlite connection.  `BEGIN IMMEDIATE` serializes mutations at the database
    boundary instead of relying on a process-local lock.
    """

    def __init__(self, path: Path, *,
                 clock: Callable[[], float] = time.time) -> None:
        # One injectable time source: liveness (heartbeats, leases) must be
        # testable without waiting out real minutes, and must not disagree
        # with the timestamps written next to it.
        self._clock = clock
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA synchronous=FULL;
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    task TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    continuation_cycle TEXT NOT NULL,
                    state TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    error TEXT NOT NULL,
                    owner_pid INTEGER NOT NULL,
                    started REAL NOT NULL,
                    updated REAL NOT NULL,
                    finished REAL,
                    heartbeat_at REAL,
                    lease_expires_at REAL,
                    waiting_reason TEXT
                );
                CREATE INDEX IF NOT EXISTS runs_started ON runs(started DESC);
                CREATE TABLE IF NOT EXISTS run_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL REFERENCES runs(run_id),
                    t REAL NOT NULL,
                    kind TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    text TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    state TEXT NOT NULL,
                    round_no INTEGER NOT NULL DEFAULT 0,
                    round_limit INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS run_events_run
                    ON run_events(run_id, sequence);
                """
            )
            # Additive migration for runtime databases created by earlier
            # builds. This is operational UI state; immutable audit evidence is
            # stored separately in Git and receipts.
            columns = {row[1] for row in db.execute("PRAGMA table_info(run_events)")}
            if "round_no" not in columns:
                db.execute(
                    "ALTER TABLE run_events ADD COLUMN round_no INTEGER "
                    "NOT NULL DEFAULT 0")
            if "round_limit" not in columns:
                db.execute(
                    "ALTER TABLE run_events ADD COLUMN round_limit INTEGER "
                    "NOT NULL DEFAULT 0")
            run_columns = {row[1] for row in db.execute("PRAGMA table_info(runs)")}
            for name, kind in (("heartbeat_at", "REAL"),
                               ("lease_expires_at", "REAL"),
                               ("waiting_reason", "TEXT")):
                if name not in run_columns:
                    # Nullable, defaulting to NULL: rows written by older
                    # builds stay valid and simply carry no liveness claim.
                    db.execute(f"ALTER TABLE runs ADD COLUMN {name} {kind}")
            db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")
        return db

    @staticmethod
    def _insert_event(db: sqlite3.Connection, run_id: str, *, kind: str,
                      actor: str, text: str, detail: str, state: RunState,
                      at: float, round_no: int = 0,
                      round_limit: int = 0) -> int:
        cursor = db.execute(
            "INSERT INTO run_events(run_id,t,kind,actor,text,detail,state,"
            "round_no,round_limit) VALUES(?,?,?,?,?,?,?,?,?)",
            (run_id, at, kind[:40], actor[:40], text[:400], detail[:2000],
             state.value, round_no, round_limit),
        )
        return int(cursor.lastrowid)

    def start(self, task: str, *, chat_id: str = "",
              continuation_cycle: str = "", owner_pid: int | None = None) -> str:
        now = self._clock()
        run_id = uuid.uuid4().hex
        active = tuple(state.value for state in ACTIVE_STATES)
        placeholders = ",".join("?" for _ in active)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                f"SELECT run_id FROM runs WHERE state IN ({placeholders}) LIMIT 1",
                active,
            ).fetchone()
            if existing is not None:
                db.rollback()
                raise RuntimeError("a build is already running in this project")
            db.execute(
                "INSERT INTO runs(run_id,task,chat_id,continuation_cycle,state,"
                "outcome,error,owner_pid,started,updated,finished,"
                "heartbeat_at,lease_expires_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,NULL,?,?)",
                (run_id, task[:12000], chat_id[:64], continuation_cycle[:64],
                 RunState.QUEUED.value, "", "", owner_pid or os.getpid(), now, now,
                 now, now + LEASE_SECONDS),
            )
            self._insert_event(
                db, run_id, kind="run_started", actor="controller", text="queued",
                detail="", state=RunState.QUEUED, at=now,
            )
            db.commit()
        return run_id

    def append(self, run_id: str, event) -> int:
        """Persist one typed RunEvent and apply its declared transition."""
        # Local import keeps the state definition independent of its event
        # facade while rejecting legacy narration dictionaries at this seam.
        from .events import RunEvent

        if not isinstance(event, RunEvent):
            raise TypeError("RunJournal.append requires a RunEvent")
        now = self._clock()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT state FROM runs WHERE run_id=?", (run_id,),
            ).fetchone()
            if row is None:
                db.rollback()
                raise KeyError(f"unknown run {run_id}")
            current = _state(row["state"])
            target = event.state
            if current in TERMINAL_STATES:
                db.rollback()
                if target != current:
                    raise RuntimeError(
                        f"invalid run transition {current.value} -> {target.value}")
                return 0
            if not _can_move(current, target):
                db.rollback()
                raise RuntimeError(
                    f"invalid run transition {current.value} -> {target.value}")
            sequence = self._insert_event(
                db, run_id, kind=event.kind, actor=event.actor, text=event.text,
                detail=event.detail, state=target, at=now,
                round_no=event.round_no, round_limit=event.round_limit,
            )
            # Every worker write is also a heartbeat and a lease renewal, so a
            # run can only look stale when nothing has actually been recorded.
            # The waiting reason follows the event: any transition that does
            # not restate one clears the previous one.
            db.execute(
                "UPDATE runs SET state=?, updated=?, heartbeat_at=?, "
                "lease_expires_at=?, waiting_reason=? WHERE run_id=?",
                (target.value, now, now, now + LEASE_SECONDS,
                 json.dumps(event.waiting_reason)
                 if event.waiting_reason is not None else None, run_id),
            )
            db.commit()
            return sequence

    def heartbeat(self, run_id: str) -> bool:
        """Renew the worker lease without adding a narration event.

        Called at provider-call boundaries, where minutes can pass with
        nothing new to say. Without this, a long clean provider turn would be
        indistinguishable from a hung worker.
        """
        now = self._clock()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT state FROM runs WHERE run_id=?", (run_id,),
            ).fetchone()
            if row is None or _state(row["state"]) not in ACTIVE_STATES:
                db.rollback()
                return False
            db.execute(
                "UPDATE runs SET heartbeat_at=?, lease_expires_at=?, updated=? "
                "WHERE run_id=?",
                (now, now + LEASE_SECONDS, now, run_id),
            )
            db.commit()
            return True

    def mark_stalled_runs(self, *, alive: Callable[[int], bool],
                          current_pid: int | None = None) -> list[str]:
        """Append one display-only stall note per silent lease expiry.

        The state deliberately does not change: an expired lease with a living
        owner means a quiet worker, and re-narrating or killing it on a timer
        would be the watchdog inventing failures. The note lets the UI say how
        long the run has been silent; dead owners remain the business of
        ``recover_abandoned``. Repeating the scan is a no-op until the worker
        speaks again, so the sweep itself is idempotent.
        """
        noted: list[str] = []
        now = self._clock()
        active = tuple(state.value for state in ACTIVE_STATES)
        placeholders = ",".join("?" for _ in active)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                f"SELECT run_id,owner_pid,state,heartbeat_at,lease_expires_at "
                f"FROM runs WHERE state IN ({placeholders})", active,
            ).fetchall()
            for row in rows:
                lease = row["lease_expires_at"]
                if lease is None or float(lease) > now:
                    continue
                owner = int(row["owner_pid"])
                if owner != (current_pid or os.getpid()) and not alive(owner):
                    continue          # a dead owner is recover_abandoned's case
                run_id = str(row["run_id"])
                last = db.execute(
                    "SELECT kind FROM run_events WHERE run_id=? "
                    "ORDER BY sequence DESC LIMIT 1", (run_id,),
                ).fetchone()
                if last is not None and str(last["kind"]) == "run_stalled":
                    continue
                beat = row["heartbeat_at"]
                detail = (f"no heartbeat for {max(0, int(now - float(beat)))}s"
                          if beat is not None else
                          "no heartbeat was ever recorded for this run")
                self._insert_event(
                    db, run_id, kind="run_stalled", actor="watchdog",
                    text="stalled", detail=detail, state=_state(row["state"]),
                    at=now,
                )
                noted.append(run_id)
            db.commit()
        return noted

    def finish(self, run_id: str, outcome: str, error: str = "") -> None:
        targets = {
            "passed": RunState.PASSED,
            "escalated": RunState.WAITING_FOR_HUMAN,
            "blocked": RunState.WAITING_FOR_HUMAN,
            "provider_wait": RunState.WAITING_FOR_PROVIDER,
            # A parked run is already in PROVIDER_UNAVAILABLE; this records
            # its outcome without narrating a second, different stop over it.
            "provider_unavailable": RunState.PROVIDER_UNAVAILABLE,
            "refused": RunState.WAITING_FOR_HUMAN,
            "cancelled": RunState.CANCELLED,
            "failed": RunState.FAILED,
        }
        target = targets.get(outcome, RunState.FAILED)
        now = self._clock()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT state FROM runs WHERE run_id=?", (run_id,),
            ).fetchone()
            if row is None:
                db.rollback()
                raise KeyError(f"unknown run {run_id}")
            current = _state(row["state"])
            if current in TERMINAL_STATES:
                db.rollback()
                return
            if not _can_move(current, target):
                db.rollback()
                raise RuntimeError(
                    f"invalid run transition {current.value} -> {target.value}")
            self._insert_event(
                db, run_id, kind="run_finished", actor="done", text=outcome,
                detail=error, state=target, at=now,
            )
            # A finished or parked run holds no lease: the watchdog must never
            # read a resting state as a worker that went quiet.
            db.execute(
                "UPDATE runs SET state=?, outcome=?, error=?, updated=?, "
                "finished=?, lease_expires_at=NULL WHERE run_id=?",
                (target.value, outcome[:40], error[:2000], now, now, run_id),
            )
            db.commit()

    def state(self, run_id: str) -> RunState:
        with self._connect() as db:
            row = db.execute(
                "SELECT state FROM runs WHERE run_id=?", (run_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown run {run_id}")
        return _state(row["state"])

    def request_cancel(self, run_id: str | None = None) -> dict:
        """Record one idempotent cancellation request for an active run."""
        now = self._clock()
        active = tuple(state.value for state in ACTIVE_STATES)
        placeholders = ",".join("?" for _ in active)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if run_id:
                row = db.execute(
                    "SELECT run_id,state FROM runs WHERE run_id=?", (run_id,),
                ).fetchone()
            else:
                row = db.execute(
                    f"SELECT run_id,state FROM runs WHERE state IN ({placeholders}) "
                    "ORDER BY started DESC LIMIT 1", active,
                ).fetchone()
            if row is None:
                db.rollback()
                raise RuntimeError("there is no active run to cancel")
            selected = str(row["run_id"])
            current = _state(row["state"])
            if current == RunState.CANCELLING:
                db.rollback()
                return {"run_id": selected, "state": current.value,
                        "requested": False}
            if current not in ACTIVE_STATES or not _can_move(
                    current, RunState.CANCELLING):
                db.rollback()
                raise RuntimeError("that run can no longer be cancelled")
            self._insert_event(
                db, selected, kind="cancel_requested", actor="user",
                text="cancelling", detail="", state=RunState.CANCELLING,
                at=now,
            )
            db.execute(
                "UPDATE runs SET state=?, updated=? WHERE run_id=?",
                (RunState.CANCELLING.value, now, selected),
            )
            db.commit()
        return {"run_id": selected, "state": RunState.CANCELLING.value,
                "requested": True}

    def recover_abandoned(self, *, current_pid: int | None = None,
                          alive: Callable[[int], bool]) -> list[str]:
        """Resolve active runs owned by dead processes exactly once.

        A durable cancellation request remains authoritative if the worker dies
        before observing it. Other active work becomes an explicit interruption.
        """
        recovered: list[str] = []
        active = tuple(state.value for state in ACTIVE_STATES)
        placeholders = ",".join("?" for _ in active)
        now = self._clock()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                f"SELECT run_id,owner_pid,state FROM runs "
                f"WHERE state IN ({placeholders})",
                active,
            ).fetchall()
            for row in rows:
                owner = int(row["owner_pid"])
                if owner == (current_pid or os.getpid()) or alive(owner):
                    continue
                run_id = str(row["run_id"])
                cancelling = _state(row["state"]) == RunState.CANCELLING
                target = RunState.CANCELLED if cancelling else RunState.INTERRUPTED
                outcome = "cancelled" if cancelling else "interrupted"
                kind = "run_cancelled" if cancelling else "run_interrupted"
                text = "cancelled" if cancelling else "interrupted"
                detail = ("worker ended after cancellation was requested" if cancelling
                          else "worker process ended before completion")
                self._insert_event(
                    db, run_id, kind=kind, actor="controller", text=text,
                    detail=detail, state=target, at=now,
                )
                db.execute(
                    "UPDATE runs SET state=?, outcome=?, error=?, updated=?, finished=? "
                    "WHERE run_id=?",
                    (target.value, outcome, "" if cancelling else detail,
                     now, now, run_id),
                )
                recovered.append(run_id)
            db.commit()
        return recovered

    def dismiss_interruption(self, run_id: str | None = None) -> bool:
        now = self._clock()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if run_id:
                row = db.execute(
                    "SELECT run_id,state FROM runs WHERE run_id=?", (run_id,),
                ).fetchone()
            else:
                row = db.execute(
                    "SELECT run_id,state FROM runs ORDER BY started DESC LIMIT 1",
                ).fetchone()
            if (row is None or
                    _state(row["state"]) not in {RunState.INTERRUPTED, RunState.FAILED}):
                db.rollback()
                return False
            selected = str(row["run_id"])
            self._insert_event(
                db, selected, kind="interruption_dismissed", actor="user",
                text="dismissed", detail="", state=RunState.CANCELLED, at=now,
            )
            db.execute(
                "UPDATE runs SET state=?, outcome=?, updated=?, finished=? WHERE run_id=?",
                (RunState.CANCELLED.value, "cancelled", now, now, selected),
            )
            db.commit()
            return True

    def complete_human_wait(self, run_id: str, reason: str = "") -> bool:
        """Re-narrate a recovered interruption whose escalation already exists.

        The needs-a-human write is two stores wide: the cycle store records
        the escalation first, the run journal second.  A death in between
        leaves an ESCALATED cycle beside an INTERRUPTED run — a decision the
        UI would present as a crash.  This completes the second half exactly
        once; any other state is left alone.
        """
        now = self._clock()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT state FROM runs WHERE run_id=?", (run_id,),
            ).fetchone()
            if row is None or _state(row["state"]) != RunState.INTERRUPTED:
                db.rollback()
                return False
            if not _can_move(RunState.INTERRUPTED, RunState.WAITING_FOR_HUMAN):
                db.rollback()
                return False
            self._insert_event(
                db, run_id, kind="human_wait_reconciled", actor="controller",
                text="escalated",
                detail=reason or ("the escalation was recorded before the "
                                  "worker ended; this run is waiting for a "
                                  "person, not crashed"),
                state=RunState.WAITING_FOR_HUMAN, at=now,
            )
            db.execute(
                "UPDATE runs SET state=?, outcome=?, error=?, updated=?, "
                "finished=? WHERE run_id=?",
                (RunState.WAITING_FOR_HUMAN.value, "escalated",
                 reason[:2000], now, now, run_id),
            )
            db.commit()
            return True

    def latest(self) -> dict | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM runs ORDER BY started DESC, rowid DESC LIMIT 1",
            ).fetchone()
            if row is None:
                return None
            events = db.execute(
                "SELECT * FROM run_events WHERE run_id=? ORDER BY sequence",
                (row["run_id"],),
            ).fetchall()
        steps = [
            {"t": event["t"], "actor": event["actor"], "text": event["text"],
             "detail": event["detail"], "event_id": event["sequence"],
             "state": event["state"], "kind": event["kind"],
             "round_no": int(event["round_no"]),
             "round_limit": int(event["round_limit"])}
            for event in events if event["kind"] != "run_started"
        ]
        state = _state(row["state"])
        end = float(row["finished"] or self._clock())
        try:
            waiting = (json.loads(row["waiting_reason"])
                       if row["waiting_reason"] else None)
        except (TypeError, ValueError):
            waiting = None
        return {
            "run_id": row["run_id"],
            "task": row["task"],
            "chat_id": row["chat_id"],
            "continuation_cycle": row["continuation_cycle"],
            "state": state.value,
            "started": float(row["started"]),
            "updated": float(row["updated"]),
            "owner_pid": int(row["owner_pid"]),
            "steps": steps,
            # A parked run is finished from the worker's point of view: no
            # thread owns it, and only an explicit human command resumes it.
            "finished": state in TERMINAL_STATES or state in PARKED_STATES,
            "outcome": row["outcome"],
            "error": row["error"],
            "elapsed": max(0, round(end - float(row["started"]))),
            "last_event_id": int(events[-1]["sequence"]) if events else 0,
            "heartbeat_at": (float(row["heartbeat_at"])
                             if row["heartbeat_at"] is not None else None),
            "lease_expires_at": (float(row["lease_expires_at"])
                                 if row["lease_expires_at"] is not None else None),
            "waiting_reason": waiting if isinstance(waiting, dict) else None,
        }

    def interruption(self) -> dict | None:
        row = self.latest()
        return (row if row and row["state"] in {
            RunState.INTERRUPTED.value, RunState.FAILED.value} else None)
