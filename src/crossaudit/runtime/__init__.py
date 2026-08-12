"""Durable operational state for the desktop agent runtime.

The audit ledger remains the evidence record.  This package owns only the
recoverable process state needed to run and present work reliably.
"""

from .events import RunEvent
from .commands import PreparedRun, RunCommandService, RunLaunch
from .processes import pid_alive, windows_pid_alive, zombie
from .provisioning import ProvisioningJournal
from .runs import ACTIVE_STATES, TERMINAL_STATES, RunJournal, RunState, journal_path
from .workspaces import acquire_workspace_slot, release_workspace_slot, workspace_capacity

__all__ = [
    "ACTIVE_STATES", "TERMINAL_STATES", "PreparedRun", "ProvisioningJournal",
    "RunCommandService", "RunEvent", "RunJournal", "RunLaunch", "RunState",
    "acquire_workspace_slot", "journal_path",
    "pid_alive", "release_workspace_slot", "windows_pid_alive",
    "workspace_capacity", "zombie",
]
