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

import os
import sqlite3
import time
import uuid
from collections.abc import Callable
from enum import Enum
from pathlib import Path

DATABASE_NAME = "runtime.sqlite3"


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
        RunState.WAITING_FOR_HUMAN, RunState.CANCELLING,
        RunState.CANCELLED, RunState.FAILED, RunState.INTERRUPTED,
    }),
    RunState.REVISING: frozenset({
        RunState.GENERATING, RunState.WAITING_FOR_CAPABILITY, RunState.PASSED,
        RunState.WAITING_FOR_PROVIDER, RunState.WAITING_FOR_HUMAN,
        RunState.CANCELLING, RunState.CANCELLED, RunState.FAILED,
        RunState.INTERRUPTED,
    }),
    RunState.CANCELLING: frozenset({
        RunState.CANCELLED, RunState.FAILED, RunState.INTERRUPTED,
    }),
    RunState.WAITING_FOR_PROVIDER: frozenset({RunState.CANCELLED}),
    RunState.WAITING_FOR_HUMAN: frozenset({RunState.CANCELLED}),
    RunState.INTERRUPTED: frozenset({RunState.CANCELLED}),
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

    def __init__(self, path: Path) -> None:
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
                    finished REAL
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
        now = time.time()
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
                "outcome,error,owner_pid,started,updated,finished) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,NULL)",
                (run_id, task[:12000], chat_id[:64], continuation_cycle[:64],
                 RunState.QUEUED.value, "", "", owner_pid or os.getpid(), now, now),
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
        now = time.time()
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
            db.execute(
                "UPDATE runs SET state=?, updated=? WHERE run_id=?",
                (target.value, now, run_id),
            )
            db.commit()
            return sequence

    def finish(self, run_id: str, outcome: str, error: str = "") -> None:
        targets = {
            "passed": RunState.PASSED,
            "escalated": RunState.WAITING_FOR_HUMAN,
            "blocked": RunState.WAITING_FOR_HUMAN,
            "provider_wait": RunState.WAITING_FOR_PROVIDER,
            "refused": RunState.WAITING_FOR_HUMAN,
            "cancelled": RunState.CANCELLED,
            "failed": RunState.FAILED,
        }
        target = targets.get(outcome, RunState.FAILED)
        now = time.time()
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
            db.execute(
                "UPDATE runs SET state=?, outcome=?, error=?, updated=?, finished=? "
                "WHERE run_id=?",
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
        now = time.time()
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
        now = time.time()
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
        now = time.time()
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
        end = float(row["finished"] or time.time())
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
            "finished": state in TERMINAL_STATES,
            "outcome": row["outcome"],
            "error": row["error"],
            "elapsed": max(0, round(end - float(row["started"]))),
            "last_event_id": int(events[-1]["sequence"]) if events else 0,
        }

    def interruption(self) -> dict | None:
        row = self.latest()
        return (row if row and row["state"] in {
            RunState.INTERRUPTED.value, RunState.FAILED.value} else None)
