"""Local Project -> Chat navigation state.

Projects are real user-selected folders and Git repositories.  Chats are
lightweight task threads inside one project; they do not duplicate the working
tree or weaken the single audit ledger.  This file stores navigation metadata
only (title, timestamps and pins) in the already-gitignored controller folder.
Conversation content remains reconstructable from committed routing, work and
audit evidence.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import threading
import time
from pathlib import Path

from ..config import Config
from ..errors import ConfigDenial

STATE_FILE = "ui-state.json"
LEGACY_CHAT_ID = "history"
CHAT_ID = re.compile(r"(?:history|[a-f0-9]{16})")
_LOCK = threading.RLock()


def _path(cfg: Config) -> Path:
    return cfg.root / cfg.state_dir / STATE_FILE


def _legacy_exists(cfg: Config) -> bool:
    ledger = cfg.root / cfg.ledger_dir
    return ((ledger / "routing.jsonl").is_file()
            or any(ledger.glob("*/report.md")))


def _has_evidence(cfg: Config, chat_id: str) -> bool:
    """A deleted UI-state file must not orphan committed Chat evidence."""
    routing = cfg.root / cfg.ledger_dir / "routing.jsonl"
    if routing.is_file():
        try:
            for line in routing.read_text(encoding="utf-8").splitlines():
                if line.strip() and json.loads(line).get("chat_id") == chat_id:
                    return True
        except (OSError, json.JSONDecodeError):
            pass
    result = subprocess.run(
        ["git", "log", "--format=%(trailers:key=CrossAudit-Chat,valueonly)"],
        cwd=str(cfg.root), capture_output=True, text=True)
    return result.returncode == 0 and chat_id in result.stdout.split()


def _default() -> dict:
    return {"version": 1, "project_pinned": False, "chats": []}


def _read(cfg: Config) -> dict:
    path = _path(cfg)
    if not path.is_file():
        return _default()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigDenial(f"chat navigation state is unreadable: {exc}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("chats", []), list):
        raise ConfigDenial("chat navigation state has an invalid structure")
    rows = []
    for row in raw.get("chats", []):
        if not isinstance(row, dict) or not CHAT_ID.fullmatch(str(row.get("id", ""))):
            continue
        rows.append({
            "id": str(row["id"]),
            "title": str(row.get("title") or "Untitled chat")[:120],
            "pinned": bool(row.get("pinned")),
            "created": int(row.get("created", 0) or 0),
            "updated": int(row.get("updated", 0) or 0),
        })
    return {"version": 1, "project_pinned": bool(raw.get("project_pinned")),
            "chats": rows}


def _write(cfg: Config, state: dict) -> None:
    path = _path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    body = json.dumps(state, ensure_ascii=False, sort_keys=True, indent=1) + "\n"
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(body)
        os.replace(temp, path)
        if os.name != "nt":
            path.chmod(0o600)
    finally:
        temp.unlink(missing_ok=True)


def _title(text: str) -> str:
    clean = " ".join(text.split()).strip()
    return (clean[:57] + "…") if len(clean) > 58 else (clean or "New chat")


def _find(state: dict, chat_id: str) -> dict | None:
    return next((row for row in state["chats"] if row["id"] == chat_id), None)


def create(cfg: Config, title: str = "New chat") -> dict:
    with _LOCK:
        state = _read(cfg)
        now = int(time.time())
        row = {"id": secrets.token_hex(8), "title": _title(title), "pinned": False,
               "created": now, "updated": now}
        state["chats"].append(row)
        _write(cfg, state)
        return dict(row)


def touch(cfg: Config, chat_id: str, message: str) -> dict:
    """Resolve/create the thread receiving one user message and update its title."""
    with _LOCK:
        state = _read(cfg)
        now = int(time.time())
        if chat_id:
            if not CHAT_ID.fullmatch(chat_id):
                raise ConfigDenial("chat id is invalid")
            row = _find(state, chat_id)
            if row is None and ((chat_id == LEGACY_CHAT_ID and _legacy_exists(cfg))
                                or _has_evidence(cfg, chat_id)):
                row = {"id": chat_id,
                       "title": ("Project history" if chat_id == LEGACY_CHAT_ID
                                 else "Recovered chat"), "pinned": False,
                       "created": now, "updated": now}
                state["chats"].append(row)
            if row is None:
                raise ConfigDenial("that chat no longer exists; create a new chat")
        else:
            row = {"id": secrets.token_hex(8), "title": _title(message),
                   "pinned": False, "created": now, "updated": now}
            state["chats"].append(row)
        if row["title"] in {"New chat", "Untitled chat"}:
            row["title"] = _title(message)
        row["updated"] = now
        _write(cfg, state)
        return dict(row)


def set_chat_pin(cfg: Config, chat_id: str, pinned: bool) -> dict:
    with _LOCK:
        if not CHAT_ID.fullmatch(chat_id):
            raise ConfigDenial("chat id is invalid")
        state = _read(cfg)
        row = _find(state, chat_id)
        if row is None and ((chat_id == LEGACY_CHAT_ID and _legacy_exists(cfg))
                            or _has_evidence(cfg, chat_id)):
            now = int(time.time())
            row = {"id": chat_id,
                   "title": ("Project history" if chat_id == LEGACY_CHAT_ID
                             else "Recovered chat"), "pinned": False,
                   "created": now, "updated": now}
            state["chats"].append(row)
        if row is None:
            raise ConfigDenial("that chat no longer exists")
        row["pinned"] = bool(pinned)
        _write(cfg, state)
        return dict(row)


def set_project_pin(cfg: Config, pinned: bool) -> bool:
    with _LOCK:
        state = _read(cfg)
        state["project_pinned"] = bool(pinned)
        _write(cfg, state)
        return state["project_pinned"]


def project_pinned(cfg: Config) -> bool:
    with _LOCK:
        return bool(_read(cfg)["project_pinned"])


def snapshot(cfg: Config, known_chat_ids=()) -> dict:
    """Return sorted navigation metadata, including read-only legacy migration."""
    with _LOCK:
        state = _read(cfg)
        rows = [dict(row) for row in state["chats"]]
        known = {str(item) for item in known_chat_ids if CHAT_ID.fullmatch(str(item))}
        if _legacy_exists(cfg):
            known.add(LEGACY_CHAT_ID)
        existing = {row["id"] for row in rows}
        now = int(time.time())
        for chat_id in sorted(known - existing):
            rows.append({"id": chat_id,
                         "title": ("Project history" if chat_id == LEGACY_CHAT_ID
                                   else "Recovered chat"),
                         "pinned": False, "created": now, "updated": now})
        rows.sort(key=lambda row: (not row["pinned"], -row["updated"], row["id"]))
        return {"project_pinned": bool(state["project_pinned"]), "items": rows}
