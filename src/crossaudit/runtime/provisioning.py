"""Durable, resumable project-provisioning jobs.

Creating a project spans local files, Git commits, optional model calls and two
GitHub repositories.  The operation is therefore a workflow, not a transient
thread notification.  This journal stores the safe UI draft and every visible
step in the workspace runtime database so restart, retry and dismissal never
depend on a closure left in memory.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path

from .runs import RunJournal


class ProvisioningJournal:
    def __init__(self, path: Path) -> None:
        # Initialize the shared workspace runtime database and its WAL policy.
        RunJournal(path)
        self.path = Path(path)
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS project_jobs (
                    job_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    project TEXT NOT NULL,
                    status TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    root TEXT,
                    current_config TEXT NOT NULL,
                    workspace TEXT NOT NULL,
                    specification TEXT NOT NULL,
                    context TEXT NOT NULL,
                    issue TEXT,
                    result TEXT,
                    owner_pid INTEGER NOT NULL,
                    started REAL NOT NULL,
                    updated REAL NOT NULL,
                    finished REAL,
                    dismissed INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS project_jobs_started
                    ON project_jobs(started DESC);
                CREATE TABLE IF NOT EXISTS project_job_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL REFERENCES project_jobs(job_id),
                    t REAL NOT NULL,
                    stage TEXT NOT NULL,
                    detail TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS project_job_events_job
                    ON project_job_events(job_id, sequence);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")
        return db

    def create(self, *, job_id: str, kind: str, project: str,
               current_config: str, workspace: str, specification: dict,
               root: str | None, context: dict, owner_pid: int | None = None) -> None:
        now = time.time()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            duplicate = db.execute(
                "SELECT job_id FROM project_jobs WHERE dismissed=0 AND status='running' "
                "AND lower(project)=lower(?) LIMIT 1", (project,),
            ).fetchone()
            if duplicate is not None:
                db.rollback()
                raise RuntimeError(f"setup is already running for {project}")
            db.execute(
                "INSERT INTO project_jobs(job_id,kind,project,status,stage,detail,root,"
                "current_config,workspace,specification,context,issue,result,owner_pid,"
                "started,updated,finished,dismissed) "
                "VALUES(?,?,?,'running','validate','Validating project settings',"
                "?,?,?,?,?,NULL,NULL,?,?,?,NULL,0)",
                (job_id, kind[:30], project[:80], root, current_config, workspace,
                 json.dumps(specification, sort_keys=True),
                 json.dumps(context, sort_keys=True), owner_pid or os.getpid(), now, now),
            )
            db.commit()

    def step(self, job_id: str, stage: str, detail: str) -> None:
        now = time.time()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT status FROM project_jobs WHERE job_id=?", (job_id,),
            ).fetchone()
            if row is None or row["status"] != "running":
                db.rollback()
                return
            db.execute(
                "INSERT INTO project_job_events(job_id,t,stage,detail) VALUES(?,?,?,?)",
                (job_id, now, stage[:60], detail[:500]),
            )
            db.execute(
                "UPDATE project_jobs SET stage=?,detail=?,updated=? WHERE job_id=?",
                (stage[:60], detail[:500], now, job_id),
            )
            db.commit()

    def complete(self, job_id: str, result: dict) -> None:
        self._finish(job_id, status="complete", stage="ready", detail="Project ready",
                     result=result)

    def fail(self, job_id: str, detail: str, issue: dict,
             *, recoverable: bool) -> None:
        context = self.get(job_id).get("context", {})
        context["recoverable"] = recoverable
        self._finish(job_id, status="failed", stage="failed", detail=detail,
                     issue=issue, context=context)

    def _finish(self, job_id: str, *, status: str, stage: str, detail: str,
                issue: dict | None = None, result: dict | None = None,
                context: dict | None = None) -> None:
        now = time.time()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            values = {
                "issue": json.dumps(issue, sort_keys=True) if issue else None,
                "result": json.dumps(result, sort_keys=True) if result else None,
                "context": json.dumps(context, sort_keys=True) if context else None,
            }
            db.execute(
                "UPDATE project_jobs SET status=?,stage=?,detail=?,issue=?,result=?,"
                "context=COALESCE(?,context),updated=?,finished=? WHERE job_id=?",
                (status, stage, detail[:500], values["issue"], values["result"],
                 values["context"], now, now, job_id),
            )
            db.execute(
                "INSERT INTO project_job_events(job_id,t,stage,detail) VALUES(?,?,?,?)",
                (job_id, now, stage[:60], detail[:500]),
            )
            db.commit()

    def recover_abandoned(self, *, current_pid: int,
                          alive: Callable[[int], bool]) -> list[str]:
        recovered = []
        now = time.time()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                "SELECT job_id,owner_pid FROM project_jobs WHERE status='running' "
                "AND dismissed=0",
            ).fetchall()
            for row in rows:
                owner = int(row["owner_pid"])
                if owner == current_pid or alive(owner):
                    continue
                job_id = str(row["job_id"])
                issue = {
                    "code": "setup_interrupted",
                    "title": "Project setup was interrupted",
                    "action": "retry",
                    "url": None,
                    "retryable": True,
                }
                db.execute(
                    "UPDATE project_jobs SET status='failed',stage='interrupted',"
                    "detail=?,issue=?,updated=?,finished=? WHERE job_id=?",
                    (("The app ended before project setup completed. No user files were "
                      "discarded; retry continues from the recorded setup state."),
                     json.dumps(issue, sort_keys=True), now, now, job_id),
                )
                db.execute(
                    "INSERT INTO project_job_events(job_id,t,stage,detail) "
                    "VALUES(?,?,'interrupted','App process ended')",
                    (job_id, now),
                )
                recovered.append(job_id)
            db.commit()
        return recovered

    @staticmethod
    def _decode(value: str | None, default):
        if not value:
            return default
        try:
            decoded = json.loads(value)
            return decoded
        except (TypeError, ValueError):
            return default

    def get(self, job_id: str) -> dict:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM project_jobs WHERE job_id=?", (job_id,),
            ).fetchone()
            if row is None:
                return {}
            events = db.execute(
                "SELECT t,stage,detail FROM project_job_events WHERE job_id=? "
                "ORDER BY sequence", (job_id,),
            ).fetchall()
        context = self._decode(row["context"], {})
        result = {
            "id": row["job_id"], "kind": row["kind"],
            "project": row["project"], "status": row["status"],
            "stage": row["stage"], "detail": row["detail"],
            "root": row["root"], "current_config": row["current_config"],
            "workspace": row["workspace"],
            "specification": self._decode(row["specification"], {}),
            "context": context,
            "issue": self._decode(row["issue"], None),
            "result": self._decode(row["result"], None),
            "started": float(row["started"]), "updated": float(row["updated"]),
            "finished": float(row["finished"]) if row["finished"] else None,
            "owner_pid": int(row["owner_pid"]),
            "steps": [dict(event) for event in events],
            **context,
        }
        return result

    def snapshot(self) -> list[dict]:
        with self._connect() as db:
            ids = [row[0] for row in db.execute(
                "SELECT job_id FROM project_jobs WHERE dismissed=0 "
                "ORDER BY started DESC LIMIT 40",
            ).fetchall()]
        return [row for job_id in reversed(ids) if (row := self.get(job_id))]

    def dismiss(self, job_id: str) -> bool:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT status FROM project_jobs WHERE job_id=?", (job_id,),
            ).fetchone()
            if row is None:
                db.rollback()
                return False
            if row["status"] == "running":
                db.rollback()
                raise RuntimeError("a running project setup task cannot be dismissed")
            db.execute("UPDATE project_jobs SET dismissed=1 WHERE job_id=?", (job_id,))
            db.commit()
            return True
