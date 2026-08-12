"""Cross-platform process liveness used by every runtime supervisor."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def windows_pid_alive(pid: object) -> bool:
    """Query Windows without ``os.kill(pid, 0)``, which can emit Ctrl+C."""
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
            return ctypes.get_last_error() == 5
        try:
            status = wintypes.DWORD()
            return bool(kernel32.GetExitCodeProcess(
                handle, ctypes.byref(status))) and status.value == 259
        finally:
            kernel32.CloseHandle(handle)
    except (ImportError, OSError, TypeError, ValueError):
        return False


def pid_alive(pid: object) -> bool:
    if os.name == "nt":
        return windows_pid_alive(pid)
    try:
        os.kill(int(pid), 0)
        return True
    except PermissionError:
        return True
    except (ProcessLookupError, OSError, ValueError, TypeError):
        return False


#: Version prefix on the identity-token FORMAT (not the process). Recovery
#: compares a stored token to a freshly probed one; the two are only
#: comparable when both are in the current format. A stored token that does
#: not carry this prefix is a pre-fix value — see below — and recovery must
#: treat it as an unverifiable identity, never as a mismatch.
IDENTITY_TOKEN_PREFIX = "v2:"


def process_identity(pid: object) -> str | None:
    """A cross-process-stable incarnation marker: pid + absolute start time.

    ``os.kill(pid, 0)`` can only say "some process answers to this number".
    After a worker dies its pid can be recycled by an unrelated process, and
    the bare-pid probe then vouches for a stranger forever. The process start
    time pins the incarnation: same pid + same start time is the same
    process; same pid + different start time is provably a recycled pid.

    The marker MUST read identical from any process on the machine, or a
    supervisor would compute a different token than the worker did for the
    same live pid and reclaim a healthy run. An earlier version rendered the
    start time with ``ps -o lstart=`` in the *caller's* locale/timezone —
    strftime %c depends on TZ / LC_TIME / LC_ALL / LANG of the calling
    process, so a daemon under launchd (no LANG) and a terminal (TZ set)
    produced different strings for the same worker, and the mismatch was
    read as a recycled pid. This version is locale- and timezone-free:

    * Linux reads the kernel's jiffies-since-boot start time from
      ``/proc/<pid>/stat`` — a bare integer, no formatting to poison;
    * macOS/BSD keep ``ps -o lstart=`` but pin ``LC_ALL=C`` and ``TZ=UTC``
      so every process renders the identical string for a given incarnation.

    The ``v2:`` prefix versions the token format so a pre-fix (poisoned)
    value stored by an earlier build is recognizable as not-comparable.

    Returns None when the identity cannot be read (Windows, a vanished pid,
    or the probe failing) — callers must treat None as "unknowable", never
    "alive".
    """
    if os.name == "nt":
        return None
    try:
        process_id = int(pid)
    except (TypeError, ValueError):
        return None
    if process_id <= 0:
        return None
    marker = _start_marker(process_id)
    if marker is None:
        return None
    return f"{IDENTITY_TOKEN_PREFIX}{process_id}:{marker}"


def _start_marker(process_id: int) -> str | None:
    """The locale-independent absolute start time of ``process_id``, or None."""
    # Linux: field 22 of /proc/<pid>/stat is starttime in clock ticks since
    # boot — a bare integer, unique per incarnation within one boot, with no
    # formatting a locale could poison, and no subprocess to spawn. After
    # dropping the leading "pid (comm)" the remaining fields begin at state
    # (field 3), so starttime (field 22) is index 19.
    proc_stat = Path(f"/proc/{process_id}/stat")
    try:
        if proc_stat.is_file():
            after_comm = proc_stat.read_text(encoding="utf-8").rsplit(")", 1)[1]
            fields = after_comm.split()
            if len(fields) > 19 and fields[19].isdigit():
                return fields[19]
    except (OSError, IndexError, ValueError):
        pass
    # macOS/BSD: no /proc. ``ps -o lstart`` renders the start wall clock with
    # strftime %c, which the CALLER's TZ/LC_TIME would poison — the exact bug
    # this pinning fixes. LC_ALL=C and TZ=UTC make the rendering identical in
    # every process on the machine; LANG is set too though LC_ALL dominates.
    try:
        result = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(process_id)],
            capture_output=True, text=True, timeout=1.0, check=False,
            env={**os.environ, "LC_ALL": "C", "LANG": "C", "TZ": "UTC"})
        started = result.stdout.strip()
        if result.returncode == 0 and started:
            return started
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def zombie(pid: int) -> bool:
    """A reaped-later POSIX zombie is dead even when kill(pid, 0) succeeds."""
    if os.name == "nt":
        return False
    proc_stat = Path(f"/proc/{pid}/stat")
    try:
        if proc_stat.is_file():
            return proc_stat.read_text(encoding="utf-8").rsplit(
                ")", 1)[1].strip().startswith("Z")
        result = subprocess.run(
            ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True,
            text=True, timeout=0.5, check=False)
        return result.returncode == 0 and result.stdout.strip().startswith("Z")
    except (OSError, subprocess.SubprocessError, IndexError):
        return False
