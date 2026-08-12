"""The single command path for starting and controlling an agent run.

The CLI and local UI used to share the inner ``run_loop`` but duplicated the
operational shell around it: workspace leasing, journal creation, event
delivery, exception classification and terminal-state recording.  That was
two lifecycle implementations even though both eventually called the same
model loop.

``RunCommandService`` owns that shell.  It stores no authoritative state in
memory: the SQLite journal is the command boundary and the read model.  A
background thread is only an executor; killing it leaves a recoverable journal
row rather than erasing the task.
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..errors import EXIT_ESCALATED, EXIT_OK, ConfigDenial, Denial
from .events import RunEvent
from .processes import pid_alive
from .runs import (
    PROVIDER_WAIT_CATEGORIES,
    RunJournal,
    RunState,
    journal_path,
    waiting_kind,
)
from .workspaces import acquire_workspace_slot, release_workspace_slot


@dataclass(frozen=True, slots=True)
class PreparedRun:
    """A task prepared while its project mutation lease is held."""

    task: str
    chat_id: str = ""
    continuation_cycle: str = ""
    initial_events: tuple[RunEvent, ...] = ()
    context: object | None = None


@dataclass(frozen=True, slots=True)
class RunLaunch:
    """The durable identity returned before a background worker proceeds."""

    run_id: str
    prepared: PreparedRun


class _CancellationRequested(Exception):
    pass


Prepare = Callable[[], PreparedRun]
Emit = Callable[[RunEvent], None]
Worker = Callable[[PreparedRun, Emit], int]


class RunCommandService:
    """Serialize one project's run commands through its durable journal."""

    def __init__(self, cfg, *, journal: RunJournal | None = None,
                 alive: Callable[[int], bool] = pid_alive,
                 on_change: Callable[[], None] | None = None) -> None:
        self.cfg = cfg
        self.journal = journal or RunJournal(journal_path(cfg))
        self._on_change = on_change
        recovered = self.journal.recover_abandoned(alive=alive)
        if recovered:
            self._changed()

    def _changed(self) -> None:
        if self._on_change is not None:
            self._on_change()

    def _cancelled(self, run_id: str) -> bool:
        return self.journal.state(run_id) == RunState.CANCELLING

    def _emit(self, run_id: str, event: RunEvent) -> None:
        if self._cancelled(run_id):
            raise _CancellationRequested
        try:
            self.journal.append(run_id, event)
        except RuntimeError:
            # Cancellation can win the SQLite transaction after the state
            # check above.  Preserve that user command instead of converting
            # the expected race into a worker failure.
            if self._cancelled(run_id):
                raise _CancellationRequested from None
            raise
        self._changed()

    def _finish(self, run_id: str, outcome: str, error: str = "") -> None:
        self.journal.finish(run_id, outcome, error)
        self._changed()

    def _park_provider_unavailable(self, run_id: str, exc: Denial) -> bool:
        """Record a routes-exhausted or budget stop as an explicit wait.

        A failed provider call must never be misrepresented as a content
        refusal (NORTH_STAR §14, §31): the journal gets PROVIDER_UNAVAILABLE
        with a machine-readable waiting reason instead of a generic
        ``refused``. Fail-closed: if the current state has no edge to the
        parked state (the loop never reached a provider phase), the caller
        falls back to the human-wait terminal it always had.

        Write order is run first, cycle second. The park append is a single
        transaction that also validates the transition, so a cancellation
        that already won simply refuses the park and no cycle-side decision
        object is minted for a task the user stopped (cycle-first here once
        raced request_cancel into exactly that orphan). If the process dies
        between the two writes, the run is honestly parked and the
        status-gated reconciler (direction B) completes the cycle side.
        """
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        category = str(detail.get("category", ""))
        if category not in PROVIDER_WAIT_CATEGORIES:
            return False
        try:
            self.journal.append(run_id, RunEvent(
                actor="loop", text="waiting for provider",
                kind="provider_unavailable", detail=exc.reason[:2000],
                state=RunState.PROVIDER_UNAVAILABLE,
                waiting_reason={"kind": waiting_kind(category),
                                "category": category,
                                "detail": exc.reason[:400]}))
        except (KeyError, RuntimeError):
            return False
        self._changed()
        self._record_park_cycle(run_id, exc)
        return True

    def _record_park_cycle(self, run_id: str, exc: Denial) -> None:
        """Best-effort cycle-side decision object for a just-parked run.

        Fail-open on the cycle side only: if the decision object cannot be
        written (no git repo, a corrupt store, or — deliberately — a cycle
        whose recorded PASS may never be rewritten into an escalation, or one
        a human already closed), the run stays parked honestly and the
        watchdog's status-gated reconciler remains the backstop. The
        run-side truth is never sacrificed to the cycle write, and the
        escalation carries this run's id so reconciliation and cancellation
        can associate the two records exactly.
        """
        from ..controller import ESCALATED, StateStore
        from ..gitio import git, is_repo

        try:
            if self.journal.state(run_id) != RunState.PROVIDER_UNAVAILABLE:
                return   # a racing cancel settled the run; nothing to decide
        except KeyError:
            return
        root = Path(self.cfg.root)
        if not is_repo(root):
            return
        try:
            anchor = git("rev-parse", "HEAD", cwd=root)
        except Denial:
            return
        row = self.journal.latest()
        if not row or str(row.get("run_id")) != run_id:
            return
        reason = ("provider failure left this task waiting for a person: "
                  + exc.reason[:400])[:400]
        rounds = [int(step.get("round_no", 0) or 0)
                  for step in row.get("steps", [])]
        store = StateStore(root / self.cfg.state_dir / "state.json")
        try:
            cycles = store.snapshot().get("cycles", {})
            candidate = next((cid for cid, c in cycles.items()
                              if c.get("active_sha") == anchor), None)
            if candidate is not None:
                status = cycles[candidate].get("status")
                if status == ESCALATED:
                    return           # the decision object already exists
                if cycles[candidate].get("closed_by_human"):
                    return           # a person already ruled: never reopen it
                # escalate() itself refuses PASSED/CONSUMED (fail-closed
                # against verdict rewriting); the Denial lands below.
                store.escalate(candidate, reason,
                               task=str(row.get("task", "")), run_id=run_id,
                               kind="provider")
            else:
                store.record_build_escalation(
                    self.cfg.science_repo, anchor, reason, max([1, *rounds]),
                    str(row.get("chat_id", "")), str(row.get("task", "")),
                    run_id=run_id, kind="provider")
        except Denial:
            return

    def _drive(self, run_id: str, prepared: PreparedRun, worker: Worker,
               slot, *, propagate: bool) -> int:
        def emit(event: RunEvent) -> None:
            self._emit(run_id, event)

        # The worker renews its lease at provider-call boundaries through this
        # handle; the signature of Worker stays unchanged so existing callers
        # and tests keep working. The run id rides along the same way so the
        # loop can reference this exact run when it records an escalation.
        emit.heartbeat = lambda: self.journal.heartbeat(run_id)
        emit.run_id = run_id
        try:
            code = worker(prepared, emit)
            if self._cancelled(run_id):
                raise _CancellationRequested
            if self.journal.state(run_id) == RunState.PROVIDER_UNAVAILABLE:
                # The loop parked the run itself (after recording the cycle
                # escalation). Keep that state rather than narrating a
                # generic escalation over the specific infrastructure wait.
                self._finish(run_id, "provider_unavailable")
                return code
            self._finish(run_id, {
                EXIT_OK: "passed",
                EXIT_ESCALATED: "escalated",
            }.get(code, "blocked"))
            return code
        except _CancellationRequested:
            self._finish(run_id, "cancelled", "cancelled by user")
            if propagate:
                raise KeyboardInterrupt("cancelled by user") from None
            return 0
        except KeyboardInterrupt:
            self._finish(run_id, "cancelled", "interrupted by user")
            if propagate:
                raise
            return 0
        except Denial as exc:
            if self._cancelled(run_id):
                self._finish(run_id, "cancelled", "cancelled by user")
            elif self._park_provider_unavailable(run_id, exc):
                self._finish(run_id, "provider_unavailable", exc.reason)
            else:
                try:
                    self._finish(run_id, "refused", exc.reason)
                except RuntimeError:
                    # Cancellation can win the transition race after the
                    # checks above (the same expected race _emit converts):
                    # CANCELLING has no edge to WAITING_FOR_HUMAN, so honor
                    # the user's durable command instead of stranding the
                    # row CANCELLING with a dead worker.
                    if not self._cancelled(run_id):
                        raise
                    self._finish(run_id, "cancelled", "cancelled by user")
            if propagate:
                raise
            return exc.exit_code
        except BaseException as exc:
            if self._cancelled(run_id):
                self._finish(run_id, "cancelled", "cancelled by user")
            else:
                self._finish(run_id, "failed", f"{type(exc).__name__}: {exc}")
            if propagate:
                raise
            return 1
        finally:
            release_workspace_slot(slot)

    def start(self, prepare: Prepare, worker: Worker, *, background: bool) -> RunLaunch | int:
        """Prepare, journal and execute one run under the shared mutation lease."""
        slot = acquire_workspace_slot(self.cfg)
        run_id = ""
        try:
            prepared = prepare()
            if not isinstance(prepared, PreparedRun) or not prepared.task.strip():
                raise TypeError("run preparation must return a non-empty PreparedRun")
            run_id = self.journal.start(
                prepared.task, chat_id=prepared.chat_id,
                continuation_cycle=prepared.continuation_cycle)
            for event in prepared.initial_events:
                self.journal.append(run_id, event)
            self._changed()
        except BaseException as exc:
            if run_id:
                self._finish(run_id, "failed", f"{type(exc).__name__}: {exc}")
            release_workspace_slot(slot)
            raise

        if not background:
            return self._drive(run_id, prepared, worker, slot, propagate=True)

        try:
            thread = threading.Thread(
                target=self._drive,
                args=(run_id, prepared, worker, slot),
                kwargs={"propagate": False},
                name=f"crossaudit-run-{run_id[:8]}", daemon=True)
            thread.start()
        except BaseException as exc:
            self._finish(run_id, "failed", f"{type(exc).__name__}: {exc}")
            release_workspace_slot(slot)
            raise
        return RunLaunch(run_id=run_id, prepared=prepared)

    def request_cancel(self, run_id: str | None = None) -> dict:
        """Persist a cancellation command; the worker observes it at its next boundary."""
        try:
            selected = self.journal.request_cancel(run_id)
        except RuntimeError as exc:
            raise ConfigDenial(str(exc), issue="run_not_active", action="dismiss") from exc
        self._changed()
        if selected.get("state") == RunState.CANCELLED.value:
            # A parked run lands directly in CANCELLED; the user's Stop is
            # the human ruling on its escalation, so the pending decision
            # object it references must not go on demanding one.
            self._close_park_escalations(str(selected.get("run_id", "")))
        return selected

    def _close_park_escalations(self, run_id: str) -> None:
        """Close pending escalations referencing a run the user just stopped.

        Only escalations that name this exact run are touched: the reference
        is the association evidence, and a legacy escalation without one is
        left for the human to rule on explicitly.
        """
        if not run_id:
            return
        from ..controller import ESCALATED, StateStore

        store = StateStore(Path(self.cfg.root) / self.cfg.state_dir /
                           "state.json")
        try:
            cycles = store.snapshot().get("cycles", {})
            for cid, cycle in cycles.items():
                if (cycle.get("status") == ESCALATED
                        and str(cycle.get("escalation_run_id", "")) == run_id):
                    store.resolve_escalation(
                        cid, "close",
                        "the user stopped this task while it was parked")
        except Denial:
            return

    def dismiss_interruption(self, run_id: str | None = None) -> bool:
        dismissed = self.journal.dismiss_interruption(run_id)
        if dismissed:
            self._changed()
        return dismissed
