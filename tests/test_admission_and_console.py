"""2.0: what a deployment may claim, and the window that shows it.

The admission tests exist because "enforced" is the word a supervision system is
most tempted to use prematurely. The console tests exist because opening a port
inside a tool that holds API keys is a real attack surface, and the defences
have to be tested as refusals, not described in a docstring.
"""
from __future__ import annotations

import json
import base64
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from crossaudit import admission as adm
from crossaudit.controller import StateStore

FULL_PROTECTION = {
    "reachable": True, "protected": True,
    "required_checks": [adm.CHECK_NAME], "admission_required": True,
    "app_bound": True, "enforce_admins": True, "allows_force_push": False,
}


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "proj"
    r.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=r, check=True)
    subprocess.run(["git", "remote", "add", "origin",
                    "https://github.com/owner/proj.git"], cwd=r, check=True)
    return r


def assess(repo: Path, monkeypatch, protection=None, **kw):
    if protection is not None:
        monkeypatch.setattr(adm, "probe_branch_protection", lambda *a, **k: protection)
    opts = {"paired": True, "controller_persistent": True, "controller_atomic": True,
            "online": True, **kw}
    return adm.assess(root=repo, **opts)


# ------------------------------------------------------------------- tiers
def test_a_repository_with_no_remote_is_local_and_says_why(tmp_path: Path):
    r = tmp_path / "solo"
    r.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=r, check=True)
    a = adm.assess(root=r, paired=False, controller_persistent=True,
                   controller_atomic=True)
    assert a.tier == adm.LOCAL
    assert any("rewritten" in s for s in a.shortfalls)


def test_everything_in_place_is_enforced(repo, monkeypatch):
    a = assess(repo, monkeypatch, FULL_PROTECTION)
    assert a.enforced and a.tier == adm.ENFORCED


@pytest.mark.parametrize("missing,expect", [
    ({"admission_required": False}, "not among the required checks"),
    ({"app_bound": False}, "any writer can post a green status"),
    ({"enforce_admins": False}, "administrators can bypass"),
    ({"allows_force_push": True}, "rewritten after the fact"),
])
def test_each_missing_platform_guarantee_denies_enforced(repo, monkeypatch,
                                                         missing, expect):
    a = assess(repo, monkeypatch, {**FULL_PROTECTION, **missing})
    assert not a.enforced
    assert any(expect in s for s in a.shortfalls), a.shortfalls


def test_an_ephemeral_controller_cannot_reach_enforced(repo, monkeypatch):
    a = assess(repo, monkeypatch, FULL_PROTECTION, controller_persistent=False)
    assert not a.enforced
    assert any("throwaway checkout" in s for s in a.shortfalls)


def test_a_non_atomic_controller_cannot_reach_enforced(repo, monkeypatch):
    a = assess(repo, monkeypatch, FULL_PROTECTION, controller_atomic=False)
    assert not a.enforced
    assert any("both admit the same receipt" in s for s in a.shortfalls)


def test_a_single_repository_cannot_reach_enforced(repo, monkeypatch):
    a = assess(repo, monkeypatch, FULL_PROTECTION, paired=False)
    assert not a.enforced
    assert any("no privilege separation" in s for s in a.shortfalls)


def test_not_probing_the_platform_never_counts_in_favour(repo):
    """A gate nobody looked at is not a gate."""
    a = adm.assess(root=repo, paired=True, controller_persistent=True,
                   controller_atomic=True, online=False)
    assert not a.enforced
    assert any("not probed" in s for s in a.shortfalls)


def test_paired_but_ungated_is_called_notification_not_enforced(repo, monkeypatch):
    a = assess(repo, monkeypatch, {"reachable": True, "protected": False,
                                   "why": "no rule"})
    assert a.tier == adm.NOTIFICATION
    assert "nothing is refused" in adm.TIER_MEANING[a.tier]


def test_every_tier_states_what_it_means():
    for tier in (adm.LOCAL, adm.REMOTE, adm.PAIRED, adm.NOTIFICATION, adm.ENFORCED):
        assert adm.TIER_MEANING[tier]


# ------------------------------------------------- controller self-attestation
def test_the_controller_proves_its_own_atomicity(tmp_path: Path):
    caps = StateStore(tmp_path / "state.json").capabilities()
    assert caps["atomic"], caps["why_not"]


def test_a_store_in_a_throwaway_location_reports_itself_impersistent():
    path = Path(tempfile.gettempdir()) / "crossaudit-ephemeral-test" / "state.json"
    caps = StateStore(path).capabilities()
    assert not caps["persistent"]
    assert "outlive" in caps["why_not"]


# ----------------------------------------------------------------- console
@pytest.fixture()
def console(tmp_path: Path):
    from crossaudit.config import load
    from crossaudit.console import serve

    root = tmp_path / "proj"
    (root).mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    (root / "AUDIT_RULES.md").write_text("### CA-X-001\n**BLOCKER.** be exact\n\nx\n")
    (root / "crossaudit.yml").write_text(
        "version: 1\nscience_repo: t/p\nconstitution: AUDIT_RULES.md\n"
        "auditor: {vendor: openai, provider: openai_compat, model: m,"
        " key_env: CROSSAUDIT_AUDITOR_KEY}\ngenerator: {vendor: anthropic}\n"
        "ledger: {dir: cycles}\nstate: {dir: .crossaudit}\n"
        "checks: [parseable]\n")
    cfg = load(root / "crossaudit.yml")
    url, httpd = serve(cfg, port=0)
    import threading

    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield url
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()


def fetch(url: str, **headers):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, r.read().decode(), dict(r.headers)


def post_json_to(console: str, path: str, payload: dict):
    url = console.replace("/?t=", f"{path}?t=")
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as response:
        return response.status, json.loads(response.read()), dict(response.headers)


def post_json(console: str, payload: dict):
    return post_json_to(console, "/api/say", payload)


def rejected(call):
    """Run an HTTP call expected to fail and close its response deterministically."""
    try:
        call()
    except urllib.error.HTTPError as error:
        try:
            return error.code, error.read(), dict(error.headers)
        finally:
            error.close()
    raise AssertionError("HTTP request unexpectedly succeeded")


def attachment(name: str, data: bytes) -> dict:
    return {"name": name, "type": "text/plain", "size": len(data),
            "data": base64.b64encode(data).decode()}


def test_console_orders_hashed_cycle_ids_by_controller_history():
    from crossaudit.console.server import _ordered_cycles

    rows = _ordered_cycles({
        "cycles": {
            "ffff": {"status": "ESCALATED", "round": 1, "active_sha": "old"},
            "0000": {"status": "PASSED", "round": 1, "active_sha": "new"},
        },
        "history": [
            {"cycle": "ffff", "event": "open", "t": 10},
            {"cycle": "0000", "event": "open", "t": 20},
            {"cycle": "0000", "event": "verdict", "t": 30},
        ],
    })

    assert [row["id"] for row in rows] == ["ffff", "0000"]
    assert rows[-1]["status"] == "PASSED" and rows[-1]["updated"] == 30


def test_the_console_serves_its_page_with_the_token(console):
    status, body, headers = fetch(console)
    assert status == 200 and "CrossAudit" in body
    assert "default-src 'none'" in headers["content-security-policy"]


def test_console_creates_and_pins_individual_chats(console):
    status, created, _headers = post_json_to(
        console, "/api/chats/new", {"title": "Pinned investigation"})
    chat = created["chat"]
    assert status == 200 and len(chat["id"]) == 16

    status, pinned, _headers = post_json_to(
        console, "/api/chats/pin", {"chat_id": chat["id"], "pinned": True})
    assert status == 200 and pinned["chat"]["pinned"] is True
    state_url = console.replace("/?t=", "/api/state?t=")
    _, body, _ = fetch(state_url)
    state = json.loads(body)
    row = next(item for item in state["chats"]["items"]
               if item["id"] == chat["id"])
    assert row["title"] == "Pinned investigation"
    assert row["pinned"] is True and row["cycles"] == 0


def test_console_deletes_one_chat_without_resurrecting_navigation(console):
    status, created, _headers = post_json_to(
        console, "/api/chats/new", {"title": "Disposable chat"})
    chat = created["chat"]
    assert status == 200

    status, deleted, _headers = post_json_to(
        console, "/api/chats/delete", {"chat_id": chat["id"]})
    assert status == 200 and deleted["chat"]["id"] == chat["id"]
    state_url = console.replace("/?t=", "/api/state?t=")
    _, body, _ = fetch(state_url)
    assert chat["id"] not in {row["id"] for row in json.loads(body)["chats"]["items"]}


def test_console_can_pin_the_current_project_folder(console):
    state_url = console.replace("/?t=", "/api/state?t=")
    _, body, _ = fetch(state_url)
    root = json.loads(body)["root"]
    status, result, _headers = post_json_to(
        console, "/api/projects/pin", {"root": root, "pinned": True})
    assert status == 200 and result["pinned"] is True
    _, body, _ = fetch(state_url)
    assert json.loads(body)["chats"]["project_pinned"] is True


def test_without_the_token_everything_is_refused(console):
    bare = console.split("?")[0]
    code, _body, _headers = rejected(lambda: fetch(bare))
    assert code == 403


def test_a_wrong_token_is_refused(console):
    code, _body, _headers = rejected(
        lambda: fetch(console.split("?")[0] + "?t=guess"))
    assert code == 403


def test_a_foreign_host_header_is_refused_even_with_the_token(console):
    """The DNS-rebinding defence: the attacker's name resolves to 127.0.0.1, but
    the request still carries their Host."""
    code, _body, _headers = rejected(
        lambda: fetch(console, Host="evil.example.com"))
    assert code == 403


def test_the_only_write_path_is_the_one_input(console):
    """The console gained exactly one write path — the sentence box — and it is
    narrow on purpose: everything it can cause, the CLI could already do."""
    req = urllib.request.Request(console, data=b"{}", method="POST")
    code, _body, _headers = rejected(
        lambda: urllib.request.urlopen(req, timeout=5))
    assert code == 404                              # POST anywhere else: no route


def test_the_input_needs_the_token_like_everything_else(console):
    bare = console.split("?")[0] + "api/say"
    req = urllib.request.Request(bare, data=b'{"text":"hello"}', method="POST",
                                 headers={"content-type": "application/json"})
    code, _body, _headers = rejected(
        lambda: urllib.request.urlopen(req, timeout=5))
    assert code == 403


def test_the_input_refuses_an_empty_or_oversized_sentence(console):
    url = console.replace("/?t=", "/api/say?t=")
    for payload, code in ((b'{"text":"   "}', 400),
                          (b'{"text":"' + b"x" * 5000 + b'"}', 413)):
        req = urllib.request.Request(url, data=payload, method="POST",
                                     headers={"content-type": "application/json"})
        actual, _body, _headers = rejected(
            lambda: urllib.request.urlopen(req, timeout=5))
        assert actual == code


def test_attachment_contents_need_a_second_explicit_consent(console):
    payload = {"text": "Use this input", "attachments": [
        attachment("input.csv", b"name,value\nalpha,3\n")],
        "attachment_consent": False}
    url = console.replace("/?t=", "/api/say?t=")
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"content-type": "application/json"})
    code, body, _headers = rejected(
        lambda: urllib.request.urlopen(req, timeout=5))
    assert code == 400
    assert "explicit consent" in body.decode()


@pytest.mark.parametrize("item,code", [
    (attachment("../secret.txt", b"x"), 400),
])
def test_the_http_boundary_refuses_unsafe_attachments(console, item, code):
    url = console.replace("/?t=", "/api/say?t=")
    req = urllib.request.Request(
        url, data=json.dumps({"text": "Use it", "attachments": [item],
                              "attachment_consent": True}).encode(),
        method="POST", headers={"content-type": "application/json"})
    actual, _body, _headers = rejected(
        lambda: urllib.request.urlopen(req, timeout=5))
    assert actual == code


def test_validated_attachments_reach_say_only_after_consent(console, monkeypatch):
    from crossaudit.console import server as server_mod

    seen = {}

    def fake_say(_cfg, text, *, attachments, attachment_consent,
                 delivery_choices=None, chat_id=""):
        seen.update(text=text, attachments=attachments,
                    attachment_consent=attachment_consent,
                    delivery_choices=delivery_choices, chat_id=chat_id)
        return {"asked": False, "lane": "generator", "confidence": 1.0,
                "reasoning": "test", "executed": "building: smoke",
                "attachments_accepted": True}

    monkeypatch.setattr(server_mod, "say", fake_say)
    status, body, _headers = post_json(console, {
        "text": "Use it", "attachments": [attachment("input.csv", b"x,y\n1,2\n")],
        "attachment_consent": True})
    assert status == 200 and body["attachments_accepted"] is True
    assert seen["attachment_consent"] is True
    assert len(seen["chat_id"]) == 16
    assert seen["attachments"][0].text == "x,y\n1,2\n"


def test_chunked_http_batch_accepts_large_binary_and_reaches_say(
        console, monkeypatch):
    """The supported browser path has no legacy count/type/file-size quota."""
    from crossaudit.console import server as server_mod

    data = bytes(range(256)) * 1200  # 307,200 bytes: above the legacy 200 KB cap.
    upload_id = "a" * 32
    batch = "b" * 32
    status, uploaded, _headers = post_json_to(console, "/api/upload", {
        "id": upload_id, "batch": batch, "ordinal": 0, "batch_count": 1,
        "name": "evidence.bin",
        "type": "application/octet-stream", "offset": 0, "total": len(data),
        "data": base64.b64encode(data).decode(),
    })
    assert status == 200 and uploaded["complete"] is True
    seen = {}

    def fake_say(_cfg, text, *, attachments, attachment_consent,
                 delivery_choices=None, chat_id=""):
        seen.update(text=text, attachments=attachments, chat_id=chat_id)
        return {"asked": False, "lane": "generator", "confidence": 1.0,
                "reasoning": "test", "executed": "building: smoke",
                "attachments_accepted": True}

    monkeypatch.setattr(server_mod, "say", fake_say)
    status, body, _headers = post_json(console, {
        "text": "Preserve this evidence", "upload_batch": batch,
        "attachment_consent": True,
    })

    assert status == 200 and body["attachments_accepted"] is True
    item = seen["attachments"][0]
    assert item.name == "evidence.bin" and item.size == len(data)
    assert item.text is None and item.source.read_bytes() == data


def test_delivery_choices_are_validated_and_bound_to_one_generator_task():
    from crossaudit.console.server import _guided_task

    task = _guided_task("Write a review", {
        "mode": "selected", "focus": "Everyday use and practical experience",
        "format": "Markdown (.md)", "tone": "Editorial and readable"})

    assert task.startswith("Write a review\n")
    assert "Output format: Markdown (.md)" in task
    assert "exactly one primary deliverable" in task


def test_delivery_choices_refuse_an_unimplemented_binary_format():
    from crossaudit.console.server import _guided_task
    from crossaudit.errors import ConfigDenial

    with pytest.raises(ConfigDenial, match="supported format"):
        _guided_task("Write a review", {
            "mode": "selected", "focus": "Balanced coverage", "format": "PDF",
            "tone": "Editorial and readable"})


def test_artifact_download_is_tokened_streamed_and_forces_a_download(
        console, monkeypatch, tmp_path):
    from crossaudit.console import server as server_mod

    output = tmp_path / "result.txt"
    output.write_bytes(b"audited output\n" + b"x" * 2_000_000)
    monkeypatch.setattr(server_mod, "resolve_artifact",
                        lambda _cfg, path: (output, "result.txt", output.stat().st_size))
    url = console.replace("/?t=", "/api/file?path=experiments%2Fresult.txt&t=")
    status, body, headers = fetch(url)
    assert status == 200 and body.startswith("audited output\n")
    assert len(body.encode()) == output.stat().st_size
    assert headers["content-disposition"].startswith("attachment;")
    assert headers["cache-control"] == "no-store"
    bare = url.split("&t=")[0]
    code, _body, _headers = rejected(lambda: fetch(bare))
    assert code == 403


def test_the_two_windows_are_reconstructed_from_the_ledger(console):
    _s, body, _h = fetch(console.replace("/?", "/api/state?"))
    data = json.loads(body)
    # Two streams, not a stored chat: what exists is commits, reports and receipts.
    assert "generator_stream" in data and "auditor_stream" in data
    assert isinstance(data["generator_stream"], list)
    assert data["generator"] and data["auditor"]
    from crossaudit import __version__
    assert data["version"] == __version__
    assert data["check_contracts"]["parseable"]
    assert data["usage"]["local_only"] is True
    assert data["usage"]["cost_label"] == "API-value estimate"
    assert ":" in data["generator"] and ":" in data["auditor"]


def test_the_state_endpoint_reports_key_presence_never_the_key(console, monkeypatch):
    monkeypatch.setenv("CROSSAUDIT_AUDITOR_KEY", "sk-secret-value-123")
    _s, body, _h = fetch(console.replace("/?", "/api/state?"))
    assert "sk-secret-value-123" not in body
    data = json.loads(body)
    assert data["key_present"] in (True, False)
    assert "tier" in data and "shortfalls" in data["tier"]


def test_app_settings_write_is_tokened_app_only_and_never_echoes_secret(
        console, monkeypatch):
    from crossaudit.console import server as server_mod

    secret = "sk-test-must-never-come-back"
    seen = {}
    monkeypatch.setenv("CROSSAUDIT_APP_MODE", "1")

    def apply(payload):
        seen.update(payload)
        return {"providers": {"openai": {"configured": True},
                              "anthropic": {"configured": False}}}

    monkeypatch.setattr(server_mod.app_keys, "apply", apply)
    monkeypatch.setattr(server_mod.connections, "status", lambda: {
        "openai": {"configured": True, "api_key": {"configured": True},
                   "chatgpt": {"available": True, "connected": False}},
        "anthropic": {"configured": False,
                      "api_key": {"configured": False}}})
    status, body, headers = post_json_to(
        console, "/api/settings", {"openai_key": secret})

    encoded = json.dumps(body)
    assert status == 200 and seen["openai_key"] == secret
    assert secret not in encoded
    assert body["providers"]["openai"]["configured"] is True
    assert headers["content-security-policy"].startswith("default-src 'none'")

    bare = console.split("?", 1)[0] + "api/settings"
    req = urllib.request.Request(
        bare, data=json.dumps({"openai_key": secret}).encode(), method="POST",
        headers={"content-type": "application/json"})
    code, body, headers = rejected(
        lambda: urllib.request.urlopen(req, timeout=5))
    assert code == 403
    assert headers["connection"] == "close"
    assert body == b"forbidden"


def test_mcp_settings_endpoint_is_tokened_and_never_echoes_bearer_token(
        console, monkeypatch):
    from crossaudit.console import server as server_mod

    secret = "mcp-secret-that-must-not-return"
    seen = {}

    def register(_cfg, payload):
        seen.update(payload)
        return {"id": "a" * 16, "name": "Tools", "transport": "http",
                "token_present": True, "tools": [], "enabled": False}

    monkeypatch.setattr(server_mod.mcp.MANAGER, "register", register)
    status, body, headers = post_json_to(console, "/api/mcp", {
        "action": "register", "name": "Tools", "transport": "http",
        "url": "secure endpoint", "bearer_token": secret,
    })

    assert status == 200 and seen["bearer_token"] == secret
    assert secret not in json.dumps(body)
    assert body["token_present"] is True
    assert headers["content-security-policy"].startswith("default-src 'none'")


def test_admit_endpoint_is_tokened_and_returns_only_receipt_identity(
        console, monkeypatch):
    from crossaudit.console import server as server_mod

    selected = {}
    def fake_admit(_cfg, cycle_id=""):
        selected["cycle_id"] = cycle_id
        return {
        "admitted": True, "verified": True, "cycle_id": "cycle-1",
        "receipt": "a" * 16, "sha": "b" * 40}
    monkeypatch.setattr(server_mod, "admit_latest", fake_admit)
    status, body, _headers = post_json_to(
        console, "/api/admit", {"cycle_id": "selected-cycle"})
    assert status == 200 and body["admitted"] is True and body["verified"] is True
    assert body["receipt"] == "a" * 16
    assert selected["cycle_id"] == "selected-cycle"

    bare = console.split("?", 1)[0] + "api/admit"
    req = urllib.request.Request(bare, data=b"{}", method="POST",
                                 headers={"content-type": "application/json"})
    code, _body, _headers = rejected(
        lambda: urllib.request.urlopen(req, timeout=5))
    assert code == 403


def test_runtime_switch_is_refused_while_a_loop_is_running(console):
    from crossaudit.console.progress import TRACKER

    TRACKER.clear()
    TRACKER.start("long audit")
    try:
        code, raw_body, _headers = rejected(lambda: post_json_to(
            console, "/api/runtime", {
                "generator_model": "gpt-5.6-luna",
                "generator_reasoning_effort": "low",
                "auditor_model": "claude-sonnet-4-6",
                "auditor_reasoning_effort": "medium",
            }))
        body = json.loads(raw_body)
    finally:
        TRACKER.finish("cancelled")
        TRACKER.clear()

    assert code == 400
    assert body["issue"] == "runtime_busy"
    assert "wait for this task to finish" in body["reason"]


def test_a_human_can_resolve_an_escalation_through_the_tokened_ui(console):
    state_url = console.replace("/?t=", "/api/state?t=")
    _status, body, _headers = fetch(state_url)
    state = json.loads(body)
    store = StateStore(Path(state["root"]) / ".crossaudit" / "state.json")
    cycle = store.open_or_advance("t/p", "a" * 40, None)
    store.escalate(cycle["cycle_id"], "round budget spent")

    status, result, _headers = post_json_to(console, "/api/escalation", {
        "cycle_id": cycle["cycle_id"], "action": "reopen",
        "reason": "One focused correction is justified.",
    })

    assert status == 200 and result["status"] == "OPEN"
    assert store.cycle(cycle["cycle_id"])["status"] == "OPEN"


def test_latest_pass_admission_reverifies_recorded_receipt(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from crossaudit.console import server as server_mod

    sha, digest, cycle_id = "b" * 40, "a" * 64, "cycle-1"
    receipt_path = tmp_path / "cycles" / f"{sha[:12]}-r1" / "receipt.json"
    receipt_path.parent.mkdir(parents=True)
    receipt_path.write_text("{}")
    state = {
        "cycles": {cycle_id: {"status": "PASSED", "active_sha": sha,
                              "round": 1, "parent_receipt": digest}},
        "history": [{"event": "verdict", "cycle": cycle_id,
                     "receipt": digest[:16]}],
    }

    class Store:
        def __init__(self, _path): pass
        def snapshot(self): return state

    receipt = {"cycle": {"cycle_id": cycle_id}, "subject": {"sha": sha}}
    cfg = SimpleNamespace(root=tmp_path, state_dir=".crossaudit",
                          ledger_dir="cycles", science_repo="owner/project")
    monkeypatch.setattr(server_mod, "StateStore", Store)
    monkeypatch.setattr(server_mod, "load_receipt", lambda path: receipt)
    monkeypatch.setattr(server_mod, "verify_receipt", lambda *a, **k: {
        "receipt_digest": digest, "admission_ready": True, "cycle_id": cycle_id,
        "sha": sha})
    monkeypatch.setattr(server_mod, "admit_receipt", lambda rec, store, evidence,
                        cfg=None: {"admitted": True, "cycle_id": cycle_id})

    result = server_mod.admit_latest(cfg)
    assert result["admitted"] and result["verified"]
    assert result["receipt"] == digest[:16] and result["sha"] == sha


def test_admission_never_falls_back_to_an_older_pass(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from crossaudit.console import server as server_mod
    from crossaudit.errors import ConfigDenial

    state = {
        "cycles": {
            "old": {"status": "PASSED", "active_sha": "a" * 40, "round": 1},
            "new": {"status": "CONSUMED", "active_sha": "b" * 40, "round": 1},
        },
        "history": [
            {"event": "verdict", "cycle": "old", "receipt": "1" * 16},
            {"event": "verdict", "cycle": "new", "receipt": "2" * 16},
        ],
    }

    class Store:
        def __init__(self, _path): pass
        def snapshot(self): return state

    cfg = SimpleNamespace(root=tmp_path, state_dir=".crossaudit",
                          ledger_dir="cycles", science_repo="owner/project")
    monkeypatch.setattr(server_mod, "StateStore", Store)
    with pytest.raises(ConfigDenial, match="no unconsumed"):
        server_mod.admit_latest(cfg)


def test_live_stream_pushes_progress_without_waiting_for_the_poll(console,
                                                                  monkeypatch):
    """Same-process progress is event-driven; a long fallback interval must not
    delay what the browser sees."""
    import time

    from crossaudit.console import server as server_mod
    from crossaudit.console.progress import TRACKER

    TRACKER.clear()
    monkeypatch.setattr(server_mod, "STREAM_POLL_S", 5.0)
    stream_url = console.replace("/?t=", "/api/stream?t=")
    with urllib.request.urlopen(stream_url, timeout=5) as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.readline().startswith(b"data: ")
        assert response.readline() == b"\n"

        started = time.monotonic()
        TRACKER.start("show this immediately")
        pushed = response.readline()
        latency = time.monotonic() - started

    TRACKER.finish("passed")
    TRACKER.clear()
    assert pushed.startswith(b"data: ")
    assert b"show this immediately" in pushed
    # A person should experience this as the same event, not as a refresh.
    # Keep enough headroom for a loaded CI worker while rejecting polling-scale
    # latency; external-process changes have their separate 100 ms ceiling.
    assert latency < 0.25, f"live update took {latency:.3f}s"


def test_external_process_fallback_is_subsecond():
    from crossaudit.console import server as server_mod

    assert server_mod.STREAM_POLL_S <= 0.1


def test_the_console_binds_to_loopback_only(console):
    assert console.startswith("http://127.0.0.1:")
