"""Owner-identity recovery, exercised against the real operating system.

The R2 identity work introduced a corruption-class bug: the owner token was
``ps -o lstart=`` rendered in the *caller's* locale/timezone, so a supervisor
in a different environment than the worker computed a different token for the
same live pid and reclaimed a healthy run — breaking the single-active-run
invariant. These tests reconstruct that exact cross-process env mismatch with
real subprocesses and the real ``process_identity`` probe (no injected
synthetic identity), which is the only way to catch a locale-poisoning bug:
an injected callable is identical in every process by construction and would
have hidden it.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

from crossaudit.runtime import RunJournal, RunState, journal_path, pid_alive
from crossaudit.runtime.processes import (IDENTITY_TOKEN_PREFIX,
                                          process_identity, zombie)
from crossaudit.runtime.runs import LEASE_SECONDS

pytestmark = pytest.mark.skipif(
    os.name == "nt", reason="POSIX process-identity semantics")

SRC_DIR = str(Path(__file__).resolve().parents[1] / "src")

# A worker that starts a run under THIS process's environment (recording its
# own identity token) and then heartbeats so the lease stays fresh — the lease
# is never the thing under test here, the identity comparison is.
_WORKER = """
import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from crossaudit.runtime.runs import RunJournal
journal = RunJournal(Path(sys.argv[2]))
run_id = journal.start("healthy in-flight run")
print(run_id, flush=True)
for _ in range(3000):
    journal.heartbeat(run_id)
    time.sleep(0.2)
"""


def _spawn_worker(tmp_path: Path, db: Path, env_overrides: dict) -> tuple:
    script = tmp_path / "identity_worker.py"
    script.write_text(_WORKER)
    env = {**os.environ, "PYTHONPATH": SRC_DIR, **env_overrides}
    proc = subprocess.Popen(
        [sys.executable, str(script), SRC_DIR, str(db)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    run_id = proc.stdout.readline().strip()          # blocks until start() done
    if not run_id:
        proc.terminate()
        raise AssertionError(f"worker did not start: {proc.stderr.read()}")
    return proc, run_id


@pytest.mark.parametrize("worker_env,supervisor_tz", [
    ({"TZ": "Asia/Shanghai"}, "UTC"),                # timezone mismatch
    ({"LC_ALL": "fr_FR.UTF-8", "LANG": "fr_FR.UTF-8"}, "UTC"),  # locale
])
def test_env_mismatch_between_worker_and_supervisor_never_reclaims(
        tmp_path, monkeypatch, worker_env, supervisor_tz):
    """A live, heartbeating worker survives a supervisor recover pass run in a
    different timezone/locale — the poisoning bug reclaimed it at 0 s and let
    a second run start over it."""
    db = tmp_path / "runtime.sqlite3"
    proc, run_id = _spawn_worker(tmp_path, db, worker_env)
    try:
        time.sleep(0.5)                              # let it heartbeat once
        # The supervisor runs in a DIFFERENT environment. On the poisoned
        # build this alone changed the computed token; the fix makes the
        # probe environment-independent so the tokens still match.
        monkeypatch.setenv("TZ", supervisor_tz)
        monkeypatch.delenv("LC_ALL", raising=False)
        monkeypatch.delenv("LANG", raising=False)
        journal = RunJournal(db)

        recovered = journal.recover_abandoned(alive=pid_alive)  # real probe

        assert recovered == []
        assert journal.state(run_id) in {RunState.GENERATING, RunState.QUEUED}
        # The single-active-run invariant holds: nothing may start beside it.
        with pytest.raises(RuntimeError, match="already running"):
            journal.start("second run over a live worker")
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_process_identity_is_stable_across_timezones_and_locales(tmp_path,
                                                                 monkeypatch):
    """The same live pid yields the same token no matter the caller's env."""
    victim = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(5)"])
    try:
        tokens = set()
        for env in ({"TZ": "Asia/Shanghai"}, {"TZ": "UTC"},
                    {"LC_ALL": "fr_FR.UTF-8"}, {"LC_ALL": "C"},
                    {"LANG": "zh_CN.UTF-8"}):
            for key in ("TZ", "LC_ALL", "LANG"):
                monkeypatch.delenv(key, raising=False)
            for key, value in env.items():
                monkeypatch.setenv(key, value)
            token = process_identity(victim.pid)
            assert token and token.startswith(IDENTITY_TOKEN_PREFIX)
            tokens.add(token)
        assert len(tokens) == 1                       # env made no difference
    finally:
        victim.terminate()
        victim.wait(timeout=5)


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires fork")
def test_a_zombie_owner_is_reclaimed_not_held(tmp_path):
    """A reaped-later zombie answers os.kill and the identity probe, so without
    the explicit zombie check it would read as 'verified alive' and hold the
    run slot until its parent reaps it."""
    pid = os.fork()
    if pid == 0:                                      # child: exit at once
        os._exit(0)
    try:
        for _ in range(100):
            if zombie(pid):
                break
            time.sleep(0.05)
        assert zombie(pid), "child did not become a zombie"
        assert pid_alive(pid)                         # os.kill still succeeds

        journal = RunJournal(tmp_path / "runtime.sqlite3")
        run_id = journal.start("owned by a soon-zombie", owner_pid=pid)
        # Fresh lease: only zombie detection (not the lease gate) can reclaim.
        recovered = journal.recover_abandoned(current_pid=os.getpid(),
                                              alive=pid_alive)
        assert recovered == [run_id]
        assert journal.state(run_id) == RunState.INTERRUPTED
        assert "zombie" in journal.latest()["error"]
    finally:
        os.waitpid(pid, 0)                            # reap it


def event(state):
    from crossaudit.runtime import RunEvent
    return RunEvent(actor="loop", text="writing", state=state)


def test_a_single_transient_probe_failure_does_not_reclaim(cfg):
    """A comparable token whose first ``ps`` came back empty is confirmed with
    a second probe before any interruption is written."""
    journal = RunJournal(journal_path(cfg))
    run_id = journal.start("healthy; ps flaked once", owner_pid=1)
    journal.append(run_id, event(RunState.GENERATING))
    token = "v2:1:marker"
    with sqlite3.connect(journal.path) as db:
        db.execute("UPDATE runs SET owner_token=? WHERE run_id=?",
                   (token, run_id))

    probes = []

    def flaky(_pid):                                  # None, then the token
        probes.append(1)
        return None if len(probes) == 1 else token

    recovered = journal.recover_abandoned(
        current_pid=os.getpid(), alive=lambda _pid: True,
        is_zombie=lambda _pid: False, identity=flaky, sleep=lambda _s: None)
    assert recovered == []
    assert len(probes) == 2                           # confirmed, not trusted once
    assert journal.state(run_id) == RunState.GENERATING


def test_a_confirmed_unverifiable_owner_reclaims_after_the_lease(cfg):
    journal = RunJournal(journal_path(cfg))
    run_id = journal.start("truly unverifiable", owner_pid=1)
    journal.append(run_id, event(RunState.GENERATING))
    with sqlite3.connect(journal.path) as db:        # comparable token, dead lease
        db.execute("UPDATE runs SET owner_token='v2:1:marker', "
                   "lease_expires_at=1 WHERE run_id=?", (run_id,))

    probes = []

    def always_none(_pid):
        probes.append(1)
        return None

    recovered = journal.recover_abandoned(
        current_pid=os.getpid(), alive=lambda _pid: True,
        is_zombie=lambda _pid: False, identity=always_none, sleep=lambda _s: None)
    assert recovered == [run_id]
    assert len(probes) == 2                           # first + confirmation
    assert "could not be verified" in journal.latest()["error"]
    assert "recycled" not in journal.latest()["error"]


def test_a_pre_fix_token_is_grace_gated_not_treated_as_a_mismatch(cfg):
    """The migration contract: a v3 row from the poisoned build carries a
    token with no ``v2:`` prefix. It must be treated as unverifiable (lease
    grace), never compared against a fresh probe and declared a recycled
    pid — which would reclaim every migrated row on the first sweep."""
    journal = RunJournal(journal_path(cfg))
    run_id = journal.start("started by the older build", owner_pid=1)
    journal.append(run_id, event(RunState.GENERATING))
    poisoned = "1:Wed Aug 12 21:03:02 2026"          # no version prefix
    with sqlite3.connect(journal.path) as db:
        db.execute("UPDATE runs SET owner_token=? WHERE run_id=?",
                   (poisoned, run_id))

    fresh = lambda _pid: "v2:1:different"             # would 'mismatch' if compared

    # Fresh lease: not comparable, so unverifiable → left alone, never a
    # mismatch-driven immediate reclaim.
    assert journal.recover_abandoned(
        current_pid=os.getpid(), alive=lambda _pid: True,
        is_zombie=lambda _pid: False, identity=fresh) == []

    with sqlite3.connect(journal.path) as db:        # now age the lease out
        db.execute("UPDATE runs SET lease_expires_at=1 WHERE run_id=?",
                   (run_id,))
    recovered = journal.recover_abandoned(
        current_pid=os.getpid(), alive=lambda _pid: True,
        is_zombie=lambda _pid: False, identity=fresh, sleep=lambda _s: None)
    assert recovered == [run_id]
    assert "could not be verified" in journal.latest()["error"]
    assert "recycled" not in journal.latest()["error"]


def test_heartbeat_upgrades_a_pre_fix_token_to_the_current_format(cfg):
    """A live owner refreshes its own migrated token to the comparable format
    at the next heartbeat, so its grace window closes into a verified one."""
    journal = RunJournal(journal_path(cfg))
    run_id = journal.start("self-owned, migrated token")   # owner == this proc
    with sqlite3.connect(journal.path) as db:        # simulate a pre-fix token
        db.execute("UPDATE runs SET owner_token='legacy-unprefixed' "
                   "WHERE run_id=?", (run_id,))

    assert journal.heartbeat(run_id) is True
    with sqlite3.connect(journal.path) as db:
        token = db.execute("SELECT owner_token FROM runs WHERE run_id=?",
                           (run_id,)).fetchone()[0]
    assert token.startswith(IDENTITY_TOKEN_PREFIX)
    assert token == process_identity(os.getpid())
