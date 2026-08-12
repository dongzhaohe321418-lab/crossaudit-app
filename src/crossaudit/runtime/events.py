"""Typed operational facts emitted by the agent loop.

Display text is narration. It must never be parsed to discover lifecycle,
round number or event meaning. ``RunEvent`` carries those facts separately so
the CLI can print prose, the journal can persist state and the UI can localize
without changing control flow.

Liveness kinds the watchdog and shell add beside the loop's own narration:
``provider_unavailable`` (the run parked because no configured provider route
can take the next request) and ``run_stalled`` (display-only: the lease
expired while the owner still lives; the state does not change).
"""
from __future__ import annotations

from dataclasses import dataclass

from .runs import RunState


@dataclass(frozen=True, slots=True)
class RunEvent:
    actor: str
    text: str
    state: RunState
    kind: str = "activity"
    detail: str = ""
    round_no: int = 0
    round_limit: int = 0
    #: Machine-readable {kind, category, detail} for waiting states, persisted
    #: on the run row so the UI can say *why* nothing is moving without
    #: parsing prose. Cleared by the next event that does not restate one.
    waiting_reason: dict | None = None

    def __post_init__(self) -> None:
        if not self.actor or not self.kind:
            raise ValueError("run events require an actor and kind")
        if self.round_no < 0 or self.round_limit < 0:
            raise ValueError("run event round values cannot be negative")
        if self.round_limit and self.round_no > self.round_limit:
            raise ValueError("run event round cannot exceed its limit")
        if self.waiting_reason is not None and not isinstance(
                self.waiting_reason, dict):
            raise ValueError("a run event waiting_reason must be a mapping")
