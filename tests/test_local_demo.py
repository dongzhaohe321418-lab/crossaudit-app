"""The credential-free "Explore a local demo" sample (first-launch slice 2).

Honesty is the contract under test: the demo populates the REAL overview with a
completed cycle, but never fabricates or implies a real audit. It runs no
provider, reads no key, mints no receipt, and labels every surface "sample".

These are unit/console tests — no network, no model. The endpoint test spins the
real loopback server like ``test_first_launch`` so the token/Host/allowlist
guards are exercised, with the daemon launch stubbed so no child process spawns.
"""
from __future__ import annotations

import json
import subprocess
import threading
import urllib.request
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

import pytest

from crossaudit.config import load
from crossaudit.console import projects, server
from crossaudit.console.page import PAGE
from crossaudit.providers.registry import NON_EVIDENTIAL
from crossaudit.providers.specs import source_independent


# ------------------------------------------------------------- env hygiene
@pytest.fixture(autouse=True)
def _no_credentials(monkeypatch):
    """The demo must work with zero providers configured. Prove it by clearing
    every credential env var the demo config could conceivably name."""
    for name in ("CROSSAUDIT_DEMO_KEY", "CROSSAUDIT_AUDITOR_KEY",
                 "CROSSAUDIT_GENERATOR_KEY", "CROSSAUDIT_ANTHROPIC_KEY",
                 "CROSSAUDIT_OPENAI_KEY", "CROSSAUDIT_APP_MODE"):
        monkeypatch.delenv(name, raising=False)


# --------------------------------------------------------- materialization
def test_demo_materializes_credential_free_and_renders_a_completed_cycle(tmp_path):
    target = projects.materialize_demo(tmp_path / projects.DEMO_DIRNAME)
    cfg = load(target / "crossaudit.yml")

    assert projects.is_demo_project(cfg) is True
    # The seeded cycle renders through the REAL overview snapshot — with no
    # provider configured and no ConfigDenial.
    snap = server.snapshot(cfg)
    assert snap["demo"] is True
    metrics = {row["label"]: row["value"] for row in snap["metrics"]}
    assert metrics["Audits"] == 1 and metrics["Passed"] == 1
    assert metrics["Admitted"] == 0            # nothing was admitted; nothing ran
    pipeline = {step["title"]: step["state"] for step in snap["pipeline"]}
    assert pipeline["Verdict"] == "done"       # the generator→auditor→PASS story
    # The roles render without naming or reaching a real vendor.
    assert "replay" in snap["auditor"] and "replay" in snap["generator"]
    assert snap["key_present"] is False


def test_demo_is_idempotent_and_never_duplicates(tmp_path):
    first = projects.materialize_demo(tmp_path / projects.DEMO_DIRNAME)
    log_before = subprocess.run(["git", "-C", str(first), "log", "--oneline"],
                                capture_output=True, text=True).stdout
    second = projects.materialize_demo(tmp_path / projects.DEMO_DIRNAME)
    log_after = subprocess.run(["git", "-C", str(second), "log", "--oneline"],
                               capture_output=True, text=True).stdout

    assert first == second
    assert log_before == log_after             # no new commits on reuse
    # setup + the generator's delivery + the seeded ledger cycle.
    assert len(log_after.strip().splitlines()) == 3
    assert len(list((first / "cycles").glob("*/report.md"))) == 1


# ---------------------------------------------- the landing view tells a story
def test_demo_landing_view_shows_the_generator_auditor_pass_story(tmp_path):
    """On open the demo lands on a populated thread, not an empty composer.

    The main conversation is reconstructed from controller state + routing +
    the chat index (not the ledger the dashboard reads), so the snapshot must
    carry a single titled chat whose thread reads user request → generator
    delivery → independent PASS review."""
    target = projects.materialize_demo(tmp_path / projects.DEMO_DIRNAME)
    cfg = load(target / "crossaudit.yml")
    snap = server.snapshot(cfg)

    # Exactly one chat, and it is titled as the story (not "Project history").
    chats = snap["chats"]["items"]
    assert len(chats) == 1
    active = chats[0]["id"]
    assert chats[0]["title"] == projects.DEMO_CHAT_TITLE

    # A controller cycle exists and is PASSED — this is what makes the review
    # card and delivery state render (the dashboard's ledger cycle does not).
    cycles = [c for c in snap["cycles"] if (c.get("chat_id") or "history") == active]
    assert len(cycles) == 1 and cycles[0]["status"] == "PASSED"
    delivery_sha = cycles[0]["sha"]

    # The opening "you" request, in this thread, routed to the generator.
    you = [m for m in snap["generator_stream"]
           if m["kind"] == "you" and m["chat_id"] == active]
    assert you and "peer review" in you[0]["utterance"]

    # The generator's delivery turn, carrying the review deliverable, and bound
    # to the PASSED cycle so the thread renders it (not filtered as a draft).
    gen = [m for m in snap["generator_stream"]
           if m["kind"] == "generator" and m["chat_id"] == active]
    assert gen and gen[0]["sha"] == delivery_sha
    assert any(a["name"] == "review.md" for a in gen[0]["artifacts"])

    # The independent auditor's PASS verdict, in the same thread.
    aud = [m for m in snap["auditor_stream"]
           if m["kind"] == "auditor" and m["chat_id"] == active]
    assert aud and aud[0]["verdict"] == "PASS"


# -------------------------------------------------------------- the honesty
def test_demo_mints_no_receipt_and_cannot_pass_as_a_real_audit(tmp_path):
    target = projects.materialize_demo(tmp_path / projects.DEMO_DIRNAME)
    cfg = load(target / "crossaudit.yml")

    # No fabricated cryptographic receipt is present at all.
    assert list((target / "cycles").glob("*/receipt.json")) == []

    # The recorded provider is the credential-free, non-evidential replay
    # adapter — a PASS through it can never be admitted, and its vendor is not a
    # source CrossAudit can attest as independent. So even were a receipt built,
    # it could not verify as a genuine independent cross-vendor audit.
    assert cfg.auditor.provider == "replay"
    assert "replay" in NON_EVIDENTIAL
    assert source_independent(cfg.auditor.vendor) is False
    assert source_independent(cfg.generator_vendor) is False

    # Every seeded artefact is pervasively labelled a sample.
    report = next((target / "cycles").glob("*/report.md")).read_text()
    assert "SAMPLE DEMONSTRATION" in report
    assert "no cryptographic receipt was minted" in report
    assert "| verdict | **PASS** |" in report          # still a real, parseable row
    marker = json.loads((target / projects.DEMO_MARKER).read_text())
    assert marker["demo"] is True and marker["kind"] == "local-sample"
    assert "not a real audit" in (target / "README.md").read_text()


def test_demo_project_opens_without_a_provider_or_spawn(tmp_path, monkeypatch):
    """demo_project materializes-or-reuses and returns a console URL without
    contacting any provider. The daemon launch is stubbed so the test stays
    in-process."""
    home = tmp_path / "home"
    home.mkdir()
    (home / "AUDIT_RULES.md").write_text("### CA-X-001\n**BLOCKER.** x\n\nx\n")
    (home / "crossaudit.yml").write_text(
        "version: 1\nscience_repo: t/home\nconstitution: AUDIT_RULES.md\n"
        "auditor: {vendor: openai, provider: openai_compat, model: m,"
        " key_env: CROSSAUDIT_AUDITOR_KEY}\ngenerator: {vendor: anthropic}\n"
        "state: {dir: .crossaudit}\nchecks: [parseable]\n")
    current = load(home / "crossaudit.yml")

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("CROSSAUDIT_WORKSPACE_ROOT", str(workspace))
    # Never spawn a real console; capture that no provider is ever asked for.
    monkeypatch.setattr(projects.daemon, "reusable_for_launch",
                        lambda cfg: {"port": 4321, "token": "tok"})

    result = projects.demo_project(current)
    assert result["demo"] is True
    assert result["url"].startswith("http://127.0.0.1:4321/?t=tok")
    assert Path(result["root"]) == (workspace / projects.DEMO_DIRNAME).resolve()
    assert (workspace / projects.DEMO_DIRNAME / "crossaudit.yml").is_file()


# ------------------------------------------------------- runtime-role guard
def test_replay_role_renders_a_sample_descriptor_but_real_typos_still_raise(tmp_path):
    from crossaudit.errors import ConfigDenial

    target = projects.materialize_demo(tmp_path / projects.DEMO_DIRNAME)
    cfg = load(target / "crossaudit.yml")
    options = projects.runtime_options(cfg)
    for role in ("generator", "auditor"):
        row = options["roles"][role]
        assert row["adjustable"] is False and row["provider"] == "replay"
        assert row["models"] == [] and row["efforts"] == []

    # A genuinely misconfigured project (unknown vendor on a REAL provider) must
    # still fail loudly rather than masquerade as a sample.
    (target / "crossaudit.yml").write_text(
        (target / "crossaudit.yml").read_text()
        .replace("provider: replay\n  model: sample-auditor",
                 "provider: openai_compat\n  model: sample-auditor"))
    broken = load(target / "crossaudit.yml")
    with pytest.raises(ConfigDenial):
        projects.runtime_options(broken)


# ---------------------------------------------------------- page + ZH parity
class _Ids(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids: list[str] = []

    def handle_starttag(self, tag, attrs):
        value = dict(attrs).get("id")
        if value:
            self.ids.append(str(value))


def test_page_carries_the_sample_banner_and_demo_wiring():
    for marker in (
        'id="sample-banner"', 'class="sample-badge"',
        'Sample demonstration — not a real audit.',
        'No models were run and no API keys were used; this content is illustrative.',
        '/api/projects/demo', "sampleBanner.hidden=!d.demo",
    ):
        assert marker in PAGE, marker
    # The honest stub is gone: the demo no longer claims to be unavailable.
    assert "The guided local demo is not available yet" not in PAGE

    parser = _Ids()
    parser.feed(PAGE)
    assert [value for value, count in Counter(parser.ids).items() if count > 1] == []


def test_demo_strings_have_chinese_parity():
    for pair in (
        '"SAMPLE":"示例"',
        '"Sample demonstration — not a real audit.":"示例演示——并非真实审计。"',
        ('"No models were run and no API keys were used; this content is '
         'illustrative.":"未运行任何模型，也未使用任何 API 密钥；此内容仅供演示说明。"'),
    ):
        assert pair in PAGE, pair
    # The dynamic failure notice is covered by a ZH pattern, not the exact map.
    assert "无法准备本地演示：" in PAGE


# ------------------------------------------------------------- the endpoint
@pytest.fixture()
def console(tmp_path: Path):
    from crossaudit.console import serve

    root = tmp_path / "proj"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    (root / "AUDIT_RULES.md").write_text("### CA-X-001\n**BLOCKER.** x\n\nx\n")
    (root / "crossaudit.yml").write_text(
        "version: 1\nscience_repo: t/p\nconstitution: AUDIT_RULES.md\n"
        "auditor: {vendor: openai, provider: openai_compat, model: m,"
        " key_env: CROSSAUDIT_AUDITOR_KEY}\ngenerator: {vendor: anthropic}\n"
        "ledger: {dir: cycles}\nstate: {dir: .crossaudit}\nchecks: [parseable]\n")
    cfg = load(root / "crossaudit.yml")
    url, httpd = serve(cfg, port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield url
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()


def test_demo_endpoint_is_on_the_allowlist_and_returns_a_url(console, monkeypatch):
    monkeypatch.setattr(projects.daemon, "reusable_for_launch",
                        lambda cfg: {"port": 9876, "token": "T"})
    url = console.replace("/?t=", "/api/projects/demo?t=")
    request = urllib.request.Request(url, data=b"{}", method="POST",
                                     headers={"content-type": "application/json"})
    with urllib.request.urlopen(request, timeout=5) as response:
        status, body = response.status, json.loads(response.read())
    assert status == 200
    assert body["demo"] is True
    assert body["url"].startswith("http://127.0.0.1:9876/?t=T")
