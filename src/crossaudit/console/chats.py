"""Threads: the durable identity of a conversation inside one project.

Projects are real user-selected folders and Git repositories.  A **Thread** is a
lightweight conversation inside one project; it does not duplicate the working
tree or weaken the single audit ledger.  A thread's durable anchor is the
``CrossAudit-Chat`` commit trailer that ties work and audit evidence to it; this
file adds only the navigation metadata that trailer cannot carry (title, pin,
archive state, timestamps) plus a private tombstone list.  Conversation content
remains reconstructable from committed routing, work and audit evidence.

The three sources that together give a thread its identity — the navigation
record here, the immutable Git trailer, and the tombstone — are reconciled in
exactly one place (:func:`_resolve`), and every lifecycle operation (create,
rename, pin, archive/unarchive, duplicate, soft-delete) is a method on this
service.  Deleting a thread records a tombstone; it never rewrites history.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from ..config import Config
from ..errors import ConfigDenial

STATE_FILE = "ui-state.json"
LEGACY_CHAT_ID = "history"
CHAT_ID = re.compile(r"(?:history|[a-f0-9]{16})")
_LOCK = threading.RLock()
_UNSET = object()


def canonical_id(value: object) -> str:
    """The stable thread id for a value that may be blank.

    Commits made before threads existed carry no trailer; everywhere a thread id
    is read from durable evidence it may be empty, and the single honest answer
    for "which thread does this belong to" is the legacy project history.
    """
    text = str(value or "").strip()
    return text or LEGACY_CHAT_ID


@dataclass
class Thread:
    """The single authoritative record of a conversation inside a project.

    Fields here are the *only* thing a thread owns of its own; files, config,
    Git, constitution and provider routes all belong to the project and are
    shared by every thread in it.
    """

    id: str
    title: str = "New chat"
    pinned: bool = False
    archived: bool = False
    created: int = 0
    updated: int = 0

    @classmethod
    def create(cls, title: str, now: int) -> "Thread":
        return cls(id=secrets.token_hex(8), title=_title(title),
                   created=now, updated=now)

    @classmethod
    def recovered(cls, chat_id: str, now: int) -> "Thread":
        """Materialise a thread known only from durable Git/legacy evidence."""
        title = "Project history" if chat_id == LEGACY_CHAT_ID else "Recovered chat"
        return cls(id=chat_id, title=title, created=now, updated=now)

    @classmethod
    def parse(cls, raw: object) -> "Thread | None":
        """Read a stored row, returning ``None`` for anything unrecognisable."""
        if not isinstance(raw, dict) or not CHAT_ID.fullmatch(str(raw.get("id", ""))):
            return None
        return cls(
            id=str(raw["id"]),
            title=str(raw.get("title") or "Untitled chat")[:120],
            pinned=bool(raw.get("pinned")),
            archived=bool(raw.get("archived")),
            created=int(raw.get("created", 0) or 0),
            updated=int(raw.get("updated", 0) or 0),
        )

    def as_row(self) -> dict:
        return {"id": self.id, "title": self.title, "pinned": self.pinned,
                "archived": self.archived, "created": self.created,
                "updated": self.updated}


def _path(cfg: Config) -> Path:
    return cfg.root / cfg.state_dir / STATE_FILE


def _legacy_exists(cfg: Config) -> bool:
    ledger = cfg.root / cfg.ledger_dir
    return ((ledger / "routing.jsonl").is_file()
            or any(ledger.glob("*/report.md")))


def _has_evidence(cfg: Config, chat_id: str) -> bool:
    """A deleted UI-state file must not orphan committed Thread evidence."""
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
        cwd=str(cfg.root), capture_output=True, text=True, check=False)
    return result.returncode == 0 and chat_id in result.stdout.split()


def _recoverable(cfg: Config, chat_id: str) -> bool:
    """Whether durable evidence alone can bring a thread back."""
    return ((chat_id == LEGACY_CHAT_ID and _legacy_exists(cfg))
            or _has_evidence(cfg, chat_id))


def _default() -> dict:
    return {"version": 2, "project_pinned": False, "chats": [], "deleted": []}


def _read(cfg: Config) -> dict:
    path = _path(cfg)
    if not path.is_file():
        return _default()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigDenial(f"chat navigation state is unreadable: {exc}") from exc
    if (not isinstance(raw, dict) or not isinstance(raw.get("chats", []), list)
            or not isinstance(raw.get("deleted", []), list)):
        raise ConfigDenial("chat navigation state has an invalid structure")
    rows = []
    for row in raw.get("chats", []):
        thread = Thread.parse(row)
        if thread is not None:
            rows.append(thread.as_row())
    deleted = list(dict.fromkeys(
        str(item) for item in raw.get("deleted", [])
        if CHAT_ID.fullmatch(str(item))))
    return {"version": 2, "project_pinned": bool(raw.get("project_pinned")),
            "chats": rows, "deleted": deleted}


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


def _resolve(cfg: Config, state: dict, chat_id: str, now: int) -> dict | None:
    """Find a thread, recovering it from durable evidence when navigation lost it.

    This is the single meeting point of the three identity sources: the
    navigation record, the immutable ``CrossAudit-Chat`` trailer, and the
    tombstone.  A recovered thread is appended so the caller can act on it; the
    tombstone is honoured by callers, which own the wording of that refusal.
    """
    row = _find(state, chat_id)
    if row is None and _recoverable(cfg, chat_id):
        row = Thread.recovered(chat_id, now).as_row()
        state["chats"].append(row)
    return row


def create(cfg: Config, title: str = "New chat") -> dict:
    with _LOCK:
        state = _read(cfg)
        row = Thread.create(title, int(time.time())).as_row()
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
            if chat_id in state["deleted"]:
                raise ConfigDenial("that chat was deleted; create a new chat")
            row = _resolve(cfg, state, chat_id, now)
            if row is None:
                raise ConfigDenial("that chat no longer exists; create a new chat")
        else:
            row = Thread.create(message, now).as_row()
            state["chats"].append(row)
        if row["title"] in {"New chat", "Untitled chat"}:
            row["title"] = _title(message)
        row["updated"] = now
        _write(cfg, state)
        return dict(row)


def rename(cfg: Config, chat_id: str, title: str) -> dict:
    """Give a thread an explicit title, independent of its first message."""
    with _LOCK:
        if not CHAT_ID.fullmatch(chat_id):
            raise ConfigDenial("chat id is invalid")
        state = _read(cfg)
        if chat_id in state["deleted"]:
            raise ConfigDenial("that chat was deleted")
        now = int(time.time())
        row = _resolve(cfg, state, chat_id, now)
        if row is None:
            raise ConfigDenial("that chat no longer exists")
        row["title"] = _title(title)
        row["updated"] = now
        _write(cfg, state)
        return dict(row)


def set_chat_pin(cfg: Config, chat_id: str, pinned: bool) -> dict:
    with _LOCK:
        if not CHAT_ID.fullmatch(chat_id):
            raise ConfigDenial("chat id is invalid")
        state = _read(cfg)
        if chat_id in state["deleted"]:
            raise ConfigDenial("that chat was deleted")
        row = _resolve(cfg, state, chat_id, int(time.time()))
        if row is None:
            raise ConfigDenial("that chat no longer exists")
        row["pinned"] = bool(pinned)
        _write(cfg, state)
        return dict(row)


def archive(cfg: Config, chat_id: str) -> dict:
    """Hide a thread from the main navigation while keeping it fully recoverable.

    Archiving is non-destructive: the thread, its title and all of its committed
    evidence stay intact.  A pin means "keep this in front of me", so archiving —
    the opposite intent — clears it.
    """
    with _LOCK:
        if not CHAT_ID.fullmatch(chat_id):
            raise ConfigDenial("chat id is invalid")
        state = _read(cfg)
        if chat_id in state["deleted"]:
            raise ConfigDenial("that chat was deleted")
        now = int(time.time())
        row = _resolve(cfg, state, chat_id, now)
        if row is None:
            raise ConfigDenial("that chat no longer exists")
        row["archived"] = True
        row["pinned"] = False
        row["updated"] = now
        _write(cfg, state)
        return dict(row)


def unarchive(cfg: Config, chat_id: str) -> dict:
    """Return an archived thread to the main navigation."""
    with _LOCK:
        if not CHAT_ID.fullmatch(chat_id):
            raise ConfigDenial("chat id is invalid")
        state = _read(cfg)
        if chat_id in state["deleted"]:
            raise ConfigDenial("that chat was deleted")
        now = int(time.time())
        row = _resolve(cfg, state, chat_id, now)
        if row is None:
            raise ConfigDenial("that chat no longer exists")
        row["archived"] = False
        row["updated"] = now
        _write(cfg, state)
        return dict(row)


def duplicate(cfg: Config, chat_id: str) -> dict:
    """Start a fresh thread from an existing one's navigation identity.

    A thread deliberately never copies Git history — duplication, like deletion,
    must not rewrite or fork the audit ledger — and every thread already shares
    the project's files, configuration, constitution and repositories.  The only
    thing a thread owns of its own is this navigation record, so a duplicate is a
    new, empty, active, unpinned thread that inherits the source's title and gets
    its own stable id.
    """
    with _LOCK:
        if not CHAT_ID.fullmatch(chat_id):
            raise ConfigDenial("chat id is invalid")
        state = _read(cfg)
        if chat_id in state["deleted"]:
            raise ConfigDenial("that chat was deleted")
        now = int(time.time())
        source = _resolve(cfg, state, chat_id, now)
        if source is None:
            raise ConfigDenial("that chat no longer exists")
        row = Thread.create(source["title"], now).as_row()
        state["chats"].append(row)
        _write(cfg, state)
        return dict(row)


def ensure_deletable(chat_id: str, *, running_chat_id: object = _UNSET,
                     active_compute_chat_ids=()) -> None:
    """Refuse to delete a thread that still has live work.

    The runtime facts — whether a task is in flight, and which remote jobs are
    still running — are supplied by the caller, so this policy carries no runtime
    or scheduler dependency of its own; only the rule and its wording live here.
    Pass ``running_chat_id`` only when a task is actually running.
    """
    if running_chat_id is not _UNSET and canonical_id(running_chat_id) == chat_id:
        raise ConfigDenial(
            "that chat has a task running; wait for it to finish before deleting")
    if any(canonical_id(cid) == chat_id for cid in active_compute_chat_ids):
        raise ConfigDenial(
            "that chat has remote compute running; cancel or finish it first")


def delete(cfg: Config, chat_id: str) -> dict:
    """Remove one thread from navigation without rewriting audit evidence.

    A thread can point at commits, reports and receipts shared by the project.
    Rewriting that history would weaken the audit ledger, so deletion records a
    private navigation tombstone. Empty threads disappear completely; threads
    with evidence stay recoverable through Git while remaining absent from the UI.
    """
    with _LOCK:
        if not CHAT_ID.fullmatch(chat_id):
            raise ConfigDenial("chat id is invalid")
        state = _read(cfg)
        row = _find(state, chat_id)
        evidence = _recoverable(cfg, chat_id)
        if row is None and chat_id not in state["deleted"] and not evidence:
            raise ConfigDenial("that chat no longer exists")
        title = (row or {}).get(
            "title", "Project history" if chat_id == LEGACY_CHAT_ID else "Deleted chat")
        state["chats"] = [item for item in state["chats"] if item["id"] != chat_id]
        if chat_id not in state["deleted"]:
            state["deleted"].append(chat_id)
        _write(cfg, state)
        return {"id": chat_id, "title": title,
                "evidence_preserved": bool(evidence)}


def set_project_pin(cfg: Config, pinned: bool) -> bool:
    with _LOCK:
        state = _read(cfg)
        state["project_pinned"] = bool(pinned)
        _write(cfg, state)
        return state["project_pinned"]


def project_pinned(cfg: Config) -> bool:
    with _LOCK:
        return bool(_read(cfg)["project_pinned"])


def _order(row: dict) -> tuple:
    return (not row["pinned"], -row["updated"], row["id"])


def snapshot(cfg: Config, known_chat_ids=()) -> dict:
    """Return sorted navigation metadata, including read-only legacy migration.

    ``items`` are the threads shown in the main navigation; ``archived`` holds
    the hidden-but-recoverable ones separately so the two never intermix.
    """
    with _LOCK:
        state = _read(cfg)
        rows = [dict(row) for row in state["chats"]
                if row["id"] not in state["deleted"]]
        known = {str(item) for item in known_chat_ids if CHAT_ID.fullmatch(str(item))}
        if _legacy_exists(cfg):
            known.add(LEGACY_CHAT_ID)
        known.difference_update(state["deleted"])
        existing = {row["id"] for row in rows}
        now = int(time.time())
        for chat_id in sorted(known - existing):
            rows.append(Thread.recovered(chat_id, now).as_row())
        active = sorted((row for row in rows if not row.get("archived")), key=_order)
        archived = sorted((row for row in rows if row.get("archived")), key=_order)
        return {"project_pinned": bool(state["project_pinned"]),
                "items": active, "archived": archived}
