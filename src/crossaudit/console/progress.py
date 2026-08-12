"""A read-only console projection of the canonical operational run journal.

The old tracker also implemented an in-memory Run/Step lifecycle.  That made
tests convenient but left a second state machine beside SQLite.  Commands now
go through :class:`crossaudit.runtime.RunCommandService`; this object only
selects a journal, reads its projection and wakes live views after a durable
mutation.
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from ..runtime import ACTIVE_STATES, RunJournal, RunState


class Tracker:
    """One run projection with optional durable journal backing."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._journal: RunJournal | None = None
        self._journal_path: Path | None = None
        self._listeners: list[Callable[[], None]] = []

    def bind(self, path: Path) -> None:
        """Bind this project process to its durable operational journal.

        Rebinding the same path is cheap. A different project replaces only the
        process-local projection; the old project's database remains intact.
        This read model deliberately performs no crash recovery or mutation.
        """
        selected = Path(path).resolve()
        with self._lock:
            if self._journal_path == selected and self._journal is not None:
                return
            journal = RunJournal(selected)
            self._journal = journal
            self._journal_path = selected

    def subscribe(self, listener: Callable[[], None]) -> None:
        """Wake a view when progress changes; the ledger remains the record."""
        with self._lock:
            self._listeners.append(listener)

    def notify(self) -> None:
        """Wake subscribers after a command has committed a journal change."""
        with self._lock:
            listeners = tuple(self._listeners)
        for listener in listeners:
            listener()

    @property
    def running(self) -> bool:
        with self._lock:
            if self._journal is None:
                return False
            latest = self._journal.latest()
            return bool(latest and RunState(latest["state"]) in ACTIVE_STATES)

    def snapshot(self) -> dict | None:
        with self._lock:
            return self._journal.latest() if self._journal is not None else None

    def interruption(self) -> dict | None:
        with self._lock:
            return self._journal.interruption() if self._journal is not None else None

    def clear(self) -> None:
        with self._lock:
            # `clear` is a process/test reset, not deletion of durable history.
            self._journal = None
            self._journal_path = None
        self.notify()

#: One tracker per process. The console is a single-project window, and a build
#: is a single-project act.
TRACKER = Tracker()
