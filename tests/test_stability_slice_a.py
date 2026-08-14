"""Stability hardening Slice A: nothing blocks forever.

Three "blocks forever" bugs are closed here, each with a regression test that
uses a real subprocess, a real socket, or the real state machine — not a
synthetic seam:

* A1 — ``gitio.git`` is bounded, so a hung git (stale index.lock, a blocking
  hook, a credential/GPG prompt) raises ``ConfigDenial`` instead of pinning the
  run in an ACTIVE state; a commit timeout surfaces to the loop as
  ``commit_refused`` and reaches a terminal state.
* A2 — provider HTTP enforces a TOTAL wall-clock deadline, so a trickled
  response body aborts at the budget as a retryable timeout instead of running
  one attempt indefinitely; a normal fast response is unaffected.
* A3 — a run stuck in CANCELLING whose worker never acknowledges is
  force-completed to CANCELLED after the stall grace window, freeing the
  single-run guard — while a verified-alive run in any other ACTIVE state is
  STILL never reclaimed.
"""
from __future__ import annotations

import os
import socket
import sqlite3
import threading
import time
import urllib.request
from pathlib import Path

import pytest

import crossaudit.providers.base as base
from crossaudit.errors import EXIT_ESCALATED, ConfigDenial, ProviderDenial
from crossaudit.runtime import LEASE_SECONDS, RunEvent, RunJournal, RunState
from crossaudit.runtime.processes import process_identity
from crossaudit.runtime.runs import STALL_AFTER_SECONDS

#: A pid that can never be alive, so the classification is deterministic
#: without spawning a real process where the identity is injected anyway.
FOREIGN_PID = 999999


# =========================================================================== A1
def test_git_call_is_bounded_and_raises_configdenial_on_hang(tmp_path, monkeypatch):
    """A git that never returns is abandoned at the timeout, not waited on.

    A real ``git`` shim on PATH that sleeps far past the (env-lowered) bound
    stands in for a stale index.lock or a blocking hook.
    """
    from crossaudit import gitio

    bindir = tmp_path / "bin"
    bindir.mkdir()
    shim = bindir / "git"
    shim.write_text("#!/bin/sh\nexec sleep 30\n")   # exec: kill reaches sleep
    shim.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("CROSSAUDIT_GIT_TIMEOUT", "1")

    start = time.monotonic()
    with pytest.raises(ConfigDenial) as excinfo:
        gitio.git("rev-parse", "HEAD", cwd=tmp_path)
    elapsed = time.monotonic() - start

    assert elapsed < 10          # bounded — it did not hang for the full 30s
    assert "did not finish" in excinfo.value.reason


def test_git_timeout_is_env_overridable_and_defaults_generous():
    from crossaudit import gitio

    assert gitio.GIT_TIMEOUT_S >= 120           # generous enough for real commits
    os.environ.pop("CROSSAUDIT_GIT_TIMEOUT", None)
    assert gitio._git_timeout() == gitio.GIT_TIMEOUT_S
    try:
        os.environ["CROSSAUDIT_GIT_TIMEOUT"] = "17"
        assert gitio._git_timeout() == 17.0
        os.environ["CROSSAUDIT_GIT_TIMEOUT"] = "garbage"   # falls back, not crash
        assert gitio._git_timeout() == gitio.GIT_TIMEOUT_S
    finally:
        os.environ.pop("CROSSAUDIT_GIT_TIMEOUT", None)


def test_commit_timeout_surfaces_to_the_loop_as_commit_refused(
        science, cfg, monkeypatch):
    """A real pre-commit hook that hangs makes the loop's commit time out; the
    loop reports ``commit_refused`` and stops at a terminal state rather than
    wedging the run. ``git add``/``rev-parse`` do not run the hook, so only the
    commit is affected."""
    from crossaudit import generator as generator_mod
    from crossaudit.cli import build as build_mod

    hooks = science / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    hook = hooks / "pre-commit"
    hook.write_text("#!/bin/sh\nexec sleep 30\n")
    hook.chmod(0o755)
    monkeypatch.setenv("CROSSAUDIT_GIT_TIMEOUT", "2")

    def fake_generate(**_kwargs):
        return generator_mod.Work(
            summary="one attempt",
            files={"experiments/demo/SUMMARY.md": "an attempt\n"})

    monkeypatch.setattr(build_mod, "_generator_complete", lambda *_a, **_k: object())
    monkeypatch.setattr(build_mod.gen_mod, "generate", fake_generate)
    monkeypatch.chdir(science)

    events: list[RunEvent] = []
    code = build_mod.run_loop(cfg, "produce the experiment",
                              on_event=events.append)

    assert code == EXIT_ESCALATED
    kinds = [e.kind for e in events]
    assert "commit_refused" in kinds
    # It stopped at the commit, before any audit round could begin.
    assert "audit_started" not in kinds


# =========================================================================== A2
class _TricklingServer:
    """A one-shot local HTTP server that dribbles the response body.

    Real socket, real thread, real time: the total-deadline logic is exercised
    against a genuinely slow peer, not an injected clock.
    """

    def __init__(self, body: bytes, *, trickle: bool, per_byte: float = 0.05):
        self.body = body
        self.trickle = trickle
        self.per_byte = per_byte
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_exc):
        try:
            self.sock.close()
        except OSError:
            pass
        self._thread.join(timeout=3)

    def _serve(self):
        try:
            conn, _ = self.sock.accept()
        except OSError:
            return
        with conn:
            try:
                conn.settimeout(5)
                request = b""
                while b"\r\n\r\n" not in request:      # drain request headers
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    request += chunk
                conn.sendall(
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Type: application/json\r\n"
                    b"Content-Length: %d\r\n"
                    b"Connection: close\r\n\r\n" % len(self.body))
                if self.trickle:
                    for i in range(len(self.body)):
                        conn.sendall(self.body[i:i + 1])
                        time.sleep(self.per_byte)
                else:
                    conn.sendall(self.body)
                # Clean close: signal EOF, then drain the rest of the client's
                # request. An unread POST body left in the receive buffer makes
                # close() send RST, which races the client's response read and
                # surfaces as a flaky ConnectionResetError.
                conn.shutdown(socket.SHUT_WR)
                while conn.recv(4096):
                    pass
            except OSError:
                pass          # the client aborted at its deadline; expected


@pytest.fixture()
def _http_opener(monkeypatch):
    """Swap the HTTPS opener for a plain-HTTP one so the read loop under test
    can be exercised over a real local socket without a certificate. Only the
    transport handler changes; the body-read path is identical for http/https."""
    real_build_opener = urllib.request.build_opener   # capture before patching

    def fake_build_opener(*_handlers):
        # Drop the HTTPS handler; keep the no-redirect policy. Uses the captured
        # real builder so it cannot recurse into this patch.
        return real_build_opener(base._NoRedirect)

    monkeypatch.setattr(base.urllib.request, "build_opener", fake_build_opener)


def test_a_trickled_body_aborts_at_the_total_deadline_as_retryable(_http_opener):
    body = b'{"message": "this body is delivered one slow byte at a time so it"}'
    with _TricklingServer(body, trickle=True) as server:
        url = f"http://127.0.0.1:{server.port}/v1/messages"
        start = time.monotonic()
        with pytest.raises(ProviderDenial) as excinfo:
            base.request_json(url, {"hi": "there"}, {}, timeout=0.5)
        elapsed = time.monotonic() - start

    # Aborted near the 0.5s deadline, well before the ~3s full trickle.
    assert elapsed < 2.0
    assert excinfo.value.detail.get("category") == "timeout"
    assert excinfo.value.detail.get("retryable") is True


def test_a_normal_fast_response_is_unaffected(_http_opener):
    body = b'{"message": "fast"}'
    with _TricklingServer(body, trickle=False) as server:
        url = f"http://127.0.0.1:{server.port}/v1/messages"
        start = time.monotonic()
        parsed, _rid = base.request_json(url, {"hi": "there"}, {}, timeout=5.0)
        elapsed = time.monotonic() - start

    assert parsed == {"message": "fast"}
    assert elapsed < 1.0          # nothing slowed the normal path down


def test_get_json_also_enforces_the_total_deadline(_http_opener):
    body = b'{"models": "this list is also delivered as a slow byte trickle!!"}'
    with _TricklingServer(body, trickle=True) as server:
        url = f"http://127.0.0.1:{server.port}/v1/models"
        with pytest.raises(ProviderDenial) as excinfo:
            base.get_json(url, {}, timeout=0.5)
    assert excinfo.value.detail.get("category") == "timeout"
    assert excinfo.value.detail.get("retryable") is True


# =========================================================================== A3
def _ticking(start: float = 1000.0):
    """A controllable clock so grace windows are testable without real minutes."""
    state = {"now": start}

    def clock() -> float:
        return state["now"]

    clock.advance = lambda seconds: state.__setitem__("now", state["now"] + seconds)
    return clock


def _event(state: RunState) -> RunEvent:
    return RunEvent(actor="loop", text="writing", state=state)


def _set_token(journal: RunJournal, run_id: str, token: str) -> None:
    with sqlite3.connect(journal.path) as db:
        db.execute("UPDATE runs SET owner_token=? WHERE run_id=?", (token, run_id))


def test_cancelling_verified_alive_owner_is_force_completed_past_the_grace(tmp_path):
    """A verified-alive worker that wedges in CANCELLING (never acknowledging)
    is force-completed once the cancel lease goes stall-silent — but not
    before."""
    clock = _ticking()
    journal = RunJournal(tmp_path / "runtime.sqlite3", clock=clock)
    run_id = journal.start("wedged worker", owner_pid=FOREIGN_PID)
    journal.append(run_id, _event(RunState.GENERATING))
    _set_token(journal, run_id, "v2:999999:marker")
    journal.request_cancel(run_id)                       # -> CANCELLING
    verified = lambda _pid: "v2:999999:marker"           # identity matches token

    # Before the grace window: a verified-alive worker still owns the ack.
    assert journal.recover_abandoned(
        current_pid=os.getpid(), alive=lambda _pid: True,
        is_zombie=lambda _pid: False, identity=verified,
        sleep=lambda _s: None) == []
    assert journal.state(run_id) == RunState.CANCELLING

    clock.advance(STALL_AFTER_SECONDS + 1)               # cancel lease goes silent
    recovered = journal.recover_abandoned(
        current_pid=os.getpid(), alive=lambda _pid: True,
        is_zombie=lambda _pid: False, identity=verified, sleep=lambda _s: None)

    assert recovered == [run_id]
    assert journal.state(run_id) == RunState.CANCELLED
    assert journal.latest()["outcome"] == "cancelled"


def test_own_process_cancelling_frees_the_single_run_guard_after_grace(tmp_path):
    """The common case: the worker is a daemon thread in this very process, so
    the owner pid is our own and its token is current. A wedge here would hold
    the single-run guard forever; the bounded completion frees it."""
    clock = _ticking()
    journal = RunJournal(tmp_path / "runtime.sqlite3", clock=clock)
    run_id = journal.start("daemon-thread worker wedged")  # own pid + current token
    journal.append(run_id, _event(RunState.GENERATING))
    journal.request_cancel(run_id)

    # The single-run guard is held while CANCELLING.
    with pytest.raises(RuntimeError):
        journal.start("a new build")

    clock.advance(STALL_AFTER_SECONDS + 1)
    recovered = journal.recover_abandoned(
        alive=lambda _pid: True,
        identity=lambda _pid: process_identity(os.getpid()),
        is_zombie=lambda _pid: False, sleep=lambda _s: None)

    assert recovered == [run_id]
    assert journal.state(run_id) == RunState.CANCELLED
    # The slot is free again — a new build can start.
    new_id = journal.start("a new build")
    assert journal.state(new_id) == RunState.QUEUED


def test_a_verified_alive_active_run_is_never_reclaimed_even_past_the_grace(tmp_path):
    """The invariant the A3 branch must NOT weaken: a verified-alive worker in
    an ACTIVE non-CANCELLING state is never reclaimed, no matter how long it has
    been silent. Only CANCELLING gets the bounded backstop."""
    clock = _ticking()
    journal = RunJournal(tmp_path / "runtime.sqlite3", clock=clock)
    run_id = journal.start("long clean generation", owner_pid=FOREIGN_PID)
    journal.append(run_id, _event(RunState.GENERATING))
    _set_token(journal, run_id, "v2:999999:marker")
    verified = lambda _pid: "v2:999999:marker"

    # Silence far past the CANCELLING grace window — irrelevant here.
    clock.advance(STALL_AFTER_SECONDS * 3)
    recovered = journal.recover_abandoned(
        current_pid=os.getpid(), alive=lambda _pid: True,
        is_zombie=lambda _pid: False, identity=verified, sleep=lambda _s: None)

    assert recovered == []
    assert journal.state(run_id) == RunState.GENERATING


def test_a_heartbeat_during_cancelling_defers_the_forced_completion(tmp_path):
    """A worker still heartbeating in CANCELLING is making progress on the
    cancel; its renewed lease resets the grace window, so it is not
    force-completed. Only a genuinely silent CANCELLING run is."""
    clock = _ticking()
    journal = RunJournal(tmp_path / "runtime.sqlite3", clock=clock)
    run_id = journal.start("cancelling but still alive")
    journal.append(run_id, _event(RunState.GENERATING))
    journal.request_cancel(run_id)

    clock.advance(STALL_AFTER_SECONDS - 10)
    assert journal.heartbeat(run_id) is True             # renews the lease
    # Even now-ish past the ORIGINAL cancel lease, the renewed lease defers it.
    clock.advance(20)
    recovered = journal.recover_abandoned(
        alive=lambda _pid: True,
        identity=lambda _pid: process_identity(os.getpid()),
        is_zombie=lambda _pid: False, sleep=lambda _s: None)
    assert recovered == []
    assert journal.state(run_id) == RunState.CANCELLING

    # Once the renewed lease also goes silent, it completes.
    clock.advance(STALL_AFTER_SECONDS + 1)
    recovered = journal.recover_abandoned(
        alive=lambda _pid: True,
        identity=lambda _pid: process_identity(os.getpid()),
        is_zombie=lambda _pid: False, sleep=lambda _s: None)
    assert recovered == [run_id]
    assert journal.state(run_id) == RunState.CANCELLED
