from __future__ import annotations

import json
import os
import subprocess

import pytest

from crossaudit.console import chats
from crossaudit.errors import ConfigDenial


def test_project_contains_independent_chats_and_only_navigation_metadata(cfg):
    first = chats.create(cfg)
    second = chats.create(cfg, "Independent task")
    updated = chats.touch(cfg, first["id"], "Review the quarterly report in PDF")

    assert first["id"] != second["id"]
    assert updated["title"] == "Review the quarterly report in PDF"
    state = chats.snapshot(cfg)
    assert {row["id"] for row in state["items"]} == {first["id"], second["id"]}
    assert all(row.keys() >= {"id", "title", "pinned", "created", "updated"}
               for row in state["items"])
    raw = (cfg.root / cfg.state_dir / chats.STATE_FILE).read_text()
    assert "quarterly report" in raw
    assert "PDF" in raw
    assert "conversation" not in raw
    if os.name != "nt":
        assert (cfg.root / cfg.state_dir / chats.STATE_FILE).stat().st_mode & 0o777 == 0o600


def test_project_and_chat_pins_are_persistent_and_sorted_first(cfg):
    older = chats.create(cfg, "Older")
    newer = chats.create(cfg, "Newer")
    chats.set_chat_pin(cfg, older["id"], True)
    assert chats.set_project_pin(cfg, True) is True

    state = chats.snapshot(cfg)
    assert state["project_pinned"] is True
    assert state["items"][0]["id"] == older["id"]
    assert state["items"][0]["pinned"] is True
    assert {row["id"] for row in state["items"]} == {older["id"], newer["id"]}


def test_legacy_project_history_is_migrated_without_rewriting_evidence(cfg):
    ledger = cfg.root / cfg.ledger_dir
    ledger.mkdir(exist_ok=True)
    route = ledger / "routing.jsonl"
    route.write_text('{"utterance":"old"}\n')

    state = chats.snapshot(cfg)
    history = next(row for row in state["items"] if row["id"] == "history")
    assert history["title"] == "Project history"
    assert not (cfg.root / cfg.state_dir / chats.STATE_FILE).exists()
    chats.set_chat_pin(cfg, "history", True)
    assert route.read_text() == '{"utterance":"old"}\n'


def test_unknown_or_malformed_chat_ids_are_refused(cfg):
    with pytest.raises(ConfigDenial, match="invalid"):
        chats.touch(cfg, "../escape", "message")
    with pytest.raises(ConfigDenial, match="no longer exists"):
        chats.touch(cfg, "0" * 16, "message")


def test_corrupt_navigation_state_fails_closed(cfg):
    path = cfg.root / cfg.state_dir / chats.STATE_FILE
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(["not", "an", "object"]))
    with pytest.raises(ConfigDenial, match="invalid structure"):
        chats.snapshot(cfg)


def test_git_trailers_keep_two_chat_outputs_in_one_project_separate(cfg):
    from crossaudit.console.streams import _commits, generator_stream

    ids = [chats.create(cfg, title)["id"] for title in ("First", "Second")]
    for number, chat_id in enumerate(ids, 1):
        target = cfg.root / "experiments" / f"chat-{number}.md"
        target.write_text(f"output {number}\n")
        subprocess.run(["git", "add", str(target.relative_to(cfg.root))],
                       cwd=cfg.root, check=True)
        subprocess.run([
            "git", "commit", "-q", "-m", f"deliver {number} (round 1)",
            "-m", f"CrossAudit-Chat: {chat_id}"], cwd=cfg.root, check=True)

    commits = _commits(cfg.root)
    delivered = [row for row in commits if row["subject"].startswith("deliver")]
    assert [row["chat_id"] for row in delivered] == ids
    stream = generator_stream(cfg, [], commits)
    chat_rows = [row for row in stream if row["kind"] == "generator"
                 and row["summary"].startswith("deliver")]
    assert {row["chat_id"] for row in chat_rows} == set(ids)
    assert {row["files"][0] for row in chat_rows} == {
        "experiments/chat-1.md", "experiments/chat-2.md"}

    # Navigation metadata is local convenience; immutable Git evidence can
    # recover the Chat if that metadata is deleted or restored from backup.
    (cfg.root / cfg.state_dir / chats.STATE_FILE).unlink()
    recovered = chats.touch(cfg, ids[0], "Continue this recovered task")
    assert recovered["id"] == ids[0]
    assert recovered["title"] == "Recovered chat"
