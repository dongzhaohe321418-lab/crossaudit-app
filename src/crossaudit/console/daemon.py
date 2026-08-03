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
* **An interrupted build must say so.** The tracker is in memory and dies with
  the process; the ledger keeps every committed round but cannot know a run was
  cut off mid-round. A flag written when a build starts, and removed when it
  ends, lets a restarted console say "this was interrupted" rather than quietly
  presenting a half-finished loop as finished.

The run file holds a session token, so it is written 0600 and lives in the state
directory, which is gitignored: a credential in the ledger would be a credential
published.
"""
from __future__ import annotations

import json
import hashlib
import os
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from ..config import Config
from ..errors import ConfigDenial

RUN_FILE = "console.json"
BUILD_FLAG = "build-in-flight.json"
WORKSPACE_RUNTIME = ".crossaudit-workspace"
DEFAULT_MAX_ACTIVE = 4
KILL_SIGNAL = getattr(signal, "SIGKILL", signal.SIGTERM)


def run_path(cfg: Config) -> Path:
    return cfg.root / cfg.state_dir / RUN_FILE


def flag_path(cfg: Config) -> Path:
    return cfg.root / cfg.state_dir / BUILD_FLAG


def _pid_alive(pid: object) -> bool:
    if os.name == "nt":
        return _windows_pid_alive(pid)
    try:
        os.kill(int(pid), 0)
        return True
    except PermissionError:
        return True
    except (ProcessLookupError, OSError, ValueError, TypeError):
        return False


def _windows_pid_alive(pid: object) -> bool:
    """Query a Windows process without os.kill(pid, 0), which emits Ctrl+C."""
    try:
        import ctypes
        from ctypes import wintypes

        process_id = int(pid)
        if process_id <= 0:
            return False
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL,
                                         wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE,
                                                ctypes.POINTER(wintypes.DWORD)]
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(0x1000, False, process_id)
        if not handle:
            # Access denied proves that something owns the PID even though this
            # process cannot inspect it; an invalid/nonexistent PID reports 87.
            return ctypes.get_last_error() == 5
        try:
            status = wintypes.DWORD()
            return bool(kernel32.GetExitCodeProcess(
                handle, ctypes.byref(status))) and status.value == 259
        finally:
            kernel32.CloseHandle(handle)
    except (ImportError, OSError, TypeError, ValueError):
        return False


def _runtime_dir(cfg: Config) -> Path:
    owner = getattr(os, "getuid", lambda: os.getpid())()
    home = Path(tempfile.gettempdir()) / f"{WORKSPACE_RUNTIME}-{owner}"
    home.mkdir(mode=0o700, exist_ok=True)
    try:
        home.chmod(0o700)
    except OSError:
        pass
    key = hashlib.sha256(str(cfg.root.parent.resolve()).encode()).hexdigest()[:20]
    return home / key


def _max_active() -> int:
    try:
        return max(1, min(32, int(os.environ.get(
            "CROSSAUDIT_MAX_ACTIVE_PROJECTS", DEFAULT_MAX_ACTIVE))))
    except ValueError:
        return DEFAULT_MAX_ACTIVE


def _with_workspace_lock(cfg: Config, operation):
    base = _runtime_dir(cfg)
    base.mkdir(mode=0o700, exist_ok=True)
    lock = base / "manager.lock"
    deadline = time.monotonic() + 2
    while True:
        try:
            lock.mkdir()
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > 10:
                    lock.rmdir()
                    continue
            except OSError:
                pass
            if time.monotonic() >= deadline:
                raise ConfigDenial("workspace runtime manager is busy; retry shortly")
            time.sleep(0.02)
    try:
        return operation(base)
    finally:
        try:
            lock.rmdir()
        except OSError:
            pass


def _slots(base: Path) -> list[dict]:
    rows = []
    for path in base.glob("slot-*.json"):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
            if _pid_alive(row.get("pid")):
                rows.append(row)
            else:
                path.unlink(missing_ok=True)
        except (OSError, ValueError, TypeError):
            path.unlink(missing_ok=True)
    return rows


def acquire_workspace_slot(cfg: Config) -> Path:
    """Atomically reserve one cross-project build slot in this workspace."""
    key = hashlib.sha256(str(cfg.root).encode()).hexdigest()[:20]
    target = _runtime_dir(cfg) / f"slot-{key}.json"

    def claim(base: Path) -> Path:
        active = _slots(base)
        if target.is_file():
            raise ConfigDenial("this project already owns a workspace build slot")
        limit = _max_active()
        if len(active) >= limit:
            names = ", ".join(Path(str(r.get("root", "?"))).name for r in active)
            raise ConfigDenial(f"workspace build capacity is {limit}; wait for {names}")
        target.write_text(json.dumps({"pid": os.getpid(), "root": str(cfg.root),
                                      "started": int(time.time())}), encoding="utf-8")
        return target

    return _with_workspace_lock(cfg, claim)


def release_workspace_slot(path: Path | None) -> None:
    if path is not None:
        path.unlink(missing_ok=True)


def workspace_capacity(cfg: Config) -> dict:
    def inspect(base: Path) -> dict:
        active = _slots(base)
        return {"active": len(active), "limit": _max_active(),
                "projects": [Path(str(r.get("root", ""))).name for r in active]}
    return _with_workspace_lock(cfg, inspect)


# ------------------------------------------------------------------ run file
def write_run(cfg: Config, *, pid: int, port: int, token: str) -> Path:
    p = run_path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    value = json.dumps({"pid": pid, "port": port, "token": token,
                        "started": int(time.time()),
                        "root": str(cfg.root)}, indent=1)
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
    url = f"http://127.0.0.1:{port}/api/state?t={token}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def fetch_state(info: dict, timeout: float = 0.5) -> dict | None:
    """Read a daemon's public console state without exposing its session token."""
    try:
        port, token = int(info["port"]), str(info["token"])
        url = f"http://127.0.0.1:{port}/api/state?t={token}"
        with urllib.request.urlopen(url, timeout=timeout) as response:
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


def url_for(info: dict) -> str:
    return f"http://127.0.0.1:{info['port']}/?t={info['token']}"


# -------------------------------------------------------------------- detach
def spawn(cfg: Config, port: int) -> dict:
    """Start a console detached from this terminal, and wait for it to answer.

    A new session means the daemon does not receive the terminal's SIGHUP when
    the window closes, which is the whole point.
    """
    env = dict(os.environ, CROSSAUDIT_CONSOLE_CHILD="1")
    log = cfg.root / cfg.state_dir / "console.log"
    log.parent.mkdir(parents=True, exist_ok=True)
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
    """A reaped-later POSIX zombie is dead even though kill(pid, 0) succeeds."""
    if os.name == "nt":
        return False
    proc_stat = Path(f"/proc/{pid}/stat")
    try:
        if proc_stat.is_file():
            # Linux: pid (comm) state ...; comm may contain spaces/parentheses.
            return proc_stat.read_text(encoding="utf-8").rsplit(")", 1)[1].strip().startswith("Z")
        result = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)],
                                capture_output=True, text=True, timeout=0.5)
        return result.returncode == 0 and result.stdout.strip().startswith("Z")
    except (OSError, subprocess.SubprocessError, IndexError):
        return False


# ------------------------------------------------------- interrupted builds
def mark_build(cfg: Config, task: str, chat_id: str = "") -> None:
    p = flag_path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"task": task, "chat_id": chat_id,
                             "started": int(time.time()), "pid": os.getpid()}),
                 encoding="utf-8")


def unmark_build(cfg: Config) -> None:
    flag_path(cfg).unlink(missing_ok=True)


def interrupted(cfg: Config) -> dict | None:
    """A build that was in flight when the process ended.

    The ledger holds the rounds that were committed; what it cannot know is that
    a round was cut off. This says so rather than letting a half-finished loop
    read as a finished one.
    """
    p = flag_path(cfg)
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
