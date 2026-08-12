"""Live progress is a read-only projection of the durable Run journal."""
from __future__ import annotations

import threading
import time

import pytest

from crossaudit.console.progress import Tracker
from crossaudit.errors import EXIT_OK, ConfigDenial
from crossaudit.runtime import (
    PreparedRun,
    RunCommandService,
    RunEvent,
    RunJournal,
    RunState,
    acquire_workspace_slot,
    journal_path,
    release_workspace_slot,
    workspace_capacity,
)


def event(actor: str, text: str, state: RunState = RunState.GENERATING,
          *, kind: str = "activity") -> RunEvent:
    return RunEvent(actor=actor, text=text, state=state, kind=kind)


def enable_build_scope(cfg) -> None:
    cfg.path.write_text(
        cfg.path.read_text(encoding="utf-8") + "scope:\n  dirs: [experiments]\n",
        encoding="utf-8")


def test_a_fresh_tracker_has_nothing_to_show():
    t = Tracker()
    assert t.snapshot() is None and not t.running


def test_steps_accumulate_in_order_while_a_run_is_in_flight(tmp_path):
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    run_id = journal.start("write the section")
    journal.append(run_id, event("generator", "writing"))
    journal.append(run_id, event(
        "auditor", "reviewing the commit", RunState.AUDITING,
        kind="audit_started"))
    t = Tracker()
    t.bind(journal.path)
    snap = t.snapshot()
    assert t.running and not snap["finished"]
    assert [s["actor"] for s in snap["steps"]] == ["generator", "auditor"]
    assert snap["task"] == "write the section"


def test_finishing_records_the_outcome_and_stops_the_run(tmp_path):
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    run_id = journal.start("x")
    journal.append(run_id, event("generator", "writing"))
    journal.finish(run_id, "passed")
    t = Tracker()
    t.bind(journal.path)
    snap = t.snapshot()
    assert not t.running and snap["finished"] and snap["outcome"] == "passed"
    assert snap["steps"][-1]["actor"] == "done"


def test_a_failure_keeps_its_reason(tmp_path):
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    run_id = journal.start("x")
    journal.finish(run_id, "refused", "the generator has no key")
    t = Tracker()
    t.bind(journal.path)
    assert t.snapshot()["error"] == "the generator has no key"


def test_only_one_build_runs_at_a_time(tmp_path):
    """Two concurrent builds would race on the working tree and on the round
    budget; the honest answer is that one is already running."""
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    first = journal.start("first")
    with pytest.raises(RuntimeError, match="already running"):
        journal.start("second")
    journal.finish(first, "passed")
    journal.start("second")                 # once it is done, the next may begin
    assert journal.latest()["task"] == "second"


def test_steps_after_the_end_do_not_reopen_a_run(tmp_path):
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    run_id = journal.start("x")
    journal.finish(run_id, "passed")
    with pytest.raises(RuntimeError, match="invalid run transition"):
        journal.append(run_id, event("generator", "a late straggler"))
    assert journal.latest()["state"] == "PASSED"


def test_clearing_a_projection_never_deletes_durable_progress(tmp_path):
    path = tmp_path / "runtime.sqlite3"
    journal = RunJournal(path)
    run_id = journal.start("x")
    journal.append(run_id, event("generator", "writing"))
    journal.finish(run_id, "passed")
    t = Tracker()
    t.bind(path)
    t.clear()
    assert t.snapshot() is None
    assert RunJournal(path).latest()["state"] == "PASSED"


def test_concurrent_steps_do_not_lose_entries(tmp_path):
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    run_id = journal.start("x")

    def hammer(n: int) -> None:
        for i in range(50):
            journal.append(run_id, event("generator", f"{n}-{i}"))

    threads = [threading.Thread(target=hammer, args=(n,)) for n in range(4)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert len(journal.latest()["steps"]) == 200


def test_every_progress_change_wakes_live_views(cfg):
    t = Tracker()
    t.bind(journal_path(cfg))
    changes = []
    t.subscribe(lambda: changes.append(t.snapshot()))

    service = RunCommandService(cfg, on_change=t.notify)

    def worker(_prepared, emit):
        emit(event("generator", "writing"))
        return EXIT_OK

    service.start(lambda: PreparedRun(task="x"), worker, background=False)

    assert len(changes) == 3
    assert changes[0]["task"] == "x"
    assert changes[1]["steps"][0]["text"] == "writing"
    assert changes[2]["finished"] is True


def test_elapsed_grows_while_running_and_freezes_when_done(tmp_path):
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    run_id = journal.start("x")
    t = Tracker()
    t.bind(journal.path)
    time.sleep(0.01)
    assert t.snapshot()["elapsed"] >= 0
    journal.finish(run_id, "passed")
    frozen = t.snapshot()["elapsed"]
    time.sleep(0.05)
    assert t.snapshot()["elapsed"] == frozen


def test_the_cli_and_the_console_share_one_run_command_service():
    """Lifecycle policy must not drift even though the presentation differs."""
    import inspect

    from crossaudit.cli import build as build_mod
    from crossaudit.console import server

    cli_source = inspect.getsource(build_mod.cmd_build)
    ui_source = inspect.getsource(server.start_build)
    assert "RunCommandService" in cli_source and "RunCommandService" in ui_source
    assert "RunJournal" not in cli_source and "TRACKER.start" not in ui_source


def test_cli_and_ui_share_one_project_mutation_lease(cfg, monkeypatch):
    from crossaudit.cli import build as build_mod

    monkeypatch.chdir(cfg.root)
    enable_build_scope(cfg)
    slot = acquire_workspace_slot(cfg)
    try:
        with pytest.raises(ConfigDenial, match="already owns"):
            build_mod.cmd_build(type("Args", (), {"words": ["must", "not", "run"]})())
    finally:
        release_workspace_slot(slot)
    assert workspace_capacity(cfg)["active"] == 0


def test_cli_build_is_projected_into_the_same_durable_run_journal(
        cfg, monkeypatch):
    from crossaudit.cli import build as build_mod

    monkeypatch.chdir(cfg.root)
    enable_build_scope(cfg)

    def fake_loop(_cfg, _task, *, on_event, **_kwargs):
        on_event(RunEvent(
            kind="round_started", actor="loop", text="localized text may vary",
            state=RunState.GENERATING, round_no=1, round_limit=3))
        on_event(RunEvent(
            kind="audit_passed", actor="auditor", text="PASS",
            state=RunState.AUDITING, round_no=1, round_limit=3))
        return EXIT_OK

    monkeypatch.setattr(build_mod, "run_loop", fake_loop)
    assert build_mod.cmd_build(
        type("Args", (), {"words": ["record", "this", "run"]})()) == EXIT_OK

    row = RunJournal(journal_path(cfg)).latest()
    assert row["task"] == "record this run" and row["state"] == "PASSED"
    assert row["steps"][0]["kind"] == "round_started"
    assert row["steps"][0]["round_no"] == 1
    assert workspace_capacity(cfg)["active"] == 0


def test_cli_failure_releases_workspace_lease_and_records_failure(cfg, monkeypatch):
    from crossaudit.cli import build as build_mod

    monkeypatch.chdir(cfg.root)
    enable_build_scope(cfg)

    def crash(*_args, **_kwargs):
        raise RuntimeError("simulated engine crash")

    monkeypatch.setattr(build_mod, "run_loop", crash)
    with pytest.raises(RuntimeError, match="simulated engine crash"):
        build_mod.cmd_build(type("Args", (), {"words": ["crash", "safely"]})())

    row = RunJournal(journal_path(cfg)).latest()
    assert row["state"] == "FAILED" and "simulated engine crash" in row["error"]
    assert workspace_capacity(cfg)["active"] == 0


def test_human_continuation_is_forced_to_the_generator_and_keeps_its_cycle(
        cfg, monkeypatch):
    from crossaudit.cli import talk as talk_mod
    from crossaudit.console import server

    seen = {}

    def fake_start(_cfg, task, **kwargs):
        seen.update(task=task, **kwargs)
        return {"task": task, "attachments": []}

    monkeypatch.setattr(server, "start_build", fake_start)
    monkeypatch.setattr(talk_mod, "_record_routing", lambda *_a, **_k: None)
    result = server.say(
        cfg, "Correct the cited figures.", chat_id="history",
        continuation_cycle="a" * 16)

    assert result["lane"] == "generator"
    assert seen["continuation_cycle"] == "a" * 16
    assert seen["chat_id"] == "history"


def test_console_safe_autonomy_starts_a_reversible_low_confidence_task(
        cfg, monkeypatch):
    from crossaudit import router
    from crossaudit.cli import talk as talk_mod
    from crossaudit.console import server

    seen = {}
    routed = router.Routing(
        utterance="make it clearer", lane="generator", confidence=0.31,
        reasoning="probably a work request", restated="make it clearer",
        clarify="Do you mean the work or its rules?")
    monkeypatch.setattr(router, "route_addressed", lambda *_a, **_k: routed)
    monkeypatch.setattr(talk_mod, "_record_routing",
                        lambda _cfg, decision, executed: seen.update(
                            decision=decision, executed=executed))
    monkeypatch.setattr(server, "start_build", lambda _cfg, task, **_kwargs: {
        "task": task, "attachments": []})

    result = server.say(cfg, "make it clearer", chat_id="history")

    assert result["asked"] is False and result["lane"] == "generator"
    assert seen["decision"].routing_mode == "automatic_safe_default"
    assert seen["decision"].confidence == 0.31
    assert seen["executed"].startswith("building:")


def test_no_string_literal_in_the_page_script_spans_a_line():
    """A stray real newline inside a JS string kills the whole script, and the
    only visible symptom is the form falling back to a native submit that drops
    the session token — which reads as a security failure rather than a typo.

    Scanned rather than counted: quotes nest inside each other and inside regex
    literals, so counting them per line cannot tell a bug from an apostrophe.
    """
    from crossaudit.console.page import PAGE

    script = PAGE.split("<script>")[1].split("</script>")[0]
    quote = None
    line = 1
    i = 0
    while i < len(script):
        ch = script[i]
        if ch == "\n":
            assert quote is None, f"string literal left open at line {line}"
            line += 1
        elif quote:
            if ch == "\\":
                i += 1                       # an escape consumes the next character
            elif ch == quote:
                quote = None
        elif ch in "'\"`":
            quote = ch
        elif ch == "/" and i + 1 < len(script) and script[i + 1] not in "/*":
            # A regex literal: skip it whole, quotes and all.
            j = i + 1
            while j < len(script) and script[j] not in "/\n":
                j += 2 if script[j] == "\\" else 1
            if j < len(script) and script[j] == "/":
                i = j
        i += 1
    assert quote is None, "the script ends inside a string literal"


def test_the_page_never_reaches_outside_itself():
    """The CSP forbids it, but the page should not even try: everything inline."""
    from crossaudit.console.page import PAGE

    # The SVG XML namespace is an identifier, not a network location.  Keep the
    # standard namespace on inline data-URI icons while rejecting actual URLs.
    network_markup = PAGE.replace("xmlns='http://www.w3.org/2000/svg'", "")
    for forbidden in ("http://", "https://", "<script src", "<link "):
        assert forbidden not in network_markup, f"page references {forbidden!r}"


def test_the_page_source_is_raw_so_javascript_escapes_survive():
    """PAGE holds JavaScript, and JavaScript is full of backslashes. A plain
    Python string eats them: \\s becomes an invalid escape, \\n becomes a real
    newline, and the script breaks in ways whose only symptom is the form
    silently falling back to a native submit."""
    import inspect

    from crossaudit.console import page as page_mod

    src = inspect.getsource(page_mod)
    assert 'PAGE = r"""' in src, "PAGE must be a raw string"


def test_the_page_javascript_still_contains_its_regexes():
    from crossaudit.console.page import PAGE

    assert r"/\s+/g" in PAGE          # would be mangled by a non-raw string
    assert r"[&<>\"]" in PAGE or '[&<>"]' in PAGE


def test_console_has_one_primary_command_composer():
    """The dashboard may grow more controls, but it must keep one obvious
    write path so a task cannot be submitted twice by competing forms."""
    from crossaudit.console.page import PAGE

    assert PAGE.count('id="say"') == 1
    assert PAGE.count('id="send"') == 1
    assert '<textarea id="say"' in PAGE
    # The Swift menu clicks these two ids directly (New Task, Show Projects).
    assert PAGE.count('id="new-task"') == 1
    assert PAGE.count('id="projects-home"') == 1
    assert "New task" in PAGE
    assert "Run task" in PAGE
    assert "Shift+Enter for new line" in PAGE
    assert "Audit context" in PAGE
    assert "runtime-generator" in PAGE and "runtime-auditor" in PAGE
    assert "Audit loop" in PAGE
    assert "Audit gates reached" in PAGE
    assert "gates reached" in PAGE
    assert "Current gate" in PAGE and "Stopped at" in PAGE and "Next gate" in PAGE
    assert "Live activity" in PAGE and "Audit evidence" in PAGE
    assert "loop-focus" in PAGE and "audit-event" in PAGE
    assert 'id="task-choices"' not in PAGE
    assert "delivery_choices" not in PAGE
    assert "Auto-planning" in PAGE
    assert "Generator infers focus, format, tone, and structure" in PAGE
    assert 'id="project-type"' in PAGE
    assert "General work - documents, reviews, code" in PAGE
    assert "Scientific / data workflow" in PAGE
    assert "No CrossAudit file-count or file-size quota" in PAGE
    assert 'id="drop-overlay"' in PAGE and 'id="file-input" type="file" multiple' in PAGE
    assert "upload_batch" in PAGE and "batch_count" in PAGE
    assert "/api/upload" in PAGE and "uploadFile" in PAGE
    assert 'id="transfer-consent"' not in PAGE
    assert 'id="confirm-transfer"' not in PAGE
    assert "attachment_consent:pendingFiles.length>0" in PAGE
    assert "/api/file" in PAGE and "download" in PAGE
    assert "Files produced" in PAGE
    assert "output-file" in PAGE and "formatBytes" in PAGE
    assert "data-open-artifacts" in PAGE
    assert PAGE.count('id="theme-toggle"') == 1
    assert PAGE.count('id="settings-modal"') == 1
    assert PAGE.count('id="settings-open"') == 1
    assert "macOS Keychain" in PAGE and "/api/settings" in PAGE
    assert 'id="auditor-connection" required' in PAGE
    assert 'id="generator-connection" required' in PAGE
    assert "ChatGPT subscription" in PAGE and "/api/providers/connect" in PAGE
    assert "consumer subscriptions are different products" in PAGE
    assert "Automatic revision limit" in PAGE and "It never auto-passes" in PAGE
    assert "data-provider-key" in PAGE and "data-provider-remove" in PAGE
    assert "Get key ↗" in PAGE and "API docs ↗" in PAGE
    assert 'data-theme="dark"' in PAGE and "crossaudit-theme" in PAGE
    assert 'data-view="models"' in PAGE
    assert 'data-audience="auto"' in PAGE
    assert 'data-audience="generator"' in PAGE
    assert 'data-audience="auditor"' in PAGE
    assert "@Generator" in PAGE and "@Auditor" in PAGE
    assert "delivery-status" in PAGE and "data-open-audits" in PAGE
    assert "data-admit-cycle" in PAGE and "/api/admit" in PAGE
    assert "The result will appear in this conversation" in PAGE
    assert "Math.round(r.confidence*100)" not in PAGE
    assert "['passed','consumed'].includes(auditStatus(d,m.sha))" in PAGE
    assert "Tasks is direct user input/output, never a raw audit log" in PAGE
    assert 'data-view="artifacts"' in PAGE
    assert 'data-view="audits"' in PAGE
    assert 'data-view="usage"' in PAGE
    assert "Token usage" in PAGE and "API-value estimate" in PAGE
    assert "counts only · no prompt content" in PAGE
    assert PAGE.count('id="sidebar-toggle"') == 1
    assert PAGE.count('id="scrim"') == 1
    assert 'aria-controls="sidebar-panel"' in PAGE
    assert '@media(max-width:380px)' in PAGE
    assert 'distanceFromBottom < 80' in PAGE
