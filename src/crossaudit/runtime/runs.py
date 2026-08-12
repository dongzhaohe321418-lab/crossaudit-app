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

from .processes import IDENTITY_TOKEN_PREFIX, process_identity, zombie

#: A single unconfirmed identity probe must not reclaim a run: ``ps`` can
#: time out transiently. When a comparable token's first probe comes back
#: empty and the row is otherwise reclaimable, recovery waits this long and
#: probes once more before writing an interruption.
_IDENTITY_CONFIRM_DELAY_S = 0.2

DATABASE_NAME = "runtime.sqlite3"

#: Databases from earlier builds report lower numbers; version 2 added the
#: liveness columns (heartbeat_at, lease_expires_at, waiting_reason), version
#: 3 the owner identity token. The number only rises; opening an old file
#: migrates additively and never rewrites rows.
SCHEMA_VERSION = 3

#: A worker renews its lease at every journal write, at every provider-call
#: boundary, and before each resilience retry attempt. A single clean
#: provider turn can still outlive one lease, so lease expiry alone proves
#: nothing about the worker: it only opens the separate stall-narration and
#: unverifiable-owner-reclaim rules below.
LEASE_SECONDS = 120.0

#: Display-only stall narration begins here. The threshold must cover the
#: longest single provider call a shipped adapter can legally make while
#: heartbeating only at its boundaries — codex_subscription's
#: DEFAULT_TIMEOUT_S is 300 s — plus headroom, or a clean first-attempt call
#: would be narrated as a stall (a test pins this against that timeout).
STALL_AFTER_SECONDS = 360.0

#: Recovery authority is the owner's *identity*, never a clock:
#:
#: * an owner whose recorded identity token (pid + process start time) still
#:   matches the living process is NEVER reclaimed — silence is narrated as
#:   a stall, not converted into a fabricated death. This also absorbs wall
#:   clock jumps (laptop sleep, suspend): a time leap cannot kill a
#:   verified worker;
#: * a dead pid, or a live pid whose identity no longer matches (the pid was
#:   recycled by a stranger), is reclaimed immediately — that worker
#:   provably cannot return;
#: * an owner with no verifiable identity (schema-v1 rows, foreign-pid rows,
#:   Windows) is reclaimed once its lease expires: it cannot be proven
#:   alive, and an unverifiable owner must not hold the run slot forever.

#: Resilience-layer failure categories that mean "no configured provider can
#: take the next request". These park a run instead of spending revision
#: rounds: routes_exhausted / circuit_open are infrastructure outages, and
#: "budget" is the local usage guardrail refusing to place the call at all
#: (NORTH_STAR §14 lists the cost ceiling as its own human-decision reason;
#: burning rounds on it would present a spending pause as content failure).
#: Retryable failures inside one provider turn stay inside that turn.
PROVIDER_WAIT_CATEGORIES = frozenset({"routes_exhausted", "circuit_open",
                                      "budget"})


def waiting_kind(category: str) -> str:
    """The machine-readable waiting_reason kind for a park category.

    A guardrail pause is not a provider outage: its remedy is to raise or
    clear the limit (or stop the task), not to review a connection, so it
    carries its own kind for the UI to route on.
    """
    return "budget" if category == "budget" else "provider"


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


def _heartbeat_advanced(seen: float | None, current: float | None) -> bool:
    """Whether the owner recorded a heartbeat after we snapshotted the row.

    Recovery probes the operating system without holding the write lock, so a
    live worker can speak in between. A newer heartbeat is proof of life; the
    reclaim is abandoned rather than racing a healthy run into INTERRUPTED.
    """
    if current is None:
        return False
    if seen is None:
        return True
    return float(current) > float(seen)


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
                    waiting_reason TEXT,
                    owner_token TEXT
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
            added_liveness = "lease_expires_at" not in run_columns
            for name, kind in (("heartbeat_at", "REAL"),
                               ("lease_expires_at", "REAL"),
                               ("waiting_reason", "TEXT"),
                               ("owner_token", "TEXT")):
                if name not in run_columns:
                    # Nullable, defaulting to NULL: rows written by older
                    # builds stay valid and simply carry no liveness claim
                    # (a NULL owner_token means the owner's identity is
                    # unverifiable, which the reclaim rules treat as such).
                    db.execute(f"ALTER TABLE runs ADD COLUMN {name} {kind}")
            if added_liveness:
                # A v1 ACTIVE row would otherwise be invisible to every
                # supervisor: the stall scan skipped NULL leases and recovery
                # trusted the pid, so a living-but-hung legacy owner could hold
                # the single run slot forever with no signal. Backfill the
                # liveness columns at migration time, granting the row one full
                # lease period to prove itself before staleness is narrated.
                now = self._clock()
                active = tuple(state.value for state in ACTIVE_STATES)
                db.execute(
                    "UPDATE runs SET heartbeat_at=?, lease_expires_at=? "
                    "WHERE lease_expires_at IS NULL AND state IN "
                    f"({','.join('?' for _ in active)})",
                    (now, now + LEASE_SECONDS, *active),
                )
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

    @staticmethod
    def _token_refresh(owner_pid: int, stored_token) -> str | None:
        """A current-format identity token to write, or None to leave it be.

        Only the owning process can attest its own identity, so it does so
        lazily. A run started by an older build carries a pre-fix, locale-
        poisoned token that recovery cannot compare; the worker rewrites it to
        the current format at its next heartbeat or transition. The guard
        below skips the probe once the token is already current, so a healthy
        run pays for at most one ``ps`` after an upgrade — and none at all for
        runs this build started, whose token is current from ``start``.
        """
        if owner_pid != os.getpid():
            return None
        if stored_token and str(stored_token).startswith(IDENTITY_TOKEN_PREFIX):
            return None
        return process_identity(os.getpid())

    def start(self, task: str, *, chat_id: str = "",
              continuation_cycle: str = "", owner_pid: int | None = None) -> str:
        now = self._clock()
        run_id = uuid.uuid4().hex
        owner = owner_pid or os.getpid()
        # A process can only attest its own identity: when the caller is the
        # worker (the normal case), record its incarnation token so recovery
        # can later distinguish "this worker still lives" from "a stranger
        # recycled its pid". A foreign owner_pid gets no token — recovery
        # treats that identity as unverifiable rather than vouched for.
        token = process_identity(owner) if owner == os.getpid() else None
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
                "heartbeat_at,lease_expires_at,owner_token) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,NULL,?,?,?)",
                (run_id, task[:12000], chat_id[:64], continuation_cycle[:64],
                 RunState.QUEUED.value, "", "", owner, now, now,
                 now, now + LEASE_SECONDS, token),
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
                "SELECT state,owner_pid,owner_token FROM runs WHERE run_id=?",
                (run_id,),
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
            # not restate one clears the previous one. The write also refreshes
            # a stale identity token so a run migrated from an older build
            # becomes verifiable.
            refreshed = self._token_refresh(int(row["owner_pid"]),
                                            row["owner_token"])
            db.execute(
                "UPDATE runs SET state=?, updated=?, heartbeat_at=?, "
                "lease_expires_at=?, waiting_reason=?, "
                "owner_token=COALESCE(?, owner_token) WHERE run_id=?",
                (target.value, now, now, now + LEASE_SECONDS,
                 json.dumps(event.waiting_reason)
                 if event.waiting_reason is not None else None,
                 refreshed, run_id),
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
                "SELECT state,owner_pid,owner_token FROM runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
            if row is None or _state(row["state"]) not in ACTIVE_STATES:
                db.rollback()
                return False
            # The boundary heartbeat is also where a migrated run refreshes a
            # pre-fix identity token to the comparable format (COALESCE leaves
            # it untouched when the refresh returns None).
            refreshed = self._token_refresh(int(row["owner_pid"]),
                                            row["owner_token"])
            db.execute(
                "UPDATE runs SET heartbeat_at=?, lease_expires_at=?, updated=?, "
                "owner_token=COALESCE(?, owner_token) WHERE run_id=?",
                (now, now + LEASE_SECONDS, now, refreshed, run_id),
            )
            db.commit()
            return True

    def mark_stalled_runs(self, *, alive: Callable[[int], bool],
                          current_pid: int | None = None) -> list[str]:
        """Append one display-only stall note per prolonged worker silence.

        The state deliberately does not change: a silent worker with a living
        owner means a quiet worker, and re-narrating or killing it on a timer
        would be the watchdog inventing failures. The note lets the UI say how
        long the run has been silent; dead owners remain the business of
        ``recover_abandoned``. Repeating the scan is a no-op until the worker
        speaks again, so the sweep itself is idempotent.

        The stall threshold is deliberately looser than the lease itself
        (``STALL_AFTER_SECONDS``, two lease periods since the last heartbeat):
        a single healthy provider turn heartbeats only at its call boundaries
        and can outlive one lease, and narrating that as a stall would be the
        watchdog describing a slow model as a hung worker. An ACTIVE row with
        no lease at all makes no liveness claim and is treated as expired.
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
                # lease == heartbeat + LEASE_SECONDS at write time, so this is
                # STALL_AFTER_SECONDS of silence since the last heartbeat.
                if lease is not None and now < float(lease) + (
                        STALL_AFTER_SECONDS - LEASE_SECONDS):
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
        """Record one idempotent cancellation request for an active or parked run.

        An active run moves to CANCELLING for its worker to observe. A parked
        run (PROVIDER_UNAVAILABLE) has no worker left to observe anything, so
        the transition table's declared PROVIDER_UNAVAILABLE -> CANCELLED edge
        is taken directly here — otherwise "Stop this task" would have no real
        command surface and the edge would be dead code.
        """
        now = self._clock()
        active = tuple(state.value for state in ACTIVE_STATES)
        parked = tuple(state.value for state in PARKED_STATES)
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
                    row = db.execute(
                        "SELECT run_id,state FROM runs WHERE state IN "
                        f"({','.join('?' for _ in parked)}) "
                        "ORDER BY started DESC LIMIT 1", parked,
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
            if current in PARKED_STATES and _can_move(
                    current, RunState.CANCELLED):
                self._insert_event(
                    db, selected, kind="run_cancelled", actor="user",
                    text="cancelled",
                    detail="stopped by user while parked for a provider",
                    state=RunState.CANCELLED, at=now,
                )
                db.execute(
                    "UPDATE runs SET state=?, outcome=?, updated=?, finished=?, "
                    "lease_expires_at=NULL WHERE run_id=?",
                    (RunState.CANCELLED.value, "cancelled", now, now, selected),
                )
                db.commit()
                return {"run_id": selected, "state": RunState.CANCELLED.value,
                        "requested": True}
            if current not in ACTIVE_STATES or not _can_move(
                    current, RunState.CANCELLING):
                db.rollback()
                raise RuntimeError("that run can no longer be cancelled")
            self._insert_event(
                db, selected, kind="cancel_requested", actor="user",
                text="cancelling", detail="", state=RunState.CANCELLING,
                at=now,
            )
            # The lease is set alongside the request so CANCELLING is
            # supervisable: if the worker never acknowledges because it is
            # gone (dead pid, recycled pid, or an unverifiable owner past
            # its lease), the watchdog completes the cancellation instead
            # of absorbing it forever. A verified-alive worker keeps owning
            # the acknowledgement itself.
            db.execute(
                "UPDATE runs SET state=?, updated=?, lease_expires_at=? "
                "WHERE run_id=?",
                (RunState.CANCELLING.value, now, now + LEASE_SECONDS, selected),
            )
            db.commit()
        return {"run_id": selected, "state": RunState.CANCELLING.value,
                "requested": True}

    def recover_abandoned(self, *, current_pid: int | None = None,
                          alive: Callable[[int], bool],
                          identity: Callable[[int], str | None] =
                          process_identity,
                          is_zombie: Callable[[int], bool] = zombie,
                          sleep: Callable[[float], None] = time.sleep
                          ) -> list[str]:
        """Resolve abandoned active runs exactly once.

        A durable cancellation request remains authoritative if the worker dies
        before observing it. Other active work becomes an explicit interruption.

        Recovery authority is the owner's *identity*, never a clock:

        * a live pid whose recorded identity token still matches is NEVER
          reclaimed — a provably-living owner's silence is narrated by the
          stall notes, not converted into a fabricated death. A laptop that
          slept for an hour mid provider call, or a foreground build under
          SIGSTOP, resumes into an intact journal, and a wall clock jump
          cannot kill a verified worker;
        * a dead pid, a reaped-later zombie, or a live pid whose token no
          longer matches (the pid was recycled by a stranger) is reclaimed —
          that worker provably cannot return. A recycle is proven by two
          *comparable* tokens disagreeing, so it never fires on a token from
          an older format;
        * an owner with no verifiable identity — no token, a pre-fix
          (locale-poisoned) token, or a probe that will not answer — is
          reclaimed only once its lease has expired: it cannot be proven
          alive, but neither may it be declared dead, so it gets one lease
          period of grace during which a live owner refreshes its token.

        The identity marker is read from the operating system, so this walks
        two phases: it snapshots the rows, then probes and (if needed) waits
        WITHOUT holding the write lock, and only then applies the reclaims —
        re-reading each row so a worker that heartbeat while we probed is left
        alone. Only this process's own runs are exempt. The interruption
        detail states only what is known — never "the process ended" when the
        owner merely could not be verified.
        """
        self_pid = current_pid or os.getpid()
        active = tuple(state.value for state in ACTIVE_STATES)
        placeholders = ",".join("?" for _ in active)
        now = self._clock()

        # Phase 1 — snapshot. No write lock is held across the OS probes below,
        # so a slow ``ps`` or the confirmation wait cannot block a live worker.
        with self._connect() as db:
            rows = db.execute(
                f"SELECT run_id,owner_pid,state,heartbeat_at,lease_expires_at,"
                f"owner_token FROM runs WHERE state IN ({placeholders})",
                active,
            ).fetchall()

        def why_reclaim(owner: int, token, lease, beat) -> str | None:
            silence = (f"no heartbeat for {max(0, int(now - float(beat)))}s"
                       if beat is not None else "no heartbeat was ever recorded")
            if not alive(owner):
                return "the worker process ended before completion"
            if is_zombie(owner):
                return (f"{silence}; the worker process ended and its pid is "
                        f"now a zombie")
            token_str = str(token) if token else ""
            lease_live = lease is not None and now < float(lease)
            if token_str.startswith(IDENTITY_TOKEN_PREFIX):
                seen = identity(owner)
                if seen == token_str:
                    return None                    # verified alive
                if seen is not None:
                    return (f"{silence}; the owner pid was recycled by another "
                            f"process — the worker is gone")
                # A comparable token whose probe came back empty: one transient
                # ``ps`` timeout must not reclaim a healthy worker. Confirm.
                sleep(_IDENTITY_CONFIRM_DELAY_S)
                if identity(owner) == token_str:
                    return None
                if lease_live:
                    return None
                return (f"{silence}; the owner process could not be verified as "
                        f"this run's worker")
            # No token, or a pre-fix (locale-poisoned) token that is not
            # comparable: unverifiable. The lease is its only claim.
            if lease_live:
                return None
            return (f"{silence}; the owner process could not be verified as "
                    f"this run's worker")

        # Phase 2 — classify, holding no lock.
        pending: list[tuple[str, str, float | None]] = []
        for row in rows:
            owner = int(row["owner_pid"])
            if owner == self_pid:
                continue
            why = why_reclaim(owner, row["owner_token"],
                              row["lease_expires_at"], row["heartbeat_at"])
            if why is not None:
                pending.append((str(row["run_id"]), why, row["heartbeat_at"]))
        if not pending:
            return []

        # Phase 3 — apply. Re-read each row so a worker that spoke while we
        # probed (a newer heartbeat, or an already-resolved state) survives,
        # and serialize the write so concurrent sweeps recover exactly once.
        recovered: list[str] = []
        now = self._clock()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for run_id, why, beat_seen in pending:
                cur = db.execute(
                    "SELECT state,heartbeat_at FROM runs WHERE run_id=?",
                    (run_id,),
                ).fetchone()
                if cur is None or _state(cur["state"]) not in ACTIVE_STATES:
                    continue
                if _heartbeat_advanced(beat_seen, cur["heartbeat_at"]):
                    continue                       # the worker spoke: alive
                cancelling = _state(cur["state"]) == RunState.CANCELLING
                target = RunState.CANCELLED if cancelling else RunState.INTERRUPTED
                outcome = "cancelled" if cancelling else "interrupted"
                kind = "run_cancelled" if cancelling else "run_interrupted"
                text = "cancelled" if cancelling else "interrupted"
                detail = (f"cancellation was requested and {why}" if cancelling
                          else why)
                self._insert_event(
                    db, run_id, kind=kind, actor="controller", text=text,
                    detail=detail, state=target, at=now,
                )
                # A resting state holds no lease: the watchdog must never read
                # a recovered row as a worker that went quiet.
                db.execute(
                    "UPDATE runs SET state=?, outcome=?, error=?, updated=?, "
                    "finished=?, lease_expires_at=NULL WHERE run_id=?",
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
            # Resting states hold no lease (same invariant as finish()).
            db.execute(
                "UPDATE runs SET state=?, outcome=?, updated=?, finished=?, "
                "lease_expires_at=NULL WHERE run_id=?",
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
            # Resting states hold no lease (same invariant as finish()).
            db.execute(
                "UPDATE runs SET state=?, outcome=?, error=?, updated=?, "
                "finished=?, lease_expires_at=NULL WHERE run_id=?",
                (RunState.WAITING_FOR_HUMAN.value, "escalated",
                 reason[:2000], now, now, run_id),
            )
            db.commit()
            return True

    def recent(self, limit: int = 20) -> list[dict]:
        """The newest run rows, newest first, without their event streams.

        Reconciliation must be able to see past the single newest run: a torn
        needs-a-human write is not healed by the retry that raced ahead of the
        sweep, and only a bounded scan can find the older torn half.
        """
        with self._connect() as db:
            rows = db.execute(
                "SELECT run_id,state,outcome,error,task,chat_id,started "
                "FROM runs ORDER BY started DESC, rowid DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
        return [{"run_id": str(row["run_id"]), "state": str(row["state"]),
                 "outcome": str(row["outcome"]), "error": str(row["error"]),
                 "task": str(row["task"]), "chat_id": str(row["chat_id"]),
                 "started": float(row["started"])} for row in rows]

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
