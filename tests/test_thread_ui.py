"""First-class thread management: rename / archive / unarchive / duplicate.

These exercise the thin transport shell (console/server.py) and the static UI
shell (console/page.py) that were added on top of the already-tested service
layer in console/chats.py.  The service invariants themselves (tombstone,
git-trailer isolation, never-fork-history) live in tests/test_chats.py; here we
assert only that the HTTP boundary is gated exactly like its /api/chats/*
siblings, calls the right service method, and surfaces a ConfigDenial cleanly
instead of corrupting state — and that the sidebar carries the new controls.
"""
from __future__ import annotations

import json
import subprocess
import threading
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

import pytest

from crossaudit.console.page import PAGE


@dataclass
class Console:
    url: str
    cfg: object
    root: Path


@pytest.fixture()
def console(tmp_path: Path):
    from crossaudit.config import load
    from crossaudit.console import serve

    root = tmp_path / "proj"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "lab@example.invalid"],
                   cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Lab"], cwd=root, check=True)
    (root / "AUDIT_RULES.md").write_text("### CA-X-001\n**BLOCKER.** be exact\n\nx\n")
    (root / "crossaudit.yml").write_text(
        "version: 1\nscience_repo: t/p\nconstitution: AUDIT_RULES.md\n"
        "auditor: {vendor: openai, provider: openai_compat, model: m,"
        " key_env: CROSSAUDIT_AUDITOR_KEY}\ngenerator: {vendor: anthropic}\n"
        "ledger: {dir: cycles}\nstate: {dir: .crossaudit}\n"
        "checks: [parseable]\n")
    cfg = load(root / "crossaudit.yml")
    url, httpd = serve(cfg, port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield Console(url=url, cfg=cfg, root=root)
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()


def fetch(url: str, **headers):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, r.read().decode(), dict(r.headers)


def post_json_to(console: Console, path: str, payload: dict):
    url = console.url.replace("/?t=", f"{path}?t=")
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as response:
        return response.status, json.loads(response.read()), dict(response.headers)


def rejected(call):
    try:
        call()
    except urllib.error.HTTPError as error:
        try:
            return error.code, error.read(), dict(error.headers)
        finally:
            error.close()
    raise AssertionError("HTTP request unexpectedly succeeded")


def state_of(console: Console) -> dict:
    _, body, _ = fetch(console.url.replace("/?t=", "/api/state?t="))
    return json.loads(body)


def new_chat(console: Console, title: str = "New chat") -> dict:
    status, created, _ = post_json_to(console, "/api/chats/new", {"title": title})
    assert status == 200
    return created["chat"]


# --------------------------------------------------------------- endpoints
def test_rename_endpoint_calls_the_service_and_persists_the_title(console):
    chat = new_chat(console, "First draft")
    status, renamed, _ = post_json_to(
        console, "/api/chats/rename",
        {"chat_id": chat["id"], "title": "Quarterly analysis"})
    assert status == 200
    assert renamed["chat"]["id"] == chat["id"]
    assert renamed["chat"]["title"] == "Quarterly analysis"

    row = next(item for item in state_of(console)["chats"]["items"]
               if item["id"] == chat["id"])
    assert row["title"] == "Quarterly analysis"


def test_archive_then_unarchive_round_trips_through_the_endpoints(console):
    keep = new_chat(console, "Active work")
    shelved = new_chat(console, "Old exploration")

    status, archived, _ = post_json_to(
        console, "/api/chats/archive", {"chat_id": shelved["id"]})
    assert status == 200 and archived["chat"]["archived"] is True

    chats = state_of(console)["chats"]
    assert {row["id"] for row in chats["items"]} == {keep["id"]}
    assert {row["id"] for row in chats["archived"]} == {shelved["id"]}

    status, restored, _ = post_json_to(
        console, "/api/chats/unarchive", {"chat_id": shelved["id"]})
    assert status == 200 and restored["chat"]["archived"] is False

    chats = state_of(console)["chats"]
    assert {row["id"] for row in chats["items"]} == {keep["id"], shelved["id"]}
    assert chats["archived"] == []


def test_duplicate_endpoint_forks_a_distinct_thread_without_git_history(console):
    from crossaudit.console.streams import _chat_map

    source = new_chat(console, "Template task")
    # Give the source real committed evidence carrying its trailer.
    target = console.root / "experiments" / "source-output.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("source work\n")
    subprocess.run(["git", "add", str(target.relative_to(console.root))],
                   cwd=console.root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "deliver source (round 1)",
                    "-m", f"CrossAudit-Chat: {source['id']}"],
                   cwd=console.root, check=True)

    status, copy, _ = post_json_to(
        console, "/api/chats/duplicate", {"chat_id": source["id"]})
    assert status == 200
    fork = copy["chat"]
    assert fork["id"] != source["id"]           # a fresh stable id
    assert fork["title"] == "Template task"      # inherited navigation identity
    assert fork["pinned"] is False and fork["archived"] is False

    ids = {row["id"] for row in state_of(console)["chats"]["items"]}
    assert {source["id"], fork["id"]} <= ids

    # The immutable trailer evidence still points only at the source thread:
    # duplication forked navigation, never the audit ledger.
    associations = _chat_map(console.root)
    assert source["id"] in associations.values()
    assert fork["id"] not in associations.values()


def test_archived_thread_is_excluded_from_active_count_and_shows_no_running_badge(
        console):
    active = new_chat(console, "Active")
    shelved = new_chat(console, "Shelved")
    post_json_to(console, "/api/chats/archive", {"chat_id": shelved["id"]})

    chats = state_of(console)["chats"]
    # The active list — the one projects.snapshot counts as "chats" — omits it.
    assert [row["id"] for row in chats["items"]] == [active["id"]]
    archived_row = next(row for row in chats["archived"]
                        if row["id"] == shelved["id"])
    # An archived thread must never surface a live running badge.
    assert archived_row.get("status") != "running"


def test_a_duplicated_thread_starts_empty_and_active_via_the_endpoint(console):
    source = new_chat(console, "Seed")
    post_json_to(console, "/api/chats/pin", {"chat_id": source["id"], "pinned": True})
    _, copy, _ = post_json_to(
        console, "/api/chats/duplicate", {"chat_id": source["id"]})
    # Duplicate never inherits placement: it is a new, active, unpinned thread.
    assert copy["chat"]["pinned"] is False
    assert copy["chat"]["archived"] is False


# --------------------------------------------------------------- gating
@pytest.mark.parametrize("path", [
    "/api/chats/rename", "/api/chats/archive",
    "/api/chats/unarchive", "/api/chats/duplicate"])
def test_each_new_endpoint_needs_the_token_like_everything_else(console, path):
    base = console.url.split("?")[0].rstrip("/")
    req = urllib.request.Request(
        base + path, data=b"{}", method="POST",
        headers={"content-type": "application/json"})
    code, _body, _headers = rejected(
        lambda: urllib.request.urlopen(req, timeout=5))
    assert code == 403                              # bare request: forbidden


def test_an_unlisted_chat_action_has_no_route(console):
    code, _body, _headers = rejected(
        lambda: post_json_to(console, "/api/chats/bogus", {"chat_id": "x"}))
    assert code == 404                              # off the allowlist: no route


@pytest.mark.parametrize("path", [
    "/api/chats/rename", "/api/chats/archive",
    "/api/chats/unarchive", "/api/chats/duplicate"])
def test_lifecycle_endpoints_surface_the_tombstone_denial_without_corruption(
        console, path):
    """A tombstoned chat refuses every lifecycle op at the service; the endpoint
    must relay that ConfigDenial as a clean 400, not a 500 or silent success."""
    chat = new_chat(console, "Doomed")
    status, _deleted, _ = post_json_to(
        console, "/api/chats/delete", {"chat_id": chat["id"]})
    assert status == 200

    body = {"chat_id": chat["id"], "title": "Nope"}
    code, raw, _headers = rejected(lambda: post_json_to(console, path, body))
    assert code == 400
    payload = json.loads(raw)
    assert payload["denied"] is True and "deleted" in payload["reason"]

    # State is unchanged: the tombstoned chat did not reappear anywhere.
    chats = state_of(console)["chats"]
    seen = {row["id"] for row in chats["items"]} | {
        row["id"] for row in chats["archived"]}
    assert chat["id"] not in seen


def test_malformed_chat_id_is_refused_by_the_endpoint(console):
    code, raw, _headers = rejected(lambda: post_json_to(
        console, "/api/chats/archive", {"chat_id": "../escape"}))
    assert code == 400
    assert "invalid" in json.loads(raw)["reason"]


# --------------------------------------------------------------- static UI
def test_page_carries_the_new_thread_controls_and_archived_section():
    for text in (
        # Endpoints wired through the existing api(path,body) helper.
        "/api/chats/rename", "/api/chats/archive",
        "/api/chats/unarchive", "/api/chats/duplicate",
        # A single per-row overflow trigger (kept beside the pin quick-toggle)
        # opens one shared menu carrying every secondary action.
        "data-chat-menu-open", "More chat actions", 'id="chat-menu"',
        'role="menu"', 'aria-haspopup="menu"',
        'data-chat-menu="rename"', 'data-chat-menu="duplicate"',
        'data-chat-menu="pin"', 'data-chat-menu="archive"',
        'data-chat-menu="delete"',
        # Archived section + its unarchive affordance.
        "data-unarchive-chat", "data-archived-toggle",
        'id="archived-list"', "archived-toggle", "Archived",
        # Rename dialog shell.
        'id="rename-chat-modal"', 'id="rename-chat-title"', "Rename chat",
        "Duplicate chat", "Archive chat", "Unarchive chat",
    ):
        assert text in PAGE
    # The five bare per-row action buttons were consolidated away.
    for gone in ("data-rename-chat", "data-duplicate-chat", "data-archive-chat"):
        assert gone not in PAGE


def test_new_strings_have_a_chinese_display_layer():
    for chinese in ("重命名对话", "复制对话", "归档对话", "取消归档对话",
                    "已归档", "保存名称", "对话标题"):
        assert chinese in PAGE


def test_static_ui_ids_stay_unique_and_the_rename_dialog_is_named():
    class _Contract(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.ids: list[str] = []
            self.dialogs: list[dict] = []

        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            if values.get("id"):
                self.ids.append(str(values["id"]))
            if values.get("role") == "dialog":
                self.dialogs.append(values)

    parser = _Contract()
    parser.feed(PAGE)
    assert [v for v, n in Counter(parser.ids).items() if n > 1] == []
    known = set(parser.ids)
    rename = next(d for d in parser.dialogs
                  if d.get("id") == "rename-chat-modal")
    assert rename.get("aria-modal") == "true"
    assert rename.get("aria-labelledby") in known
