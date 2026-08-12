"""Typed operational facts emitted by the agent loop.

Display text is narration. It must never be parsed to discover lifecycle,
round number or event meaning. ``RunEvent`` carries those facts separately so
the CLI can print prose, the journal can persist state and the UI can localize
without changing control flow.
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

    def __post_init__(self) -> None:
        if not self.actor or not self.kind:
            raise ValueError("run events require an actor and kind")
        if self.round_no < 0 or self.round_limit < 0:
            raise ValueError("run event round values cannot be negative")
        if self.round_limit and self.round_no > self.round_limit:
            raise ValueError("run event round cannot exceed its limit")
