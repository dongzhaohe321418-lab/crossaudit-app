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


def test_rename_sets_an_explicit_title_independent_of_the_first_message(cfg):
    row = chats.create(cfg, "First draft")
    renamed = chats.rename(cfg, row["id"], "Quarterly analysis")

    assert renamed["id"] == row["id"]
    assert renamed["title"] == "Quarterly analysis"
    assert renamed["updated"] >= row["updated"]
    # A later message no longer overwrites a deliberately chosen title.
    touched = chats.touch(cfg, row["id"], "some unrelated follow-up question")
    assert touched["title"] == "Quarterly analysis"


def test_archive_hides_a_thread_from_navigation_but_keeps_it_recoverable(cfg):
    keep = chats.create(cfg, "Active work")
    shelved = chats.create(cfg, "Old exploration")
    chats.set_chat_pin(cfg, shelved["id"], True)

    archived = chats.archive(cfg, shelved["id"])
    assert archived["archived"] is True
    # Archiving is the opposite intent to pinning, so it clears the pin.
    assert archived["pinned"] is False

    state = chats.snapshot(cfg)
    assert {row["id"] for row in state["items"]} == {keep["id"]}
    assert {row["id"] for row in state["archived"]} == {shelved["id"]}

    restored = chats.unarchive(cfg, shelved["id"])
    assert restored["archived"] is False
    back = chats.snapshot(cfg)
    assert {row["id"] for row in back["items"]} == {keep["id"], shelved["id"]}
    assert back["archived"] == []


def test_duplicate_forks_identity_into_a_fresh_empty_thread(cfg):
    source = chats.create(cfg, "Template task")
    chats.set_chat_pin(cfg, source["id"], True)
    copy = chats.duplicate(cfg, source["id"])

    # A new stable id, the inherited title, and none of the source's placement:
    # duplication never copies Git history and starts active and unpinned.
    assert copy["id"] != source["id"]
    assert copy["title"] == "Template task"
    assert copy["pinned"] is False
    assert copy["archived"] is False
    ids = {row["id"] for row in chats.snapshot(cfg)["items"]}
    assert {source["id"], copy["id"]} <= ids


def test_deleted_threads_refuse_every_lifecycle_operation(cfg):
    row = chats.create(cfg, "Doomed")
    chats.delete(cfg, row["id"])
    for operation in (
            lambda: chats.rename(cfg, row["id"], "Nope"),
            lambda: chats.archive(cfg, row["id"]),
            lambda: chats.unarchive(cfg, row["id"]),
            lambda: chats.duplicate(cfg, row["id"]),
    ):
        with pytest.raises(ConfigDenial, match="deleted"):
            operation()


def test_ensure_deletable_guards_a_busy_thread_without_runtime_coupling(cfg):
    row = chats.create(cfg, "Running")
    # No live work: deletion is permitted.
    chats.ensure_deletable(row["id"])

    with pytest.raises(ConfigDenial, match="task running"):
        chats.ensure_deletable(row["id"], running_chat_id=row["id"])
    with pytest.raises(ConfigDenial, match="remote compute running"):
        chats.ensure_deletable(row["id"], active_compute_chat_ids=[row["id"]])

    # A blank runtime chat_id canonicalises to the legacy project history, so it
    # only blocks deletion of that history — never an unrelated thread.
    chats.ensure_deletable(row["id"], running_chat_id="")
    with pytest.raises(ConfigDenial, match="task running"):
        chats.ensure_deletable(chats.LEGACY_CHAT_ID, running_chat_id="")


def test_duplicate_starts_empty_and_never_forks_git_evidence(cfg):
    from crossaudit.console.streams import _chat_map

    source = chats.create(cfg, "Has history")
    target = cfg.root / "experiments" / "source-output.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("source work\n")
    subprocess.run(["git", "add", str(target.relative_to(cfg.root))],
                   cwd=cfg.root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "deliver source (round 1)",
                    "-m", f"CrossAudit-Chat: {source['id']}"], cwd=cfg.root, check=True)

    copy = chats.duplicate(cfg, source["id"])
    associations = _chat_map(cfg.root)
    # The immutable trailer evidence still points only at the source thread.
    assert source["id"] in associations.values()
    assert copy["id"] not in associations.values()


def test_lifecycle_operations_reject_malformed_ids(cfg):
    for operation in (
            lambda: chats.rename(cfg, "../escape", "x"),
            lambda: chats.archive(cfg, "../escape"),
            lambda: chats.unarchive(cfg, "../escape"),
            lambda: chats.duplicate(cfg, "../escape"),
    ):
        with pytest.raises(ConfigDenial, match="invalid"):
            operation()
