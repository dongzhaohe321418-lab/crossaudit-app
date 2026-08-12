"""Controller state machine with an explicit, atomically-mutated store.

Two properties this module exists to guarantee, both of which the pre-package
implementation only approximated:

**The store's location is injected, never inferred.** The old module resolved
its state as `Path(__file__).parent / "state.json"`, which under a wheel would
put a deployment's mutable ledger inside site-packages, and under a CI job
would put it inside a throwaway checkout — where "consumed" survives nothing.
`StateStore` takes a path and keeps it.

**Every mutation is a read-modify-write inside an exclusive lock.** Admission
is a single-use claim; two concurrent verifiers must not both see an unconsumed
receipt. The lock is an `O_EXCL` file with the holder's pid and a stale-break
timeout, and the state file is replaced by atomic rename after fsync, so a
crash mid-write leaves the previous state intact rather than a truncated file.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ..errors import ConfigDenial, IntegrityDenial

STATE_FILENAME = "state.json"
LOCK_TIMEOUT_S = 30.0
LOCK_STALE_S = 120.0

OPEN, BLOCKED, PASSED, ESCALATED, CONSUMED = "OPEN", "BLOCKED", "PASSED", "ESCALATED", "CONSUMED"
TERMINAL = frozenset({CONSUMED})


def cycle_id_for(repo: str, root_sha: str) -> str:
    return hashlib.sha256(f"{repo}\n{root_sha}".encode()).hexdigest()[:16]


class StateStore:
    """Cycle state on disk. One instance per state file; safe across processes."""

    def __init__(self, path: str | os.PathLike) -> None:
        self.path = Path(path).resolve()
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    # ---------------------------------------------------------------- storage
    def _read(self) -> dict:
        if not self.path.exists():
            return {"schema": 1, "cycles": {}, "history": []}
        text: str | None = None
        # ``os.replace`` is atomic, but Windows virus scanners and indexers can
        # briefly hold the destination between rename and open. Reads are much
        # more frequent than writes in the live UI; retry that transient sharing
        # violation without hiding a persistent permissions error.
        for attempt in range(5):
            try:
                text = self.path.read_text(encoding="utf-8")
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.01 * (attempt + 1))
        assert text is not None
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise IntegrityDenial(f"state file is corrupt: {exc}", path=str(self.path)) from exc
        if not isinstance(data, dict) or "cycles" not in data:
            raise IntegrityDenial("state file has no cycles map", path=str(self.path))
        return data

    def _write(self, state: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + f".tmp{os.getpid()}")
        with open(tmp, "w") as fh:
            json.dump(state, fh, indent=2, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.path)          # atomic within a filesystem
        if os.name != "nt":
            dir_fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)             # the rename itself must survive a crash
            finally:
                os.close(dir_fd)

    @contextmanager
    def _locked(self) -> Iterator[dict]:
        """Exclusive read-modify-write. Yields state; writes it back on clean exit."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + LOCK_TIMEOUT_S
        while True:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, f"{os.getpid()} {time.time():.0f}".encode())
                os.close(fd)
                break
            except FileExistsError:
                age = time.time() - self.lock_path.stat().st_mtime if self.lock_path.exists() else 0
                if age > LOCK_STALE_S:
                    self.lock_path.unlink(missing_ok=True)   # holder died; break it
                    continue
                if time.monotonic() > deadline:
                    raise ConfigDenial(
                        "could not acquire the controller lock; another verifier is "
                        "mid-transaction", lock=str(self.lock_path))
                time.sleep(0.05)
        try:
            state = self._read()
            yield state
            self._write(state)
        finally:
            self.lock_path.unlink(missing_ok=True)

    @staticmethod
    def _log(state: dict, event: str, **kw: object) -> None:
        state.setdefault("history", []).append({"t": int(time.time()), "event": event, **kw})

    # ------------------------------------------------------------------ reads
    def snapshot(self) -> dict:
        return self._read()

    def cycle(self, cycle_id: str) -> dict | None:
        c = self._read()["cycles"].get(cycle_id)
        return dict(c, cycle_id=cycle_id) if c else None

    # -------------------------------------------------------------- mutations
    def open_or_advance(self, repo: str, sha: str, parent_sha: str | None) -> dict:
        """New root commit opens a cycle; a child of an active sha advances it.

        Identity follows the commit graph, never changed-path sets, so a nonce
        file cannot reset a round.
        """
        with self._locked() as state:
            cycles = state["cycles"]
            for cid, c in cycles.items():
                if c["active_sha"] == sha and c["status"] == OPEN and c.get("awaiting_verdict"):
                    # This round was opened and never reached a verdict: the audit
                    # crashed, the provider timed out, the machine died. Re-entering
                    # resumes it. Incrementing here would let transient failures
                    # spend the revision budget and escalate a healthy increment.
                    self._log(state, "resume_open_round", cycle=cid, sha=sha,
                              round=c["round"])
                    return dict(c, cycle_id=cid)
                if c["active_sha"] == sha and c["status"] in (OPEN, BLOCKED):
                    c["round"] += 1
                    c["status"] = OPEN
                    c["awaiting_verdict"] = True
                    self._log(state, "readvance_same_sha", cycle=cid, sha=sha, round=c["round"])
                    return dict(c, cycle_id=cid)
                if c["active_sha"] == sha and c["status"] == ESCALATED:
                    self._log(state, "blocked_by_escalation", cycle=cid, sha=sha)
                    return dict(c, cycle_id=cid, blocked_by_escalation=True)
                if c["active_sha"] == sha and c["status"] == CONSUMED:
                    self._log(state, "already_admitted", cycle=cid, sha=sha)
                    return dict(c, cycle_id=cid, already_admitted=True)
            for cid, c in cycles.items():
                if parent_sha and c["active_sha"] == parent_sha:
                    if c["status"] == ESCALATED:
                        self._log(state, "blocked_by_escalation", cycle=cid, sha=sha,
                                  parent=parent_sha)
                        return dict(c, cycle_id=cid, blocked_by_escalation=True)
                    if c["status"] in (BLOCKED, OPEN):
                        c["round"] += 1
                        c["active_sha"] = sha
                        c["status"] = OPEN
                        c["awaiting_verdict"] = True
                        self._log(state, "advance", cycle=cid, sha=sha, round=c["round"])
                        return dict(c, cycle_id=cid)
            cid = cycle_id_for(repo, sha)
            c = {"repo": repo, "root_sha": sha, "active_sha": sha, "parent_receipt": "",
                 "round": 1, "status": OPEN, "consumed": [], "awaiting_verdict": True}
            cycles[cid] = c
            self._log(state, "open", cycle=cid, sha=sha)
            return dict(c, cycle_id=cid)

    def continue_cycle(self, cycle_id: str, repo: str, sha: str) -> dict:
        """Advance a named blocked cycle across append-only ledger commits.

        In a local deployment, report and receipt commits sit between two
        generator commits. Direct-parent inference therefore cannot identify a
        build revision. The caller first proves ancestry in the science git
        graph; this locked mutation then preserves the cycle identity.
        """
        with self._locked() as state:
            c = state["cycles"].get(cycle_id)
            if c is None:
                raise IntegrityDenial("unknown continuation cycle", cycle_id=cycle_id)
            if c["repo"] != repo:
                raise IntegrityDenial("continuation cycle belongs to another repository",
                                      cycle_id=cycle_id)
            human_reopened = c["status"] == OPEN and c.get("human_reopened") is True
            if c["status"] != BLOCKED and not human_reopened:
                raise IntegrityDenial(
                    f"cycle is {c['status']}, not BLOCKED or human-reopened; it "
                    f"cannot accept a build revision",
                    cycle_id=cycle_id, status=c["status"])
            if c["active_sha"] == sha:
                raise IntegrityDenial("a build revision must create a new commit",
                                      cycle_id=cycle_id, sha=sha)
            previous = c["active_sha"]
            c["round"] += 1
            c["active_sha"] = sha
            c["status"] = OPEN
            c["awaiting_verdict"] = True
            c.pop("human_reopened", None)
            self._log(state, "continue_build", cycle=cycle_id, sha=sha,
                      parent_active_sha=previous, round=c["round"])
            return dict(c, cycle_id=cycle_id)

    def escalate(self, cycle_id: str, reason: str, *, task: str = "",
                 run_id: str = "") -> dict:
        """Persist a build-level stop so status and Console expose it.

        ``run_id`` links this decision object to the exact journal run whose
        stop it records. Reconciliation heals only the referenced run: an
        escalation is evidence about one stop, never a license to re-narrate
        unrelated interrupted runs as "waiting for a person".
        """
        with self._locked() as state:
            c = state["cycles"].get(cycle_id)
            if c is None:
                raise IntegrityDenial("unknown cycle", cycle_id=cycle_id)
            if c["status"] not in (OPEN, BLOCKED, ESCALATED):
                # Fail-closed against verdict rewriting: a recorded PASS or a
                # consumed admission is ledger, and no supervisor (watchdog,
                # reconciler, retry handler) may flip it into an escalation.
                raise IntegrityDenial(
                    f"cycle is {c['status']}; it cannot be escalated",
                    cycle_id=cycle_id, status=c["status"])
            c["status"] = ESCALATED
            c["awaiting_verdict"] = False
            c["escalation_reason"] = reason
            if run_id:
                c["escalation_run_id"] = run_id[:64]
            if task.strip():
                c["task"] = task.strip()[:12000]
            self._log(state, "escalate", cycle=cycle_id, reason=reason,
                      round=c["round"], run_id=run_id[:64])
            return dict(c, cycle_id=cycle_id)

    def record_build_escalation(self, repo: str, sha: str, reason: str,
                                round_: int, chat_id: str = "",
                                task: str = "", run_id: str = "") -> dict:
        """Persist a build that stopped before any auditable revision existed.

        Provider refusals can consume the whole generator budget before there is
        a generated commit for ``cmd_run`` to open.  That still requires a
        durable, human-resolvable cycle; otherwise the UI says it needs a human
        while exposing no decision object.  The current task/routing commit is
        the immutable anchor and ``chat_id`` keeps the ruling in its UI thread.
        """
        if round_ < 1:
            raise IntegrityDenial("an escalated build must have attempted a round")
        cid = cycle_id_for(repo, sha)
        with self._locked() as state:
            cycles = state["cycles"]
            existing = cycles.get(cid)
            if existing and existing.get("active_sha") != sha:
                raise IntegrityDenial("build escalation cycle has a conflicting sha",
                                      cycle_id=cid)
            if existing and existing.get("status") in (PASSED, CONSUMED):
                # Fail-closed against verdict rewriting: this cycle already
                # carries a recorded PASS (or was consumed by admission). The
                # watchdog's reconciler and any retry path anchor escalations
                # by sha, and without this guard a stale human-wait run could
                # silently flip a passed cycle back into ESCALATED — a
                # supervisor rewriting the ledger's judgment.
                raise IntegrityDenial(
                    f"cycle is {existing['status']}; a recorded verdict cannot "
                    f"be overwritten with an escalation",
                    cycle_id=cid, status=existing["status"])
            c = existing or {
                "repo": repo, "root_sha": sha, "active_sha": sha,
                "parent_receipt": "", "consumed": [],
            }
            c.update(round=round_, status=ESCALATED, awaiting_verdict=False,
                     escalation_reason=reason)
            if run_id:
                # The run this decision object records; reconciliation heals
                # only referenced runs (see escalate()).
                c["escalation_run_id"] = run_id[:64]
            if chat_id:
                c["chat_id"] = chat_id
            if task.strip():
                c["task"] = task.strip()[:12000]
            cycles[cid] = c
            self._log(state, "build_escalated_before_revision", cycle=cid,
                      sha=sha, reason=reason, round=round_, chat_id=chat_id,
                      run_id=run_id[:64])
            return dict(c, cycle_id=cid)

    def record_verdict(self, cycle_id: str, sha: str, verdict: str,
                       receipt_hash: str, max_rounds: int,
                       escalation_reason: str = "") -> str:
        """Record one round's verdict; ``escalation_reason`` names the stop.

        When the round's failure was infrastructural (the model audit could
        not run at all), the caller passes a reason carrying "provider
        failure" so an escalated cycle routes to the provider remedies
        instead of asking a human for content guidance about an outage.
        """
        with self._locked() as state:
            c = state["cycles"].get(cycle_id)
            if c is None:
                raise IntegrityDenial("unknown cycle", cycle_id=cycle_id)
            if c["active_sha"] != sha:
                self._log(state, "stale_verdict_ignored", cycle=cycle_id, sha=sha,
                          verdict=verdict)
                return c["status"]
            if c["status"] == CONSUMED:
                # An admitted cycle is closed; a late verdict cannot reopen it.
                self._log(state, "verdict_after_admission_ignored", cycle=cycle_id, sha=sha)
                return c["status"]
            if verdict == "PASS":
                c["status"] = PASSED
            elif verdict in ("ESCALATE", "DCL_ONLY"):
                c["status"] = ESCALATED
            else:
                c["status"] = ESCALATED if c["round"] >= max_rounds else BLOCKED
            if c["status"] == ESCALATED and escalation_reason.strip():
                c["escalation_reason"] = escalation_reason.strip()[:400]
            c["parent_receipt"] = receipt_hash
            c["awaiting_verdict"] = False
            self._log(state, "verdict", cycle=cycle_id, sha=sha, verdict=verdict,
                      round=c["round"], status=c["status"], receipt=receipt_hash[:16])
            return c["status"]

    def admit(self, cycle_id: str, sha: str, receipt_hash: str) -> None:
        """Consume a receipt, once. Raises IntegrityDenial rather than returning a string.

        Freshness, status, binding and replay are all checked *inside* the lock,
        so two processes cannot both observe an unconsumed receipt.
        """
        with self._locked() as state:
            c = state["cycles"].get(cycle_id)
            if c is None:
                raise IntegrityDenial("unknown cycle", cycle_id=cycle_id)
            if c["status"] != PASSED:
                raise IntegrityDenial(f"cycle status is {c['status']}, not PASSED",
                                      cycle_id=cycle_id, status=c["status"])
            if c["active_sha"] != sha:
                raise IntegrityDenial(
                    f"stale: receipt sha {sha[:12]} is not the cycle's active "
                    f"{c['active_sha'][:12]}", cycle_id=cycle_id)
            if receipt_hash in c["consumed"]:
                raise IntegrityDenial("receipt already consumed (replay)", cycle_id=cycle_id)
            if c["parent_receipt"] != receipt_hash:
                raise IntegrityDenial("receipt is not the cycle's recorded latest receipt",
                                      cycle_id=cycle_id)
            c["consumed"].append(receipt_hash)
            c["status"] = CONSUMED
            self._log(state, "admit", cycle=cycle_id, sha=sha, receipt=receipt_hash[:16])

    def resolve_escalation(self, cycle_id: str, action: str, reason: str) -> dict:
        """The human principal rules on an escalation (I6's other half).

        Escalation hands an increment to a human; this is the verb the human
        answers with. `reopen` returns the increment to the loop for another
        audit round; `close` ends the cycle without admission. Either way the
        decision and its stated reason enter the ledger, because a ruling that
        leaves no record is exactly what this protocol exists to prevent.
        """
        if action not in ("reopen", "close"):
            raise IntegrityDenial(f"unknown resolution {action!r}; use reopen or close")
        if not reason.strip():
            raise IntegrityDenial("a resolution must state its reason; it becomes ledger")
        with self._locked() as state:
            c = state["cycles"].get(cycle_id)
            if c is None:
                raise IntegrityDenial("unknown cycle", cycle_id=cycle_id)
            if c["status"] != ESCALATED:
                raise IntegrityDenial(f"cycle is {c['status']}, not ESCALATED; only an "
                                      f"escalated cycle needs a human ruling")
            if action == "reopen":
                c["status"] = OPEN
                c["awaiting_verdict"] = True
                c["human_reopened"] = True
                # The ruled-on stop is settled; a future escalation will
                # reference the run of the retry, not this one.
                c.pop("escalation_run_id", None)
            else:
                c["status"] = BLOCKED
                c["closed_by_human"] = True
                c.pop("human_reopened", None)
            self._log(state, "human_resolution", cycle=cycle_id, action=action,
                      reason=reason[:400])
            return dict(c, cycle_id=cycle_id)

    # ------------------------------------------------------- self-attestation
    def capabilities(self) -> dict:
        """What this store can actually promise, tested rather than declared.

        The admission tier turns on two properties of the controller, and a
        configuration file claiming them proves nothing. Both are probed here:
        persistence by asking whether the store lives outside any ephemeral
        checkout, and atomicity by exercising the lock this process would rely
        on. A store that cannot demonstrate both never supports enforced
        admission, however it is configured.
        """
        ephemeral_markers = ("/runner/work/", "/home/runner/")
        path = str(self.path)
        try:
            in_system_temp = self.path.is_relative_to(Path(tempfile.gettempdir()).resolve())
        except (OSError, ValueError):
            in_system_temp = False
        persistent = not in_system_temp and not any(
            marker in path.replace("\\", "/") for marker in ephemeral_markers)

        atomic = False
        detail = ""
        try:
            with self._locked() as state:
                state.setdefault("cycles", {})
                # If the lock is real, a second acquisition from this process
                # must fail while we hold it.
                try:
                    fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    os.close(fd)
                    detail = "the lock did not exclude a second holder"
                except FileExistsError:
                    atomic = True
        except Exception as exc:                       # noqa: BLE001
            detail = f"the store could not be locked: {exc}"

        shortfalls = []
        if not persistent:
            shortfalls.append("the store is in a location that does not outlive "
                              "the run that wrote it")
        if detail:
            shortfalls.append(detail)
        return {"path": path, "persistent": persistent, "atomic": atomic,
                "why_not": "; ".join(shortfalls)}

    def mark_deadlettered(self, cycle_id: str, issue_ref: str) -> None:
        with self._locked() as state:
            c = state["cycles"].get(cycle_id)
            if c is not None:
                c["deadlettered"] = issue_ref
                self._log(state, "deadletter", cycle=cycle_id, issue=issue_ref)

    def stuck_cycles(self, max_age_s: int) -> list[dict]:
        state = self._read()
        last: dict[str, int] = {}
        for h in state.get("history", []):
            if "cycle" in h:
                last[h["cycle"]] = h["t"]
        now = int(time.time())
        return [dict(c, cycle_id=cid) for cid, c in state["cycles"].items()
                if c["status"] in (OPEN, BLOCKED) and not c.get("deadlettered")
                and now - last.get(cid, now) > max_age_s]
