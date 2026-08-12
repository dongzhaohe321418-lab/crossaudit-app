"""Keeping the console alive across a closed window, and finding it again.

Closing a browser tab never stopped a build — it runs in a thread of the console
process. What stopped it was closing the terminal. So the console can now detach
from the terminal that started it, and a later `crossaudit console` finds the
running one and hands back its URL instead of starting a second server.

Three things this has to get right, and each is a small honesty problem:

* **Reattaching, not restarting.** Two consoles on one project would race on the
  working tree and the round budget. If a live daemon is found, its URL is
  returned; the second invocation starts nothing.
* **A stale run file is not a running daemon.** A crash leaves the file behind,
  so liveness is proven by asking the port, not by trusting the file.
* **An interrupted build must say so.** Git keeps every committed round but
  cannot know that a provider call was cut off mid-round. The operational
  SQLite journal records each typed run transition, so a restarted console can
  recover a dead worker exactly once instead of presenting partial work as
  finished. A legacy flag is read only to migrate projects created before the
  journal existed.

The run file holds a session token, so it is written 0600 and lives in the state
directory, which is gitignored: a credential in the ledger would be a credential
published.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from .. import _selfid
from ..config import Config
from ..controller import BLOCKED, ESCALATED, OPEN, StateStore
from ..errors import Denial
from ..gitio import git, is_repo
from ..runtime import (
    RunCommandService,
    RunJournal,
    RunState,
    journal_path,
    pid_alive,
    windows_pid_alive,
    zombie,
)

RUN_FILE = "console.json"
#: How often the console's watchdog walks this project's runs table. 30 s is
#: far below the 120 s lease, so a stall is reported within one lease window,
#: while an idle project costs a few cheap SQLite reads per minute.
WATCHDOG_INTERVAL_S = 30.0
#: Cycle-store history events that prove the needs-a-human write reached the
#: cycle side after a given run started.
_ESCALATION_EVENTS = frozenset({
    "escalate", "build_escalated_before_revision", "human_resolution"})
#: Run states that mean "a person owns the next step".
_HUMAN_WAIT_STATES = frozenset({
    RunState.WAITING_FOR_HUMAN.value, RunState.PROVIDER_UNAVAILABLE.value})
# Read-only migration fallback for a build interrupted by CrossAudit <= 4.14.
LEGACY_BUILD_FLAG = "build-in-flight.json"
KILL_SIGNAL = getattr(signal, "SIGKILL", signal.SIGTERM)


def run_path(cfg: Config) -> Path:
    return cfg.root / cfg.state_dir / RUN_FILE


def _pid_alive(pid: object) -> bool:
    if os.name == "nt":
        return _windows_pid_alive(pid)
    return pid_alive(pid)


def _windows_pid_alive(pid: object) -> bool:
    return windows_pid_alive(pid)


# ------------------------------------------------------------------ run file
def write_run(cfg: Config, *, pid: int, port: int, token: str) -> Path:
    p = run_path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    identity = _selfid.identity(cfg.root)
    value = json.dumps({"pid": pid, "port": port, "token": token,
                        "started": int(time.time()), "root": str(cfg.root),
                        "runtime": {
                            "version": identity["version"],
                            "code_digest_sha256": identity["code_digest_sha256"],
                            "install_mode": identity["install_mode"],
                        }}, indent=1)
    # Set the restrictive mode at creation time; writing first and chmodding
    # afterwards briefly exposed the browser token on POSIX systems.
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(value)
    if os.name != "nt":
        p.chmod(0o600)
    return p


def read_run(cfg: Config) -> dict | None:
    p = run_path(cfg)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def clear_run(cfg: Config) -> None:
    run_path(cfg).unlink(missing_ok=True)


def responding(port: int, token: str, timeout: float = 1.5) -> bool:
    """Liveness is proven by the port answering, never by the file existing."""
    url = f"http://127.0.0.1:{port}/api/health?t={token}"
    try:
        # URL is constructed here from a validated integer and loopback literal.
        with urllib.request.urlopen(url, timeout=timeout) as r:  # nosec B310
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def fetch_state(info: dict, timeout: float = 0.5) -> dict | None:
    """Read a daemon's public console state without exposing its session token."""
    try:
        port, token = int(info["port"]), str(info["token"])
        url = f"http://127.0.0.1:{port}/api/state?t={token}"
        # URL is constructed here from a validated integer and loopback literal.
        with urllib.request.urlopen(url, timeout=timeout) as response:  # nosec B310
            value = json.loads(response.read())
            return value if response.status == 200 and isinstance(value, dict) else None
    except (KeyError, TypeError, ValueError, json.JSONDecodeError,
            urllib.error.URLError, OSError):
        return None


def live(cfg: Config) -> dict | None:
    """The running console for this project, if there is one."""
    info = read_run(cfg)
    if not info:
        return None
    if not responding(info["port"], info["token"]):
        clear_run(cfg)                 # stale: the process is gone
        return None
    return info


def runtime_matches(info: dict, *, root: Path | None = None) -> bool:
    """Whether a live worker serves the same code as this launcher."""
    recorded = info.get("runtime")
    if not isinstance(recorded, dict):
        return False
    current = _selfid.identity(root)
    return (recorded.get("version") == current["version"]
            and recorded.get("code_digest_sha256") == current["code_digest_sha256"]
            and recorded.get("install_mode") == current["install_mode"])


def reusable_for_launch(cfg: Config) -> dict | None:
    """Return a compatible worker, or replace an idle worker from older code.

    A software update must not interrupt a Generator/Auditor run in flight. An
    idle older worker, however, must not keep serving cached UI and provider
    behavior after the application bundle is replaced.
    """
    info = live(cfg)
    if not info or runtime_matches(info, root=cfg.root):
        return info
    state = fetch_state(info)
    progress = state.get("progress") if isinstance(state, dict) else None
    if not isinstance(progress, dict) or not progress.get("finished", True):
        return info
    stopped = stop(cfg)
    return info if "did not stop" in stopped else None


def url_for(info: dict) -> str:
    return f"http://127.0.0.1:{info['port']}/?t={info['token']}"


# -------------------------------------------------------------------- detach
def spawn(cfg: Config, port: int) -> dict:
    """Start a console detached from this terminal, and wait for it to answer.

    A new session means the daemon does not receive the terminal's SIGHUP when
    the window closes, which is the whole point.
    """
    lock = cfg.root / cfg.state_dir / "console-start.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + 10
    while True:
        try:
            lock.mkdir()
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > 15:
                    lock.rmdir()
                    continue
            except OSError:
                pass
            if time.monotonic() >= deadline:
                raise TimeoutError("another process is still starting this project")
            time.sleep(0.05)
    try:
        # The caller normally checked before entering spawn, but another click
        # or app process may have won the lock in between.
        running = reusable_for_launch(cfg)
        if running:
            return running
        env = dict(os.environ, CROSSAUDIT_CONSOLE_CHILD="1")
        log = cfg.root / cfg.state_dir / "console.log"
        if os.environ.get("CROSSAUDIT_APP_MODE") == "1":
            command = ([sys.executable, "--project-console", str(cfg.root), str(port)]
                       if getattr(sys, "frozen", False) else
                       [sys.executable, "-m", "crossaudit.app", "--project-console",
                        str(cfg.root), str(port)])
        else:
            command = [sys.executable, "-m", "crossaudit.cli.main", "console",
                       "--port", str(port), "--foreground"]
        with open(log, "ab") as fh:
            subprocess.Popen(
                command,
                cwd=str(cfg.root), env=env, stdout=fh, stderr=fh,
                stdin=subprocess.DEVNULL, start_new_session=True)
        for _ in range(60):                # up to ~6s for the port to come up
            time.sleep(0.1)
            info = read_run(cfg)
            if info and responding(info["port"], info["token"]):
                return info
        raise TimeoutError(f"the console did not come up; see {log}")
    finally:
        try:
            lock.rmdir()
        except OSError:
            pass


def stop(cfg: Config) -> str:
    info = read_run(cfg)
    if not info:
        return "no console was running"
    pid = info.get("pid")
    try:
        os.kill(pid, signal.SIGTERM)
    except (ProcessLookupError, OSError, TypeError):
        clear_run(cfg)
        return "no console was running (stale record cleared)"
    # A silent port is not a dead process. Wait for the process itself, then
    # insist — and never clear the record while it is still alive, because that
    # record is the only way anything can find this process again.
    if not _gone(pid, tries=30):
        try:
            os.kill(pid, KILL_SIGNAL)
        except (ProcessLookupError, OSError, TypeError):
            pass
        if not _gone(pid, tries=20):
            return (f"the console on port {info['port']} (pid {pid}) did not stop; "
                    f"its record is kept so it can be found again")
    clear_run(cfg)
    return f"stopped the console on port {info['port']}"


def _gone(pid: int, *, tries: int) -> bool:
    for _ in range(tries):
        time.sleep(0.1)
        if _zombie(pid):
            return True
        if not _pid_alive(pid):
            return True
    return False


def _zombie(pid: int) -> bool:
    return zombie(pid)


# ------------------------------------------------------- interrupted builds
def interrupted(cfg: Config) -> dict | None:
    """A build that was in flight when the process ended.

    The ledger holds the rounds that were committed; what it cannot know is that
    a round was cut off. This says so rather than letting a half-finished loop
    read as a finished one.
    """
    runtime = journal_path(cfg)
    if runtime.is_file():
        service = RunCommandService(
            cfg, journal=RunJournal(runtime), alive=_pid_alive)
        journal = service.journal
        row = journal.interruption()
        if row:
            steps = row.get("steps") or []
            failed = row["state"] == "FAILED"
            work_steps = [step for step in steps if step.get("kind") not in {
                "run_finished", "run_interrupted", "interruption_dismissed"}]
            latest = work_steps[-1] if work_steps else {}
            return {
                "run_id": row["run_id"],
                "task": row["task"],
                "chat_id": row.get("chat_id", ""),
                "continuation_cycle": row.get("continuation_cycle", ""),
                "phase": "failed" if failed else (
                    latest.get("actor") or row["state"].lower()),
                "detail": (row.get("error", "") if failed else
                           latest.get("detail") or latest.get("text") or
                           row.get("error", "")),
                "started": int(row["started"]),
                "updated": int(row["updated"]),
                "pid": row.get("owner_pid", 0),
                "failed": failed,
            }
    p = cfg.root / cfg.state_dir / LEGACY_BUILD_FLAG
    if not p.is_file():
        return None
    try:
        info = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    pid = info.get("pid")
    if pid and pid != os.getpid():
        if _pid_alive(pid):            # still alive: it is running, not interrupted
            return None
    elif pid == os.getpid():
        return None
    return info


def dismiss_legacy_interruption(cfg: Config) -> bool:
    """Consume only the read-only <=4.14 migration marker, if present."""
    legacy = cfg.root / cfg.state_dir / LEGACY_BUILD_FLAG
    if legacy.exists():
        legacy.unlink(missing_ok=True)
        return True
    return False


# ----------------------------------------------------------------- liveness
def reconcile_human_wait(cfg: Config, journal: RunJournal | None = None) -> dict:
    """Complete a torn needs-a-human write, in either direction, exactly once.

    "A person owns the next step" is recorded in two stores: the cycle store
    (state.json, status ESCALATED — the decision object) and the run journal
    (WAITING_FOR_HUMAN / PROVIDER_UNAVAILABLE — what the UI narrates). The
    writers' contract is cycle first, run second (build.run_loop tail,
    cmd_run's record_verdict); a process death in between tears them:

    * an ESCALATED cycle beside an INTERRUPTED run presents a human decision
      as a crash — the run side is completed to WAITING_FOR_HUMAN;
    * a human-wait run with no escalation recorded since it started offers
      the person nothing to decide on — the cycle side is escalated with the
      run's own stop reason.

    Only the newest run is considered: older human-wait runs belong to cycles
    that were already ruled on, and reviving them would invent decisions.
    Both repairs are idempotent; a corrupt store aborts rather than guesses.
    """
    result: dict = {"run_completed": None, "cycle_recorded": None}
    runtime = journal_path(cfg)
    if journal is None:
        if not runtime.is_file():
            return result
        journal = RunJournal(runtime)
    row = journal.latest()
    if row is None:
        return result
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    try:
        state = store.snapshot()
    except Denial:
        return result            # a corrupt store is its own incident; never guess
    since = float(row["started"]) - 1
    recent = [event for event in state.get("history", [])
              if float(event.get("t", 0) or 0) >= since]
    escalation_recorded = any(
        event.get("event") in ("escalate", "build_escalated_before_revision")
        or (event.get("event") == "verdict" and event.get("status") == ESCALATED)
        for event in recent)
    escalation_activity = escalation_recorded or any(
        event.get("event") == "human_resolution" for event in recent)
    cycles = state.get("cycles", {})
    escalated_now = [dict(c, cycle_id=cid) for cid, c in cycles.items()
                     if c.get("status") == ESCALATED]

    if (row["state"] == RunState.INTERRUPTED.value and escalation_recorded
            and escalated_now):
        reason = str(escalated_now[-1].get("escalation_reason", ""))[:400]
        if journal.complete_human_wait(str(row["run_id"]), reason):
            result["run_completed"] = str(row["run_id"])
        return result

    if row["state"] in _HUMAN_WAIT_STATES and not escalation_activity:
        if not is_repo(cfg.root):
            return result
        try:
            anchor = git("rev-parse", "HEAD", cwd=cfg.root)
        except Denial:
            return result
        waiting = row.get("waiting_reason") or {}
        if row["state"] == RunState.PROVIDER_UNAVAILABLE.value:
            # "provider failure" in the reason is what routes the escalation
            # to the provider remedies (retry / review connection / change
            # model) instead of content guidance.
            reason = ("provider failure left this task waiting for a person: "
                      + str(waiting.get("detail") or row.get("error")
                            or "no provider route is available"))[:400]
        else:
            reason = (str(row.get("error") or "").strip()
                      or "the run stopped for a person before its decision "
                         "record was written")[:400]
        rounds = [int(step.get("round_no", 0) or 0)
                  for step in row.get("steps", [])]
        target = next((cid for cid, c in cycles.items()
                       if c.get("active_sha") == anchor
                       and c.get("status") in (OPEN, BLOCKED, ESCALATED)), None)
        try:
            if target is not None:
                cycle = store.escalate(target, reason,
                                       task=str(row.get("task", "")))
            else:
                cycle = store.record_build_escalation(
                    cfg.science_repo, anchor, reason, max([1, *rounds]),
                    str(row.get("chat_id", "")), str(row.get("task", "")))
        except Denial:
            return result
        result["cycle_recorded"] = cycle["cycle_id"]
    return result


def watchdog_sweep(cfg: Config) -> dict:
    """One idempotent liveness pass over this project's runs table.

    Three duties, each bounded: dead owners are recovered exactly once (a
    durable cancellation still ends CANCELLED, other work INTERRUPTED — the
    existing recover_abandoned semantics); an expired lease under a living
    owner becomes a display-only stall note, never a state change; and a torn
    needs-a-human write is completed on whichever side is missing. Running
    the sweep twice changes nothing the first pass did not.
    """
    reconciled: dict = {"run_completed": None, "cycle_recorded": None}
    runtime = journal_path(cfg)
    if not runtime.is_file():
        return {"changed": False, "recovered": [], "stalled": [],
                "reconciled": reconciled}
    journal = RunJournal(runtime)
    recovered = journal.recover_abandoned(alive=_pid_alive)
    stalled = journal.mark_stalled_runs(alive=_pid_alive)
    reconciled = reconcile_human_wait(cfg, journal)
    return {"changed": bool(recovered or stalled
                            or reconciled["run_completed"]
                            or reconciled["cycle_recorded"]),
            "recovered": recovered, "stalled": stalled,
            "reconciled": reconciled}
