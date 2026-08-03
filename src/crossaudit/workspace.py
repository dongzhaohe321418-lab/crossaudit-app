"""Persist and validate the desktop application's user-selected workspace."""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from .errors import ConfigDenial

SETTINGS_NAME = "app-settings.json"


def default_workspace() -> Path:
    return Path.home() / "Documents" / "CrossAudit Projects"


def _settings_path(support: Path) -> Path:
    return support / SETTINGS_NAME


def _read_settings(support: Path) -> dict:
    path = _settings_path(support)
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def saved_workspace(support: Path) -> Path | None:
    selected = str(_read_settings(support).get("workspace", "")).strip()
    return Path(selected).expanduser().resolve() if selected else None


def known_workspaces(support: Path) -> tuple[Path, ...]:
    """Return only existing folders previously approved by the native picker."""
    value = _read_settings(support)
    rows = value.get("workspaces", [])
    if not isinstance(rows, list):
        rows = []
    active = str(value.get("workspace", "")).strip()
    if active:
        rows.append(active)
    result: list[Path] = []
    for row in rows:
        try:
            path = Path(str(row)).expanduser().resolve(strict=True)
        except (OSError, ValueError):
            continue
        if path.is_dir() and path not in result:
            result.append(path)
    return tuple(result)


def configured_workspace(support: Path) -> Path:
    override = os.environ.get("CROSSAUDIT_WORKSPACE_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return saved_workspace(support) or default_workspace()


def select_workspace(support: Path, selected: str) -> Path:
    """Validate a native-picked directory, persist it, and activate it now."""
    raw = selected.strip()
    if not raw or len(raw) > 4096:
        raise ConfigDenial(
            "Choose a local folder for CrossAudit projects",
            issue="workspace_missing", action="choose_workspace")
    try:
        root = Path(raw).expanduser().resolve(strict=True)
    except OSError as exc:
        raise ConfigDenial(
            "That workspace folder no longer exists; choose it again",
            issue="workspace_missing", action="choose_workspace") from exc
    if not root.is_dir():
        raise ConfigDenial(
            "The selected workspace is not a folder",
            issue="workspace_not_directory", action="choose_workspace")
    if not os.access(root, os.R_OK | os.W_OK | os.X_OK):
        raise ConfigDenial(
            "CrossAudit cannot read and write the selected folder. Choose another "
            "folder or grant your account access in Finder",
            issue="workspace_permission", action="choose_workspace")

    # os.access can be optimistic with ACLs and network volumes. A private,
    # empty probe proves the exact create/remove operations project setup needs.
    probe = root / f".crossaudit-write-test-{uuid.uuid4().hex}"
    try:
        probe.mkdir(mode=0o700)
        probe.rmdir()
    except OSError as exc:
        try:
            probe.rmdir()
        except OSError:
            pass
        raise ConfigDenial(
            "CrossAudit could not create a project in that folder. Choose a writable "
            "folder or update its Finder permissions",
            issue="workspace_permission", action="choose_workspace") from exc

    support.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = _settings_path(support)
    tmp = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
    known = list(known_workspaces(support))
    if root not in known:
        known.append(root)
    body = json.dumps({"version": 2, "workspace": str(root),
                       "workspaces": [str(item) for item in known]},
                      indent=2) + "\n"
    try:
        tmp.write_text(body, encoding="utf-8", newline="\n")
        os.chmod(tmp, 0o600)
        tmp.replace(path)
        os.chmod(path, 0o600)
    except OSError as exc:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise ConfigDenial(
            "CrossAudit could not save the workspace choice. Check access to the "
            "application support folder and try again",
            issue="workspace_settings", action="choose_workspace") from exc
    os.environ["CROSSAUDIT_WORKSPACE_ROOT"] = str(root)
    return root
