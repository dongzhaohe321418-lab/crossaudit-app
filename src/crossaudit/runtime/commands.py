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

from ..errors import EXIT_ESCALATED, EXIT_OK, ConfigDenial, Denial
from .events import RunEvent
from .processes import pid_alive
from .runs import (
    PROVIDER_WAIT_CATEGORIES,
    RunJournal,
    RunState,
    journal_path,
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
        """Record a routes-exhausted stop as an explicit provider wait.

        A failed provider call must never be misrepresented as a content
        refusal (NORTH_STAR §14, §31): the journal gets PROVIDER_UNAVAILABLE
        with a machine-readable waiting reason instead of a generic
        ``refused``. Fail-closed: if the current state has no edge to the
        parked state (the loop never reached a provider phase), the caller
        falls back to the human-wait terminal it always had.
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
                waiting_reason={"kind": "provider", "category": category,
                                "detail": exc.reason[:400]}))
        except (KeyError, RuntimeError):
            return False
        self._changed()
        return True

    def _drive(self, run_id: str, prepared: PreparedRun, worker: Worker,
               slot, *, propagate: bool) -> int:
        def emit(event: RunEvent) -> None:
            self._emit(run_id, event)

        # The worker renews its lease at provider-call boundaries through this
        # handle; the signature of Worker stays unchanged so existing callers
        # and tests keep working.
        emit.heartbeat = lambda: self.journal.heartbeat(run_id)
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
                self._finish(run_id, "refused", exc.reason)
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
        return selected

    def dismiss_interruption(self, run_id: str | None = None) -> bool:
        dismissed = self.journal.dismiss_interruption(run_id)
        if dismissed:
            self._changed()
        return dismissed
