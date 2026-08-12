"""Canonical operational run state, recovery and concurrency."""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from crossaudit.console.progress import Tracker
from crossaudit.runtime import (
    PreparedRun,
    ProvisioningJournal,
    RunCommandService,
    RunEvent,
    RunJournal,
    RunLaunch,
    RunState,
    workspace_capacity,
)


def event(actor: str, text: str, state: RunState, *, detail: str = "",
          kind: str = "activity", round_no: int = 0,
          round_limit: int = 0) -> RunEvent:
    return RunEvent(actor=actor, text=text, state=state, detail=detail,
                    kind=kind, round_no=round_no, round_limit=round_limit)


def test_bound_tracker_survives_a_new_projection(tmp_path):
    path = tmp_path / "runtime.sqlite3"
    journal = RunJournal(path)
    run_id = journal.start("prepare the release", chat_id="history")
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))
    journal.append(run_id, event(
        "auditor", "reviewing the commit", RunState.AUDITING,
        kind="audit_started"))
    first = Tracker()
    first.bind(path)

    second = Tracker()
    second.bind(path)
    snapshot = second.snapshot()
    assert snapshot["task"] == "prepare the release"
    assert snapshot["chat_id"] == "history"
    assert snapshot["state"] == "AUDITING"
    assert [row["actor"] for row in snapshot["steps"]] == ["generator", "auditor"]
    assert second.running is True


def test_run_command_service_is_the_single_sync_lifecycle(cfg):
    changes = []
    service = RunCommandService(cfg, on_change=lambda: changes.append(True))

    def worker(prepared, emit):
        assert prepared.task == "prepare evidence"
        emit(event("generator", "writing", RunState.GENERATING))
        emit(event("auditor", "reviewing", RunState.AUDITING))
        return 0

    code = service.start(
        lambda: PreparedRun(task="prepare evidence"), worker,
        background=False)

    row = service.journal.latest()
    assert code == 0 and row["state"] == "PASSED"
    assert [step["actor"] for step in row["steps"]] == [
        "generator", "auditor", "done"]
    assert len(changes) == 4
    assert workspace_capacity(cfg)["active"] == 0


def test_run_command_service_records_failure_and_releases_lease(cfg):
    service = RunCommandService(cfg)

    def crash(_prepared, _emit):
        raise RuntimeError("engine stopped")

    with pytest.raises(RuntimeError, match="engine stopped"):
        service.start(lambda: PreparedRun(task="fail safely"), crash,
                      background=False)

    row = service.journal.latest()
    assert row["state"] == "FAILED"
    assert "engine stopped" in row["error"]
    assert workspace_capacity(cfg)["active"] == 0


def test_durable_cancel_wins_over_a_late_background_success(cfg):
    entered = threading.Event()
    release = threading.Event()
    service = RunCommandService(cfg)

    def worker(_prepared, emit):
        emit(event("generator", "writing", RunState.GENERATING))
        entered.set()
        assert release.wait(2)
        emit(event("auditor", "late result", RunState.AUDITING))
        return 0

    launch = service.start(
        lambda: PreparedRun(task="cancel me"), worker, background=True)
    assert isinstance(launch, RunLaunch) and entered.wait(2)

    requested = service.request_cancel(launch.run_id)
    assert requested["requested"] is True
    assert service.request_cancel(launch.run_id)["requested"] is False
    release.set()

    deadline = time.monotonic() + 2
    while not service.journal.latest()["finished"] and time.monotonic() < deadline:
        time.sleep(0.01)
    row = service.journal.latest()
    assert row["state"] == "CANCELLED" and row["outcome"] == "cancelled"
    assert [step["kind"] for step in row["steps"]][-2:] == [
        "cancel_requested", "run_finished"]
    assert workspace_capacity(cfg)["active"] == 0


def test_tracker_has_no_second_mutable_run_state_machine():
    tracker = Tracker()
    for removed in ("start", "step", "finish", "dismiss_interruption"):
        assert not hasattr(tracker, removed)


def test_binding_a_read_projection_cannot_recover_or_mutate_a_run(tmp_path):
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    run_id = journal.start("read without side effects", owner_pid=999999)

    tracker = Tracker()
    tracker.bind(journal.path)

    assert tracker.snapshot()["run_id"] == run_id
    assert journal.latest()["state"] == "QUEUED"


def test_dead_worker_becomes_an_explicit_interruption(tmp_path):
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    run_id = journal.start("recover me", owner_pid=999999)
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))

    recovered = journal.recover_abandoned(current_pid=os.getpid(),
                                           alive=lambda _pid: False)
    assert recovered == [run_id]
    row = journal.interruption()
    assert row["run_id"] == run_id
    assert row["state"] == "INTERRUPTED"
    assert row["finished"] is True
    assert row["steps"][-1]["kind"] == "run_interrupted"
    # Recovery is idempotent; reopening the app cannot add another interruption.
    assert journal.recover_abandoned(current_pid=os.getpid(),
                                     alive=lambda _pid: False) == []


def test_dead_worker_after_a_durable_cancel_finishes_cancelled(tmp_path):
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    run_id = journal.start("cancel survives the crash", owner_pid=999999)
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))
    journal.request_cancel(run_id)

    assert journal.recover_abandoned(
        current_pid=os.getpid(), alive=lambda _pid: False) == [run_id]
    row = journal.latest()
    assert row["state"] == "CANCELLED" and row["outcome"] == "cancelled"
    assert row["error"] == "" and row["steps"][-1]["kind"] == "run_cancelled"
    assert journal.interruption() is None


def test_a_live_foreign_worker_is_not_declared_interrupted(tmp_path):
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    journal.start("still running", owner_pid=4242)
    assert journal.recover_abandoned(current_pid=os.getpid(),
                                     alive=lambda pid: pid == 4242) == []
    assert journal.latest()["state"] == "QUEUED"


def test_dismissing_an_interruption_is_a_recorded_transition(tmp_path):
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    journal.start("recover me", owner_pid=999999)
    journal.recover_abandoned(current_pid=os.getpid(), alive=lambda _pid: False)
    assert journal.dismiss_interruption() is True
    row = journal.latest()
    assert row["state"] == "CANCELLED"
    assert row["steps"][-1]["actor"] == "user"
    assert journal.interruption() is None
    assert journal.dismiss_interruption() is False


def test_invalid_lifecycle_transition_is_refused(tmp_path):
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    run_id = journal.start("x")
    journal.append(run_id, event("generator", "writing", RunState.GENERATING))
    journal.finish(run_id, "escalated")
    # Waiting for a person cannot silently resume itself.
    with pytest.raises(RuntimeError, match="invalid run transition"):
        journal.append(run_id, event("generator", "writing", RunState.GENERATING))


def test_parallel_progress_events_have_one_total_order(tmp_path):
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    run_id = journal.start("parallel updates")
    journal.append(run_id, event(
        "generator", "writing", RunState.GENERATING,
        kind="round_started", round_no=1, round_limit=3))

    def hammer(worker: int) -> None:
        for index in range(25):
            journal.append(run_id, event(
                "generator", f"{worker}-{index}", RunState.GENERATING))

    workers = [threading.Thread(target=hammer, args=(index,)) for index in range(4)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    steps = journal.latest()["steps"]
    assert len(steps) == 101
    ids = [row["event_id"] for row in steps]
    assert ids == sorted(ids) and len(ids) == len(set(ids))
    assert steps[0]["kind"] == "round_started"
    assert steps[0]["round_no"] == 1 and steps[0]["round_limit"] == 3


def test_journal_rejects_untyped_narration_at_the_state_boundary(tmp_path):
    journal = RunJournal(tmp_path / "runtime.sqlite3")
    run_id = journal.start("typed only")

    with pytest.raises(TypeError, match="RunEvent"):
        journal.append(run_id, {"actor": "generator", "text": "writing"})


def test_build_five_runtime_database_migrates_without_losing_events(tmp_path):
    path = tmp_path / "runtime.sqlite3"
    with sqlite3.connect(path) as db:
        db.executescript(
            """
            CREATE TABLE runs (
                run_id TEXT PRIMARY KEY, task TEXT NOT NULL, chat_id TEXT NOT NULL,
                continuation_cycle TEXT NOT NULL, state TEXT NOT NULL,
                outcome TEXT NOT NULL, error TEXT NOT NULL, owner_pid INTEGER NOT NULL,
                started REAL NOT NULL, updated REAL NOT NULL, finished REAL
            );
            CREATE TABLE run_events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL REFERENCES runs(run_id), t REAL NOT NULL,
                kind TEXT NOT NULL, actor TEXT NOT NULL, text TEXT NOT NULL,
                detail TEXT NOT NULL, state TEXT NOT NULL
            );
            INSERT INTO runs VALUES(
                'old-run','legacy task','','','PASSED','passed','',1,1,2,2
            );
            INSERT INTO run_events(run_id,t,kind,actor,text,detail,state)
                VALUES('old-run',2,'run_finished','done','passed','','PASSED');
            """
        )

    row = RunJournal(path).latest()

    assert row["task"] == "legacy task" and row["outcome"] == "passed"
    assert row["steps"][0]["round_no"] == 0
    assert row["steps"][0]["round_limit"] == 0


def test_run_start_is_serialized_across_connections(tmp_path):
    path = tmp_path / "runtime.sqlite3"
    one, two = RunJournal(path), RunJournal(path)
    barrier = threading.Barrier(2)
    outcomes = []

    def start(journal: RunJournal, name: str) -> None:
        barrier.wait()
        try:
            outcomes.append((name, journal.start(name)))
        except RuntimeError:
            outcomes.append((name, "refused"))

    workers = [threading.Thread(target=start, args=(one, "one")),
               threading.Thread(target=start, args=(two, "two"))]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    assert sum(value != "refused" for _name, value in outcomes) == 1


def test_database_uses_wal_and_private_permissions(tmp_path):
    path = tmp_path / "runtime.sqlite3"
    RunJournal(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600


def test_abrupt_process_exit_leaves_a_recoverable_run_not_a_locked_database(tmp_path):
    path = tmp_path / "runtime.sqlite3"
    source = Path(__file__).resolve().parents[1] / "src"
    code = (
        "import os\n"
        "from pathlib import Path\n"
        "from crossaudit.runtime import RunEvent, RunJournal, RunState\n"
        f"journal=RunJournal(Path({str(path)!r}))\n"
        "run_id=journal.start('crash boundary')\n"
        "journal.append(run_id,RunEvent(actor='generator',text='writing',"
        "state=RunState.GENERATING))\n"
        "os._exit(23)\n"
    )
    env = dict(os.environ, PYTHONPATH=str(source))
    worker = subprocess.Popen([sys.executable, "-c", code], env=env)
    worker.wait(timeout=10)
    assert worker.returncode == 23

    journal = RunJournal(path)
    assert journal.latest()["owner_pid"] == worker.pid
    recovered = journal.recover_abandoned(
        current_pid=os.getpid(), alive=lambda pid: pid != worker.pid)
    assert recovered == [journal.latest()["run_id"]]
    assert journal.latest()["state"] == "INTERRUPTED"
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_abrupt_project_setup_exit_preserves_the_exact_retry_specification(tmp_path):
    path = tmp_path / "runtime.sqlite3"
    source = Path(__file__).resolve().parents[1] / "src"
    code = (
        "import os\n"
        "from pathlib import Path\n"
        "from crossaudit.runtime import ProvisioningJournal\n"
        f"journal=ProvisioningJournal(Path({str(path)!r}))\n"
        "journal.create(job_id='job-crash',kind='create',project='science',"
        "current_config='/safe/crossaudit.yml',workspace='/safe',"
        "specification={'kind':'create','payload':{'name':'science'}},"
        "root='/safe/science',context={'draft':{'name':'science'}})\n"
        "journal.step('job-crash','github','Creating repositories')\n"
        "os._exit(29)\n"
    )
    env = dict(os.environ, PYTHONPATH=str(source))
    worker = subprocess.Popen([sys.executable, "-c", code], env=env)
    worker.wait(timeout=10)
    assert worker.returncode == 29

    journal = ProvisioningJournal(path)
    assert journal.recover_abandoned(
        current_pid=os.getpid(), alive=lambda pid: pid != worker.pid) == ["job-crash"]
    row = journal.get("job-crash")
    assert row["status"] == "failed" and row["issue"]["retryable"] is True
    assert row["specification"]["payload"] == {"name": "science"}
    assert row["draft"] == {"name": "science"}
