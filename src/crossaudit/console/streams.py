"""Reconstructing the two conversations from the ledger.

The console shows the generator and the auditor as two windows, but neither of
them is a chat log: what exists is commits, reports, receipts and routing
decisions. This module reads those back into the two streams a person would
recognise as conversations, which is the only honest way to render them —
nothing here is stored for the console's benefit.

Where the user's own words belong to one side, they appear in that window: a
sentence routed to the work shows in the generator's stream, a sentence about
the standards in the auditor's. That is the black box made legible — you see
which window heard you, and how sure the router was.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..config import Config
from ..dispute import DISPUTES_LOG, parse_findings
from ..router import history as routing_history
from .chats import LEGACY_CHAT_ID

GENERATOR_LANES = {"generator", "project"}
AUDITOR_LANES = {"auditor", "amendment", "dispute", "resolve", "query"}
ROUND_RE = re.compile(r"\(round (\d+)\)\s*$")
NON_GENERATOR_COMMITS = (
    "audit report",
    "audit receipt",
    "amend rules",
    "dispute ",
    "crossaudit: initialize supervised project",
)

KIND_BY_SUFFIX = {
    ".csv": "CSV data",
    ".json": "JSON data",
    ".md": "Markdown",
    ".docx": "Word document",
    ".pdf": "PDF document",
    ".py": "Python source",
    ".ts": "TypeScript source",
    ".tsx": "TypeScript source",
    ".js": "JavaScript source",
    ".jsx": "JavaScript source",
    ".txt": "Text",
    ".yaml": "YAML data",
    ".yml": "YAML data",
}


def _commits(root: Path, limit: int = 200) -> list[dict]:
    import subprocess

    # The record separator leads each entry: with --name-only the file list
    # follows its commit's header, so a trailing separator would put every
    # commit's files at the head of the next commit's chunk.
    out = subprocess.run(
        ["git", "log", f"-{limit}",
         "--format=%x1e%H%x1f%ct%x1f%s%x1f%(trailers:key=CrossAudit-Chat,valueonly)",
         "--name-only"],
        cwd=str(root), capture_output=True, text=True)
    if out.returncode != 0:
        return []
    rows = []
    for chunk in out.stdout.split("\x1e"):
        if not chunk.strip():
            continue
        head, _, files = chunk.partition("\n")
        parts = head.split("\x1f")
        if len(parts) < 4:
            continue
        rows.append({"sha": parts[0], "t": int(parts[1]), "subject": parts[2],
                     "chat_id": parts[3].strip() or LEGACY_CHAT_ID,
                     "files": [f for f in files.split("\n") if f.strip()]})
    return rows[::-1]


def _chat_map(root: Path) -> dict[str, str]:
    """All durable Chat associations; unlike the visible stream, never capped."""
    import subprocess

    result = subprocess.run(
        ["git", "log", "--format=%H%x1f%(trailers:key=CrossAudit-Chat,valueonly)"],
        cwd=str(root), capture_output=True, text=True)
    if result.returncode != 0:
        return {}
    rows = {}
    for line in result.stdout.splitlines():
        sha, separator, chat_id = line.partition("\x1f")
        if separator:
            rows[sha] = chat_id.strip() or LEGACY_CHAT_ID
    return rows


def _artifact(cfg: Config, relative: str) -> dict:
    """Small, non-sensitive metadata for a file chip in the conversation."""
    path = Path(relative)
    candidate = cfg.root / path
    available = candidate.is_file() and not candidate.is_symlink()
    try:
        size = candidate.stat().st_size if available else None
    except OSError:
        available, size = False, None
    suffix = path.suffix.lower()
    return {
        "path": relative,
        "name": path.name,
        "extension": suffix.removeprefix(".").upper() or "FILE",
        "kind": KIND_BY_SUFFIX.get(suffix, "File"),
        "bytes": size,
        "available": available,
    }


def generator_stream(cfg: Config, routing: list[dict],
                     commits: list[dict] | None = None) -> list[dict]:
    """What the generator did, plus the user's words that were meant for it."""
    stream: list[dict] = []
    scope = tuple((cfg.scope_dirs or []))
    for c in commits if commits is not None else _commits(cfg.root):
        work = [f for f in c["files"]
                if not scope or f.split("/", 1)[0] in scope]
        if not work or c["subject"].startswith(NON_GENERATOR_COMMITS):
            continue
        m = ROUND_RE.search(c["subject"])
        stream.append({
            "kind": "generator", "t": c["t"],
            "chat_id": c["chat_id"],
            "sha": c["sha"],
            "summary": ROUND_RE.sub("", c["subject"]).strip(),
            "round": int(m.group(1)) if m else None,
            "files": work,
            "artifacts": [_artifact(cfg, path) for path in work],
            "notes": "",
        })
    for r in routing:
        if r.get("lane") in GENERATOR_LANES:
            stream.append({**r, "kind": "you",
                           "chat_id": str(r.get("chat_id") or LEGACY_CHAT_ID)})
    return sorted(stream, key=lambda m: m["t"])[-40:]


def auditor_stream(cfg: Config, routing: list[dict],
                   commits: list[dict] | None = None,
                   commit_chats: dict[str, str] | None = None) -> list[dict]:
    """Every verdict, every dispute ruling, and the user's words about standards."""
    stream: list[dict] = []
    ledger = cfg.root / cfg.ledger_dir
    commit_rows = commits if commits is not None else _commits(cfg.root)
    commit_chats = commit_chats or {row["sha"]: row["chat_id"]
                                    for row in commit_rows}
    for report in ledger.glob("*/report.md"):
        text = report.read_text(encoding="utf-8")
        verdict = "?"
        m = re.search(r"\|\s*verdict\s*\|\s*\*\*(\w+)\*\*", text)
        if m:
            verdict = m.group(1)
        round_match = re.search(r"-r(\d+)$", report.parent.name)
        stream.append({
            "kind": "auditor", "t": int(report.stat().st_mtime), "verdict": verdict,
            "chat_id": next((chat for sha, chat in commit_chats.items()
                              if sha.startswith(report.parent.name.split("-r", 1)[0])),
                             LEGACY_CHAT_ID),
            "round": int(round_match.group(1)) if round_match else 1,
            "findings": [{"severity": f.severity, "rule": f.rule,
                          "artifact": f.artifact, "observation": f.observation[:400]}
                         for f in parse_findings(text)],
        })
    disputes = ledger / DISPUTES_LOG
    if disputes.is_file():
        for line in disputes.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            stream.append({
                "kind": "auditor", "t": d.get("t", 0), "verdict": d["ruling"],
                "chat_id": str(d.get("chat_id") or LEGACY_CHAT_ID),
                "findings": [{"severity": "dispute", "rule": d["rule"],
                              "artifact": d["artifact"],
                              "observation": d["reasoning"]}],
            })
    for r in routing:
        if r.get("lane") in AUDITOR_LANES:
            stream.append({**r, "kind": "you",
                           "chat_id": str(r.get("chat_id") or LEGACY_CHAT_ID)})
            prefix = "answered by auditor: "
            if r.get("lane") == "auditor" and str(r.get("executed", "")).startswith(prefix):
                stream.append({"kind": "auditor_chat", "t": r.get("t", 0),
                               "chat_id": str(r.get("chat_id") or LEGACY_CHAT_ID),
                               "response": r["executed"][len(prefix):],
                               "addressed_to": "auditor"})
    return sorted(stream, key=lambda m: (m["t"], m.get("round", 0)))[-40:]


def bundle(cfg: Config) -> tuple[list[dict], list[dict], dict[str, str]]:
    """Build both streams and the commit association map with one Git read."""
    routing = routing_history(cfg.root / cfg.ledger_dir / "routing.jsonl", 60)
    commits = _commits(cfg.root)
    chat_map = _chat_map(cfg.root)
    return (generator_stream(cfg, routing, commits),
            auditor_stream(cfg, routing, commits, chat_map), chat_map)


def both(cfg: Config) -> tuple[list[dict], list[dict]]:
    generator, auditor, _chat_map = bundle(cfg)
    return generator, auditor


def commit_chat_map(cfg: Config) -> dict[str, str]:
    """Full audited commit SHA to chat association from immutable trailers."""
    return _chat_map(cfg.root)
