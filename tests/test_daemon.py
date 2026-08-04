"""The console outliving its terminal, and being found again afterwards.

Closing a window was never supposed to end a build. These tests hold the three
things that makes true: a second invocation reattaches instead of racing, a
stale record is not mistaken for a running process, and a build cut off
mid-round says so rather than reading as finished.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

import pytest

from crossaudit.config import load
from crossaudit.console import daemon, serve
from crossaudit.console.progress import Tracker

CONFIG = (
    "version: 1\nscience_repo: t/p\nconstitution: AUDIT_RULES.md\n"
    "auditor: {vendor: openai, provider: openai_compat, model: m,"
    " key_env: CROSSAUDIT_AUDITOR_KEY}\ngenerator: {vendor: anthropic}\n"
    "scope: {dirs: [work]}\nledger: {dir: cycles}\nstate: {dir: .crossaudit}\n"
    "checks: [parseable]\n")


@pytest.fixture()
def cfg(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    (root / "AUDIT_RULES.md").write_text("### CA-X-001\n**BLOCKER.** be exact\n\nx\n")
    (root / "crossaudit.yml").write_text(CONFIG)
    return load(root / "crossaudit.yml")


@pytest.fixture()
def running(cfg):
    url, httpd = serve(cfg, port=0, register=True)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield cfg, url
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()
        daemon.clear_run(cfg)


# ------------------------------------------------------------- finding it again
def test_a_running_console_can_be_found_by_a_later_invocation(running):
    cfg, url = running
    info = daemon.live(cfg)
    assert info is not None
    assert daemon.url_for(info) == url          # the same URL, token and all
    assert info["pid"] == os.getpid()


def test_liveness_uses_constant_time_health_not_the_expensive_state(running,
                                                                    monkeypatch):
    cfg, _url = running
    from crossaudit.console import server as server_mod

    monkeypatch.setattr(
        server_mod, "snapshot",
        lambda _cfg: (_ for _ in ()).throw(AssertionError("state must not run")))
    started = time.monotonic()
    assert daemon.live(cfg) is not None
    assert time.monotonic() - started < 0.5


def test_spawn_rechecks_liveness_inside_its_start_lock(cfg, monkeypatch):
    existing = {"pid": 7, "port": 8, "token": "already-running"}
    monkeypatch.setattr(daemon, "live", lambda _cfg: existing)
    monkeypatch.setattr(
        daemon.subprocess, "Popen",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("duplicate spawn")))
    assert daemon.spawn(cfg, 0) == existing
    assert not (cfg.root / cfg.state_dir / "console-start.lock").exists()


def test_the_run_file_is_not_world_readable(running):
    """It carries a session token; a credential readable by anyone on the box is
    a credential."""
    if os.name == "nt":
        pytest.skip("Windows uses inherited ACLs rather than POSIX permission bits")
    cfg, _url = running
    mode = daemon.run_path(cfg).stat().st_mode & 0o777
    assert mode == 0o600


def test_the_run_file_lives_outside_the_ledger(cfg, running):
    """A token committed to the ledger would be a token published."""
    _cfg, _url = running
    assert daemon.run_path(cfg).is_relative_to(cfg.root / cfg.state_dir)
    assert cfg.state_dir not in (cfg.ledger_dir,)


def test_nothing_is_found_when_nothing_is_running(cfg):
    assert daemon.live(cfg) is None


def test_a_stale_record_is_not_a_running_console(cfg):
    """A crash leaves the file behind; liveness is proven by the port answering,
    never by the file existing."""
    daemon.write_run(cfg, pid=999999, port=1, token="stale")
    assert daemon.read_run(cfg) is not None      # the file is there
    assert daemon.live(cfg) is None              # and it means nothing
    assert not daemon.run_path(cfg).exists()     # and it is cleaned up


def test_a_corrupt_record_is_survived(cfg):
    p = daemon.run_path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not json")
    assert daemon.read_run(cfg) is None and daemon.live(cfg) is None


def test_stopping_when_nothing_runs_says_so(cfg):
    assert "no console" in daemon.stop(cfg)


# -------------------------------------------------------- interrupted builds
def test_a_build_in_flight_from_a_dead_process_reads_as_interrupted(cfg):
    daemon.mark_build(cfg, "write the section")
    # Rewrite the flag as if another, now-dead process had left it.
    flag = json.loads(daemon.flag_path(cfg).read_text())
    flag["pid"] = 999999
    daemon.flag_path(cfg).write_text(json.dumps(flag))
    found = daemon.interrupted(cfg)
    assert found and found["task"] == "write the section"


def test_our_own_running_build_is_not_reported_as_interrupted(cfg):
    daemon.mark_build(cfg, "still going")
    assert daemon.interrupted(cfg) is None


def test_caught_worker_failure_remains_recoverable_in_the_same_process(cfg):
    daemon.mark_build(cfg, "recover this", chat_id="history")
    daemon.mark_failed(cfg, "failed", "RuntimeError: worker stopped")
    found = daemon.interrupted(cfg)
    assert found["task"] == "recover this"
    assert found["phase"] == "failed" and found["failed"] is True


def test_a_finished_build_leaves_nothing_behind(cfg):
    daemon.mark_build(cfg, "done soon")
    daemon.unmark_build(cfg)
    assert daemon.interrupted(cfg) is None
    assert not daemon.flag_path(cfg).exists()


def test_the_state_endpoint_surfaces_an_interruption(running):
    cfg, url = running
    daemon.mark_build(cfg, "cut off mid-round")
    flag = json.loads(daemon.flag_path(cfg).read_text())
    flag["pid"] = 999999
    daemon.flag_path(cfg).write_text(json.dumps(flag))

    import urllib.request

    with urllib.request.urlopen(url.replace("/?", "/api/state?"), timeout=5) as r:
        data = json.loads(r.read())
    assert data["interrupted"]["task"] == "cut off mid-round"
    daemon.unmark_build(cfg)


def test_interrupted_notice_can_be_dismissed_through_the_ui_api(running):
    cfg, url = running
    daemon.mark_build(cfg, "preserve this work")
    flag = json.loads(daemon.flag_path(cfg).read_text())
    flag["pid"] = 999999
    daemon.flag_path(cfg).write_text(json.dumps(flag))

    import urllib.request

    endpoint = url.replace("/?", "/api/interrupted?")
    request = urllib.request.Request(
        endpoint, data=b'{"action":"dismiss"}', method="POST",
        headers={"content-type": "application/json"})
    with urllib.request.urlopen(request, timeout=5) as response:
        result = json.loads(response.read())
    assert result == {"dismissed": True, "working_tree_preserved": True}
    assert daemon.interrupted(cfg) is None


# ---------------------------------------------------------------- idle policy
def test_a_running_build_keeps_the_console_alive(cfg, monkeypatch):
    """The whole point: a closed window must not end a build. Idleness is only
    grounds for shutting down when nothing is in flight."""
    import crossaudit.console.server as server_mod

    tracker = Tracker()
    tracker.start("long job")
    monkeypatch.setattr(server_mod, "TRACKER", tracker)

    url, httpd = serve(cfg, port=0, idle_timeout=0.05)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        import time
        import urllib.request

        time.sleep(0.4)                          # well past the idle timeout
        with urllib.request.urlopen(url.replace("/?", "/api/state?"), timeout=5) as r:
            assert r.status == 200               # still up, because work is running
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()
        daemon.clear_run(cfg)


def test_closing_a_console_reclaims_its_idle_watcher(cfg):
    _url, httpd = serve(cfg, port=0, idle_timeout=float("inf"))
    serving = threading.Thread(target=httpd.serve_forever)
    serving.start()

    httpd.shutdown()
    serving.join(timeout=5)
    httpd.server_close()

    assert not serving.is_alive()
    assert httpd.idle_thread is not None and not httpd.idle_thread.is_alive()


def test_an_open_realtime_stream_cannot_block_native_app_shutdown(cfg):
    url, httpd = serve(cfg, port=0, idle_timeout=float("inf"))
    serving = threading.Thread(target=httpd.serve_forever)
    serving.start()
    stream = urllib.request.urlopen(
        url.replace("/?", "/api/stream?"), timeout=5)  # nosec B310
    try:
        assert stream.readline().startswith(b"data: ")
        started = time.monotonic()
        httpd.shutdown()
        serving.join(timeout=2)
        httpd.server_close()
        assert not serving.is_alive()
        assert time.monotonic() - started < 2
    finally:
        stream.close()


# ------------------------------------------- stopping a background console
def test_the_signal_handler_never_blocks_the_loop_it_is_stopping():
    """`shutdown()` waits for `serve_forever()` to return, and `serve_forever()`
    is suspended inside the handler. Called there it deadlocks the process into
    an orphan: run record deleted, port held, answering nothing, and already
    inside the handler so a second signal changes nothing.

    Nothing else in the suite fails if this is reverted, which is why it has a
    test of its own.
    """
    import re

    src = (Path(__file__).resolve().parents[1] / "src" / "crossaudit" / "cli"
           / "main.py").read_text()
    body = re.search(r"def bye\(\*_a\) -> None:\n(.*?)signal\.signal", src, re.S).group(1)
    assert "httpd.shutdown" in body
    assert "Thread" in body, "shutdown() must not run on the serving thread"
    assert "clear_run" not in body, (
        "clearing the record from the handler orphans a process that has not died")


def test_the_record_outlives_a_stop_that_did_not_work(cfg, monkeypatch):
    """The run file is the only way to find the process again. Deleting it while
    the process lives is what turns a failed stop into a permanent orphan."""
    from crossaudit.console import daemon

    daemon.write_run(cfg, pid=999999, port=1, token="t")
    monkeypatch.setattr(daemon.os, "kill", lambda *a: None)      # signals vanish
    monkeypatch.setattr(daemon, "_gone", lambda pid, tries: False)

    said = daemon.stop(cfg)
    assert "did not stop" in said
    assert daemon.read_run(cfg) is not None, "the record was thrown away"


def test_a_stop_that_worked_clears_the_record(cfg, monkeypatch):
    from crossaudit.console import daemon

    daemon.write_run(cfg, pid=999999, port=1, token="t")
    monkeypatch.setattr(daemon.os, "kill", lambda *a: None)
    monkeypatch.setattr(daemon, "_gone", lambda pid, tries: True)

    assert "stopped" in daemon.stop(cfg)
    assert daemon.read_run(cfg) is None


def test_stop_escalates_when_the_polite_signal_is_ignored(cfg, monkeypatch):
    """A daemon can inherit SIG_IGN for SIGTERM from whatever started it. The
    stop path has to be able to insist."""
    import signal as sig

    from crossaudit.console import daemon

    daemon.write_run(cfg, pid=999999, port=1, token="t")
    sent = []
    monkeypatch.setattr(daemon.os, "kill", lambda pid, s: sent.append(s))
    monkeypatch.setattr(daemon, "_gone",
                        lambda pid, tries: len(sent) >= 2)

    daemon.stop(cfg)
    assert sent == [sig.SIGTERM, daemon.KILL_SIGNAL]


def test_a_zombie_is_already_gone_even_if_kill_zero_succeeds(monkeypatch):
    monkeypatch.setattr(daemon, "_zombie", lambda pid: True)
    monkeypatch.setattr(daemon.os, "kill",
                        lambda *a: (_ for _ in ()).throw(AssertionError("not needed")))
    assert daemon._gone(12345, tries=1) is True


def test_windows_pid_probe_never_uses_kill_zero(monkeypatch):
    seen = []
    monkeypatch.setattr(daemon.os, "name", "nt")
    monkeypatch.setattr(daemon, "_windows_pid_alive",
                        lambda pid: seen.append(pid) or True)
    monkeypatch.setattr(daemon.os, "kill",
                        lambda *a: (_ for _ in ()).throw(AssertionError("unsafe")))
    assert daemon._pid_alive(12345) is True
    assert seen == [12345]


def test_workspace_capacity_is_cross_project_and_recoverable(cfg, tmp_path, monkeypatch):
    from crossaudit.errors import ConfigDenial

    monkeypatch.setenv("CROSSAUDIT_MAX_ACTIVE_PROJECTS", "1")
    other_root = tmp_path / "other"
    other_root.mkdir()
    (other_root / "AUDIT_RULES.md").write_text("### CA-X-001\n**BLOCKER.** exact\n")
    (other_root / "crossaudit.yml").write_text(CONFIG)
    other = load(other_root / "crossaudit.yml")
    slot = daemon.acquire_workspace_slot(cfg)
    assert daemon.workspace_capacity(cfg)["active"] == 1
    with pytest.raises(ConfigDenial, match="capacity is 1"):
        daemon.acquire_workspace_slot(other)
    daemon.release_workspace_slot(slot)
    other_slot = daemon.acquire_workspace_slot(other)
    assert other_slot.is_file()
    daemon.release_workspace_slot(other_slot)


def test_stale_workspace_slots_are_reclaimed(cfg):
    base = daemon._runtime_dir(cfg)
    base.mkdir(parents=True, exist_ok=True)
    (base / "slot-dead.json").write_text(json.dumps({"pid": 999999,
                                                      "root": "/gone"}))
    assert daemon.workspace_capacity(cfg)["active"] == 0
    assert not (base / "slot-dead.json").exists()
