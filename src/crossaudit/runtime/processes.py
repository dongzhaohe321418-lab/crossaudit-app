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
