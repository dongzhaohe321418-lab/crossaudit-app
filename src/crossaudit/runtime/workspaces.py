"""Atomic cross-process capacity leases for project mutations."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

from ..errors import ConfigDenial
from .processes import pid_alive

WORKSPACE_RUNTIME = ".crossaudit-workspace"
DEFAULT_MAX_ACTIVE = 4


def _runtime_dir(cfg) -> Path:
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


def _with_workspace_lock(cfg, operation):
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
            if pid_alive(row.get("pid")):
                rows.append(row)
            else:
                path.unlink(missing_ok=True)
        except (OSError, ValueError, TypeError):
            path.unlink(missing_ok=True)
    return rows


def acquire_workspace_slot(cfg) -> Path:
    """Atomically reserve one cross-project mutation slot in this workspace."""
    key = hashlib.sha256(str(cfg.root).encode()).hexdigest()[:20]
    target = _runtime_dir(cfg) / f"slot-{key}.json"

    def claim(base: Path) -> Path:
        active = _slots(base)
        if target.is_file():
            raise ConfigDenial("this project already owns a workspace build slot")
        limit = _max_active()
        if len(active) >= limit:
            names = ", ".join(Path(str(row.get("root", "?"))).name for row in active)
            raise ConfigDenial(f"workspace build capacity is {limit}; wait for {names}")
        target.write_text(json.dumps({
            "pid": os.getpid(), "root": str(cfg.root), "started": int(time.time()),
        }), encoding="utf-8")
        return target

    return _with_workspace_lock(cfg, claim)


def release_workspace_slot(path: Path | None) -> None:
    if path is not None:
        path.unlink(missing_ok=True)


def workspace_capacity(cfg) -> dict:
    def inspect(base: Path) -> dict:
        active = _slots(base)
        return {"active": len(active), "limit": _max_active(),
                "projects": [Path(str(row.get("root", ""))).name for row in active]}

    return _with_workspace_lock(cfg, inspect)
