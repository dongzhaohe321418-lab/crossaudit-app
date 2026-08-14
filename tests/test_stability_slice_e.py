"""Stability hardening — Slice E: background resources and streams stay healthy.

E1  App-mode per-project daemons take a FINITE idle timeout so a daemon with no
    run in flight, no connected SSE client and no recent request self-retires,
    instead of accumulating forever behind ``idle_timeout=inf``. A daemon doing
    real work — an active run (``TRACKER.running``) OR a live stream
    (``active_streams``) — is never reaped.
E2  The multi-project overview probes sibling daemons concurrently on a bounded
    pool under one deadline, so a wedged daemon costs one timeout for the whole
    list rather than one per project, and healthy rows stay identical.
E3  Accepted SSE sockets get SO_KEEPALIVE so a silently-dead peer surfaces in
    seconds-to-minutes instead of the OS default of many minutes, without ever
    dropping a slow-but-alive client.
"""
from __future__ import annotations

import re
import socket
import threading
import time
import urllib.request
from pathlib import Path

import pytest

from crossaudit.config import load
from crossaudit.console import daemon, serve
from crossaudit.console import projects as projects_mod
from crossaudit.console import server as server_mod

CONFIG = (
    "version: 1\nscience_repo: t/p\nconstitution: AUDIT_RULES.md\n"
    "auditor: {vendor: openai, provider: openai_compat, model: m,"
    " key_env: CROSSAUDIT_AUDITOR_KEY}\ngenerator: {vendor: anthropic}\n"
    "scope: {dirs: [work]}\nledger: {dir: cycles}\nstate: {dir: .crossaudit}\n"
    "checks: [parseable]\n")


def _make_project(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    (root / "AUDIT_RULES.md").write_text("### CA-X-001\n**BLOCKER.** be exact\n\nx\n")
    (root / "crossaudit.yml").write_text(CONFIG)
    return load(root / "crossaudit.yml")


@pytest.fixture()
def cfg(tmp_path: Path):
    return _make_project(tmp_path / "proj")


def _serve_bg(cfg, **kw):
    url, httpd = serve(cfg, port=0, **kw)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return url, httpd, thread


def _teardown(httpd, thread, cfg):
    httpd.shutdown()
    thread.join(timeout=5)
    httpd.server_close()
    daemon.clear_run(cfg)


def _wait(predicate, timeout=4.0, step=0.02) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(step)
    return predicate()


# --------------------------------------------------------------------- E1 unit
def test_the_idle_predicate_never_expires_while_a_run_is_in_flight():
    # A closed window must not end a running build: an active run holds the
    # console open no matter how long since the last request.
    assert server_mod._idle_expired(
        running=True, active_streams=0, idle_seconds=10_000, timeout=1) is False


def test_the_idle_predicate_never_expires_while_a_stream_is_connected():
    # A still-open project window (a live SSE client) is real work too and must
    # never be reaped from under the viewer.
    assert server_mod._idle_expired(
        running=False, active_streams=1, idle_seconds=10_000, timeout=1) is False


def test_the_idle_predicate_expires_only_a_truly_idle_console():
    assert server_mod._idle_expired(
        running=False, active_streams=0, idle_seconds=2, timeout=1) is True
    assert server_mod._idle_expired(
        running=False, active_streams=0, idle_seconds=0.5, timeout=1) is False


def test_project_daemons_take_a_finite_generous_idle_timeout():
    # The whole E1 bug: project_console passed idle_timeout=float("inf").
    assert server_mod.PROJECT_IDLE_TIMEOUT_S != float("inf")
    assert 15 * 60 <= server_mod.PROJECT_IDLE_TIMEOUT_S <= 30 * 60
    src = (Path(server_mod.__file__).resolve().parents[1] / "app.py").read_text()
    body = re.search(r"def project_console.*?httpd = serve\((.*?)\)",
                     src, re.DOTALL).group(1)
    assert "float(\"inf\")" not in body and "float('inf')" not in body
    assert "PROJECT_IDLE_TIMEOUT_S" in body


# ---------------------------------------------------------------- E1 behaviour
def test_an_idle_project_daemon_self_retires(cfg, monkeypatch):
    monkeypatch.setattr(server_mod, "IDLE_POLL_S", 0.05)
    _url, httpd, thread = _serve_bg(cfg, idle_timeout=0.05)
    try:
        # No run, no client, no request: it must shut itself down.
        assert _wait(httpd.stop_event.is_set), "an idle daemon must self-retire"
        assert httpd.active_streams == 0
    finally:
        _teardown(httpd, thread, cfg)


def test_a_running_daemon_never_retires_past_its_window(cfg, monkeypatch):
    from crossaudit.console.progress import Tracker
    from crossaudit.runtime import RunJournal, journal_path

    tracker = Tracker()
    tracker.bind(journal_path(cfg))
    RunJournal(journal_path(cfg)).start("long job")
    monkeypatch.setattr(server_mod, "TRACKER", tracker)
    monkeypatch.setattr(server_mod, "IDLE_POLL_S", 0.05)

    _url, httpd, thread = _serve_bg(cfg, idle_timeout=0.05)
    try:
        assert tracker.running
        time.sleep(0.4)                       # many idle ticks past the window
        assert not httpd.stop_event.is_set(), "a run in flight was reaped"
    finally:
        _teardown(httpd, thread, cfg)


def test_a_live_stream_holds_an_otherwise_idle_daemon_open(cfg, monkeypatch):
    # idle_timeout (0.2s) is far below the 15s heartbeat, so touch() alone would
    # let the console look idle after the first frame; the active_streams guard
    # is what keeps a streamed-to daemon alive.
    monkeypatch.setattr(server_mod, "IDLE_POLL_S", 0.05)
    url, httpd, thread = _serve_bg(cfg, idle_timeout=0.2)
    stream = None
    try:
        stream = urllib.request.urlopen(       # nosec B310 — loopback test URL
            url.replace("/?", "/api/stream?"), timeout=5)
        line = stream.readline()
        while line and not line.startswith(b"data:"):
            line = stream.readline()
        assert line.startswith(b"data:")       # connected and streaming
        assert _wait(lambda: httpd.active_streams >= 1)
        time.sleep(0.6)                        # well past the idle window
        assert not httpd.stop_event.is_set(), "a live stream was reaped"
        assert httpd.active_streams >= 1
    finally:
        if stream is not None:
            stream.close()
        _teardown(httpd, thread, cfg)


# ------------------------------------------------------------- E2 fan-out
def _fake_state(port: int) -> dict:
    return {"progress": {"task": f"task-{port}", "finished": False,
                         "elapsed": 5,
                         "steps": [{"actor": "generator", "text": "working"}]}}


def _running_siblings(tmp_path: Path, count: int) -> list:
    sibs = []
    for i in range(count):
        cfg = _make_project(tmp_path / f"sib{i}")
        daemon.write_run(cfg, pid=10_000 + i, port=20_000 + i, token=f"t{i}")
        sibs.append(cfg)
    return sibs


def test_sibling_fanout_pays_one_timeout_not_n(tmp_path, monkeypatch):
    projects_mod._RUNTIME_CACHE.clear()
    sleep_s, count = 0.3, 6                     # count <= pool workers (8)

    def slow_fetch(info, timeout=0.5):
        time.sleep(sleep_s)
        return _fake_state(int(info["port"]))

    monkeypatch.setattr(daemon, "fetch_state", slow_fetch)
    current = _make_project(tmp_path / "current")
    sibs = _running_siblings(tmp_path, count)
    paths = [c.root for c in sibs]

    started = time.monotonic()
    prewarmed = projects_mod._prewarm_siblings(paths, current)
    elapsed = time.monotonic() - started

    # Serial would be count*sleep_s (1.8s); concurrent is ~one timeout.
    assert elapsed < 3 * sleep_s, (
        f"fan-out was not concurrent: {elapsed:.2f}s for {count} slow siblings")
    assert elapsed < 0.75 * count * sleep_s
    assert len(prewarmed) == count
    # Each sibling maps to ITS OWN fetched state — no cross-contamination.
    for c in sibs:
        info = daemon.read_run(c)
        assert prewarmed[str(c.root)] == _fake_state(int(info["port"]))


def test_fanned_out_rows_are_identical_to_the_serial_path(tmp_path, monkeypatch):
    projects_mod._RUNTIME_CACHE.clear()

    def fetch(info, timeout=0.5):
        return _fake_state(int(info["port"]))

    monkeypatch.setattr(daemon, "fetch_state", fetch)
    current = _make_project(tmp_path / "current")
    (sib,) = _running_siblings(tmp_path, 1)

    prewarmed = projects_mod._prewarm_siblings([sib.root], current)
    parallel = projects_mod._runtime(sib, current, prewarmed)

    projects_mod._RUNTIME_CACHE.clear()
    serial = projects_mod._runtime(sib, current)      # original serial path

    expected = projects_mod._progress_from_state(_fake_state(20_000))
    assert parallel == serial == expected
    assert parallel["task"] == "task-20000"


def test_a_wedged_sibling_does_not_delay_the_healthy_ones(tmp_path, monkeypatch):
    projects_mod._RUNTIME_CACHE.clear()

    def mixed_fetch(info, timeout=0.5):
        if int(info["port"]) == 20_000:            # the wedged one
            time.sleep(0.4)
        return _fake_state(int(info["port"]))

    monkeypatch.setattr(daemon, "fetch_state", mixed_fetch)
    current = _make_project(tmp_path / "current")
    sibs = _running_siblings(tmp_path, 5)

    started = time.monotonic()
    prewarmed = projects_mod._prewarm_siblings([c.root for c in sibs], current)
    elapsed = time.monotonic() - started

    assert elapsed < 0.8, f"one wedged daemon serialised the rest: {elapsed:.2f}s"
    for c in sibs:                                  # all still resolved
        info = daemon.read_run(c)
        assert prewarmed[str(c.root)] == _fake_state(int(info["port"]))


def test_the_fanout_pool_is_bounded():
    assert projects_mod._FANOUT_WORKERS <= 8
    pool = projects_mod._fanout_pool()
    assert pool._max_workers <= 8
    assert projects_mod._fanout_pool() is pool     # one shared, reused pool


# --------------------------------------------------------------------- E3
def _keepalive_on(sock) -> bool:
    try:
        return sock.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE) != 0
    except OSError:
        return False


def test_enable_keepalive_turns_it_on_and_is_platform_safe():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        assert not _keepalive_on(sock)             # off by default
        server_mod._enable_keepalive(sock)
        assert _keepalive_on(sock)                 # on afterwards
    finally:
        sock.close()


def test_accepted_stream_sockets_get_keepalive_and_still_stream(cfg, monkeypatch):
    seen: list = []
    real = server_mod._enable_keepalive

    def spy(conn):
        real(conn)
        seen.append(conn)

    monkeypatch.setattr(server_mod, "_enable_keepalive", spy)
    url, httpd, thread = _serve_bg(cfg, idle_timeout=float("inf"))
    stream = None
    try:
        stream = urllib.request.urlopen(       # nosec B310 — loopback test URL
            url.replace("/?", "/api/stream?"), timeout=5)
        assert stream.readline().startswith(b"data:")   # a slow-but-alive client
        assert seen, "get_request did not enable keepalive on accepted sockets"
        assert any(_keepalive_on(s) for s in seen)
    finally:
        if stream is not None:
            stream.close()
        _teardown(httpd, thread, cfg)
