"""Stability hardening Slice C: a read must not write, and an idle stream
must not burn a core.

Two HIGH findings from the long-conversation / complex-project scenario, each
closed with a regression test that uses the real journal, real process
identities and the real snapshot derivation — not a synthetic seam:

* C2 — rendering the multi-project overview calls ``daemon.interrupted`` for
  every sibling project. It used to construct a ``RunCommandService``, whose
  ``__init__`` runs ``recover_abandoned`` under the CONTROLLER's pid, so a mere
  list render could write INTERRUPTED over a healthy sibling whose lease had
  expired but whose worker was alive (North Star §6/§31). ``interrupted`` is now
  a PURE READ: it surfaces a run the owning daemon already stopped, or an
  in-flight run whose owner is provably dead, using only ``kill(pid, 0)`` — it
  never reclaims, and a verified-alive sibling is neither written nor surfaced.

* C1 — the SSE ``_stream`` re-derived the whole snapshot (git log over the
  entire repo, report globs, a YAML re-parse) on every 0.1 s poll tick, pegging
  a core on a large or old project even at idle (§32). The snapshot is now
  memoized behind a cheap stat/probe fingerprint: an unchanged project reuses
  the cache, while any real change — in-process OR cross-process — still
  recomputes promptly.
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

from crossaudit.config import load
from crossaudit.console import daemon, projects
from crossaudit.console import server as server_mod
from crossaudit.console import streams
from crossaudit.runtime import (
    RunEvent,
    RunJournal,
    RunState,
    journal_path,
)

#: A pid that can never be alive, so a dead owner is deterministic without
#: spawning a process where the identity is injected anyway.
FOREIGN_PID = 999999

CONFIG = (
    "version: 1\nscience_repo: t/p\nconstitution: AUDIT_RULES.md\n"
    "auditor: {vendor: openai, provider: openai_compat, model: m,"
    " key_env: CROSSAUDIT_AUDITOR_KEY}\ngenerator: {vendor: anthropic}\n"
    "scope: {dirs: [work]}\nledger: {dir: cycles}\nstate: {dir: .crossaudit}\n"
    "checks: [parseable]\n")


def _make_project(base: Path, name: str):
    root = base / name
    root.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@e"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    (root / "AUDIT_RULES.md").write_text("### CA-X-001\n**BLOCKER.** be exact\n\nx\n")
    (root / "crossaudit.yml").write_text(CONFIG)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init (round 1)"], cwd=root, check=True)
    return load(root / "crossaudit.yml")


@pytest.fixture()
def project(tmp_path: Path):
    return _make_project(tmp_path, "proj")


@pytest.fixture()
def live_worker():
    """A genuinely-alive process to own a run, torn down after the test."""
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        yield proc
    finally:
        proc.terminate()
        proc.wait()


def _expire_lease(journal: RunJournal, run_id: str) -> None:
    with sqlite3.connect(journal.path) as db:
        db.execute("UPDATE runs SET lease_expires_at=? WHERE run_id=?",
                   (time.time() - 999, run_id))


# =========================================================================== C2
def test_render_path_never_reclaims_a_verified_alive_sibling(tmp_path, live_worker):
    """The isolation guarantee (§6/§31): rendering the overview while a sibling
    project has a healthy ACTIVE run whose lease expired but whose worker is
    alive must NOT interrupt it — no INTERRUPTED written, still ACTIVE."""
    current = _make_project(tmp_path, "controller")
    sibling = _make_project(tmp_path, "sibling")

    journal = RunJournal(journal_path(sibling))
    run_id = journal.start("a 200s reasoning turn", owner_pid=live_worker.pid)
    journal.append(run_id, RunEvent(
        actor="generator", text="writing", detail="mid provider call",
        state=RunState.GENERATING))
    _expire_lease(journal, run_id)     # the exact precondition the old bug reclaimed

    # The render path — both the row builder and the function it calls.
    row = projects._project_row(sibling.root, current)
    assert row is not None
    assert row["status"] != "interrupted"
    assert row["interrupted"] is None
    assert daemon.interrupted(sibling) is None

    # The sibling's run is untouched: a live owner is never written over.
    after = RunJournal(journal_path(sibling)).latest()
    assert after["state"] == RunState.GENERATING.value
    assert after["run_id"] == run_id
    with sqlite3.connect(journal_path(sibling)) as db:
        interrupted_rows = db.execute(
            "SELECT COUNT(*) FROM runs WHERE state=?",
            (RunState.INTERRUPTED.value,)).fetchone()[0]
    assert interrupted_rows == 0


def test_interrupted_is_a_pure_read_and_never_calls_recover_abandoned(
        project, live_worker, monkeypatch):
    """The contract, encoded directly: the render path must never invoke the
    write-capable recovery. recover_abandoned stays a command / own-daemon
    responsibility."""
    journal = RunJournal(journal_path(project))
    run_id = journal.start("healthy work", owner_pid=live_worker.pid)
    journal.append(run_id, RunEvent(actor="generator", text="writing",
                                    state=RunState.GENERATING))
    _expire_lease(journal, run_id)

    calls: list = []
    real = RunJournal.recover_abandoned

    def spy(self, **kwargs):
        calls.append(True)
        return real(self, **kwargs)

    monkeypatch.setattr(RunJournal, "recover_abandoned", spy)

    daemon.interrupted(project)
    projects._project_row(project.root, project)
    assert calls == []          # a render reclaimed nothing


def test_a_dead_owner_run_is_surfaced_read_only_without_being_reclaimed(project):
    """A build whose owner process is provably gone still reads as interrupted
    (the existing behaviour), but as a PURE READ: the journal row is NOT written
    to INTERRUPTED by the mere act of displaying it."""
    journal = RunJournal(journal_path(project))
    run_id = journal.start("cut off mid-round", owner_pid=FOREIGN_PID)
    journal.append(run_id, RunEvent(
        actor="generator", text="writing", detail="drafting report",
        state=RunState.GENERATING))

    found = daemon.interrupted(project)
    assert found and found["task"] == "cut off mid-round"
    assert found["phase"] == "generator" and found["detail"] == "drafting report"
    assert found["failed"] is False

    # Surfacing it did not persist the stop: the row is still ACTIVE, the
    # durable INTERRUPTED transition stays the owning daemon's watchdog job.
    assert RunJournal(journal_path(project)).latest()["state"] == \
        RunState.GENERATING.value


def test_a_genuinely_interrupted_sibling_still_displays_as_interrupted(project):
    """The pure read must still surface real state: a run the owning daemon
    already moved to INTERRUPTED shows as interrupted."""
    journal = RunJournal(journal_path(project))
    run_id = journal.start("owner already died", owner_pid=FOREIGN_PID)
    journal.append(run_id, RunEvent(actor="generator", text="writing",
                                    state=RunState.GENERATING))
    # The owning daemon's own watchdog reclaims its dead worker -> INTERRUPTED.
    recovered = journal.recover_abandoned(alive=lambda _pid: False)
    assert recovered == [run_id]
    assert journal.state(run_id) == RunState.INTERRUPTED

    found = daemon.interrupted(project)
    assert found and found["task"] == "owner already died"
    assert found["run_id"] == run_id


# =========================================================================== C1
def _spy_derivation(monkeypatch):
    """Count full snapshot derivations and the git-log call inside them."""
    counts = {"snapshot": 0, "git_log": 0}
    real_snapshot = server_mod.snapshot
    real_commits = streams._commits

    def counted_snapshot(cfg):
        counts["snapshot"] += 1
        return real_snapshot(cfg)

    def counted_commits(root, limit=200):
        counts["git_log"] += 1
        return real_commits(root, limit)

    monkeypatch.setattr(server_mod, "snapshot", counted_snapshot)
    monkeypatch.setattr(streams, "_commits", counted_commits)
    return counts


def _warm(cfg, cache):
    """Prime the cache past first-run file creation, until it stabilises."""
    prev = None
    for _ in range(8):
        server_mod._memoized_snapshot(cfg, cache)
        sig = server_mod._snapshot_fingerprint(cfg)
        if sig == prev:
            break
        prev = sig


def test_idle_stream_tick_reuses_the_memoized_snapshot(project, monkeypatch):
    """An idle tick with nothing changed reuses the cache: the expensive
    derivation — git log / report glob — is NOT re-invoked (§32)."""
    counts = _spy_derivation(monkeypatch)
    cache: dict = {}
    _warm(project, cache)

    base_snapshot, base_git = counts["snapshot"], counts["git_log"]
    first = server_mod._memoized_snapshot(project, cache)
    second = server_mod._memoized_snapshot(project, cache)

    assert counts["snapshot"] == base_snapshot   # no fresh derivation
    assert counts["git_log"] == base_git         # git log not re-run
    assert second is first                        # same cached object reused


def test_an_in_process_change_recomputes_promptly(project, monkeypatch):
    """A real in-process change (STREAM_CHANGES bumped by any mutation) moves
    the fingerprint and forces a fresh snapshot — live updates must not
    regress."""
    counts = _spy_derivation(monkeypatch)
    cache: dict = {}
    _warm(project, cache)
    server_mod._memoized_snapshot(project, cache)      # settle into reuse
    base = counts["snapshot"]

    server_mod.STREAM_CHANGES.notify()
    server_mod._memoized_snapshot(project, cache)
    assert counts["snapshot"] == base + 1              # recomputed


def test_a_cross_process_change_is_caught_without_an_in_process_signal(
        project, monkeypatch):
    """The 0.1 s poll exists for changes another local process makes without
    waking this one. Keying on STREAM_CHANGES alone would miss them, so the
    fingerprint must move on a cross-process journal write and a cross-process
    git commit — with STREAM_CHANGES never touched."""
    counts = _spy_derivation(monkeypatch)
    cache: dict = {}
    _warm(project, cache)
    server_mod._memoized_snapshot(project, cache)
    base = counts["snapshot"]

    # A run started by another process writes only the journal.
    RunJournal(journal_path(project)).start("external build", owner_pid=FOREIGN_PID)
    server_mod._memoized_snapshot(project, cache)
    assert counts["snapshot"] == base + 1

    # And once more idle -> reuse (the change settled into the cache).
    server_mod._memoized_snapshot(project, cache)
    assert counts["snapshot"] == base + 1

    # A round committed by another process moves git HEAD only.
    (project.root / "work.txt").write_text("output")
    subprocess.run(["git", "add", "-A"], cwd=project.root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "deliver (round 2)"],
                   cwd=project.root, check=True)
    server_mod._memoized_snapshot(project, cache)
    assert counts["snapshot"] == base + 2


def test_the_memoized_snapshot_equals_a_direct_snapshot(project):
    """The cache is an optimisation, not a behaviour change: every ledger-derived
    field the memoization touches (the git/glob/YAML derivation) is identical to
    a freshly computed snapshot. Only wall-clock stamps like ``compute.updated``
    legitimately differ between two derivations, and those churned a frame every
    0.1 s in the un-memoized loop this fix replaces."""
    cache: dict = {}
    _warm(project, cache)
    reused = server_mod._memoized_snapshot(project, cache)
    fresh = server_mod.snapshot(load(project.path))
    for field in ("generator_stream", "auditor_stream", "cycles", "interrupted",
                  "metrics", "pipeline", "findings", "escalations", "disputes",
                  "runtime_config", "auditor", "generator", "routing"):
        assert reused[field] == fresh[field], field


def test_chat_map_is_bounded_like_the_commit_stream(project):
    """The formerly-uncapped whole-repo git log is now bounded, so it stops
    scaling the wrong way on a large/old project while keeping the recent
    associations the streams and cycles reference."""
    for i in range(3):
        (project.root / f"f{i}.txt").write_text(str(i))
        subprocess.run(["git", "add", "-A"], cwd=project.root, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", f"work (round {i + 1})",
             "-m", "CrossAudit-Chat: chat-abc"], cwd=project.root, check=True)
    # Recent history is fully associated within the bound.
    full = streams._chat_map(project.root)
    assert "chat-abc" in full.values()
    # The bound is honoured: a tiny cap sees only the most recent commits.
    assert len(streams._chat_map(project.root, limit=1)) == 1
