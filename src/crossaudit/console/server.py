"""`crossaudit console` — two windows, one input, and the ledger between them.

The generator is the main window, the auditor the side window, and the single
input at the bottom is the black box: you type as you would to any assistant and
the router decides which side hears it. The routing decision is shown where it
happened, because a box whose sorting is invisible is asking for trust it has
not earned.

Opening a port inside a tool that holds API keys is a real attack surface, and
the defences are structural rather than promised:

* **loopback only**, bound to 127.0.0.1.
* **a per-session token on every request, and no cookies at all.** CSRF needs a
  credential the browser attaches for you; there is none to ride.
* **Host pinned to localhost**, which is what turns away DNS rebinding.
* **a strict inline-only CSP**, so nothing on the page can fetch or exfiltrate.
* **one write path, and it is narrow.** `/api/say` accepts an instruction and,
  only after a second explicit confirmation, completed project uploads. Large
  files reach the local inbox through bounded `/api/upload` transport chunks;
  both paths feed the same build loop the CLI uses.
* **keys are reported present or absent, never rendered.**
* **idle shutdown**, so a forgotten port closes itself.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import secrets
import shutil
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

from ..config import Config, load
from .. import app_doctor, app_keys, connections, document_export, hpc, mcp, usage
from ..controller import StateStore
from ..errors import ConfigDenial, Denial
from ..gitio import is_ancestor
from ..receipt.verify import (admit as admit_receipt, load as load_receipt,
                              verify as verify_receipt)
from ..providers import resilience as provider_resilience
from ..router import history as routing_history
from . import chats, daemon, overview, projects
from .page import PAGE
from .progress import TRACKER
from .streams import bundle
from .transfers import (MAX_REQUEST_BYTES, TransferError, decode_attachments,
                        prompt_section, receive_upload_chunk, resolve_artifact,
                        resolve_upload_batch, resolve_uploads, retire_uploads,
                        stage_attachments, preview_artifact)

IDLE_TIMEOUT_S = 900.0
STREAM_POLL_S = 0.1          # fallback for changes made by another local process
STREAM_HEARTBEAT_S = 15.0
MAX_UTTERANCE = 4000
ALLOWED_HOSTS = {"localhost", "127.0.0.1", "[::1]"}


def app_settings(cfg: Config | None = None) -> dict:
    """Non-secret desktop readiness state for the Settings panel."""
    from .. import _selfid

    identity = _selfid.identity()
    app_mode = os.environ.get("CROSSAUDIT_APP_MODE") == "1"
    if cfg is not None and app_mode:
        app_doctor.JOBS.start(cfg, STREAM_CHANGES.notify)
    doctor = (app_doctor.JOBS.snapshot(cfg) if cfg is not None and app_mode else {
        "status": "idle", "summary": "Environment has not been checked",
        "checks": [], "checked_at": 0,
    })
    checked = {row.get("id"): row for row in doctor.get("checks", [])}
    return {
        "app_mode": app_mode,
        "workspace": os.environ.get("CROSSAUDIT_WORKSPACE_ROOT", ""),
        "providers": connections.status(),
        "provider_login": connections.LOGINS.snapshot(),
        "dependencies": {
            "git": (checked.get("git", {}).get("status") == "ready"
                    if "git" in checked else bool(shutil.which("git"))),
            "github_cli": (checked.get("github_cli", {}).get("status") == "ready"
                           if "github_cli" in checked else
                           bool(os.environ.get("CROSSAUDIT_BUNDLED_GH", "") or
                                shutil.which("gh"))),
        },
        "runtime": {
            "install_mode": identity["install_mode"],
            "code_digest": identity["code_digest_sha256"][:12],
        },
        "doctor": doctor,
    }


def admit_latest(cfg: Config, cycle_id: str = "") -> dict:
    """Verify and consume the selected, or newest, recorded PASS."""
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    state = store.snapshot()
    verdicts = [event for event in state.get("history", [])
                if event.get("event") == "verdict"]
    if cycle_id:
        verdicts = [event for event in verdicts
                    if str(event.get("cycle", "")) == cycle_id]
    if verdicts:
        event = verdicts[-1]
        cycle_id = str(event.get("cycle", ""))
        cycle = state.get("cycles", {}).get(cycle_id, {})
        if cycle.get("status") == "PASSED":
            sha = str(cycle.get("active_sha", ""))
            round_ = int(cycle.get("round", 0))
            candidates = sorted((cfg.root / cfg.ledger_dir).glob(
                f"{sha[:12]}-r{round_}*/receipt.json"), reverse=True)
            for path in candidates:
                receipt = load_receipt(path)
                if receipt["cycle"]["cycle_id"] != cycle_id:
                    continue
                evidence = verify_receipt(
                    receipt, science_root=cfg.root, audit_root=cfg.root,
                    expect_repo=cfg.science_repo, expect_sha=sha, cfg=cfg)
                digest = evidence["receipt_digest"]
                recorded = event.get("receipt") == digest[:16]
                latest = cycle.get("parent_receipt") == digest
                if not (evidence["admission_ready"] and recorded and latest):
                    raise ConfigDenial("the selected PASS is not ready for admission")
                result = admit_receipt(receipt, store, evidence, cfg=cfg)
                return {**result, "verified": True, "sha": sha,
                        "receipt": digest[:16]}
            raise ConfigDenial("the selected PASS receipt is missing")
    raise ConfigDenial("there is no unconsumed passing result to admit")


class _ChangeSignal:
    """A versioned wake-up shared by every live SSE connection."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._version = 0

    def current(self) -> int:
        with self._condition:
            return self._version

    def notify(self) -> None:
        with self._condition:
            self._version += 1
            self._condition.notify_all()

    def wait(self, version: int, timeout: float) -> int:
        with self._condition:
            self._condition.wait_for(lambda: self._version != version,
                                     timeout=timeout)
            return self._version


STREAM_CHANGES = _ChangeSignal()
PROGRESS_CHANGES = _ChangeSignal()
MODEL_SWITCH_LOCK = threading.Lock()


class _ConsoleHTTPServer(ThreadingHTTPServer):
    """HTTP server whose idle watcher has the same lifetime as the socket."""

    def __init__(self, *args, **kwargs) -> None:
        self.stop_event = threading.Event()
        self.idle_thread: threading.Thread | None = None
        super().__init__(*args, **kwargs)

    def shutdown(self) -> None:
        self.stop_event.set()
        super().shutdown()

    def server_close(self) -> None:
        self.stop_event.set()
        super().server_close()
        watcher = self.idle_thread
        if watcher and watcher is not threading.current_thread():
            watcher.join(timeout=2)


def _notify_progress() -> None:
    """Wake the main stream and identify the cheap in-memory-only change."""
    PROGRESS_CHANGES.notify()
    STREAM_CHANGES.notify()


TRACKER.subscribe(_notify_progress)
usage.subscribe(STREAM_CHANGES.notify)


def _ordered_cycles(state: dict, commit_chats: dict[str, str] | None = None) -> list[dict]:
    """Project controller cycles oldest first, following recorded event time.

    Cycle IDs are hashes and therefore have no chronological meaning. Keeping
    the newest cycle last is a UI contract: status badges, the simple delivery
    state, and the audit gate card must all describe the same latest task.
    """
    states = state.get("cycles", {})
    updated: dict[str, int] = {}
    for event in state.get("history", []):
        cycle_id = str(event.get("cycle", ""))
        if cycle_id in states:
            updated[cycle_id] = max(updated.get(cycle_id, 0),
                                    int(event.get("t", 0) or 0))
    ordered = sorted(states.items(), key=lambda item: (
        updated.get(item[0], 0), item[0]))
    chat_map = commit_chats or {}
    return [{"id": cid, "status": cycle["status"], "round": cycle["round"],
             "sha": cycle["active_sha"], "updated": updated.get(cid, 0),
             "chat_id": (cycle.get("chat_id") or
                         chat_map.get(cycle["active_sha"], chats.LEGACY_CHAT_ID))}
            for cid, cycle in ordered]


def snapshot(cfg: Config) -> dict:
    from .. import __version__
    from .. import admission as adm
    from ..dcl import contracts as check_contracts
    from .. import skills as skills_mod

    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    controller_state = store.snapshot()
    caps = store.capabilities()
    tier = adm.assess(root=cfg.root, paired=bool(cfg.audit_repo),
                      controller_persistent=caps["persistent"],
                      controller_atomic=caps["atomic"], online=False)
    const = cfg.root / cfg.constitution
    gen_stream, aud_stream, commit_chats = bundle(cfg)
    cycles = _ordered_cycles(controller_state, commit_chats)
    known_chats = {str(row.get("chat_id", ""))
                   for row in (*gen_stream, *aud_stream, *cycles)
                   if row.get("chat_id")}
    chat_state = chats.snapshot(cfg, known_chats)
    progress = TRACKER.snapshot()
    for row in chat_state["items"]:
        related = [cycle for cycle in cycles if cycle["chat_id"] == row["id"]]
        row["cycles"] = len(related)
        row["status"] = ("running" if progress and not progress.get("finished")
                         and progress.get("chat_id") == row["id"] else
                         related[-1]["status"].lower() if related else "ready")
        if related:
            row["updated"] = max(row["updated"], related[-1]["updated"])
    audits = overview.read_cycles(cfg)
    escalation_rows = overview.escalations(cfg)
    cycle_chats = {row["id"]: row["chat_id"] for row in cycles}
    for row in escalation_rows:
        # Older controller records predate the durable chat_id field.  The
        # commit trailer mapping used by the rest of this snapshot still lets
        # the decision prompt appear in the correct conversation.
        row["chat_id"] = row.get("chat_id") or cycle_chats.get(
            row["cycle_id"], chats.LEGACY_CHAT_ID)
    try:
        house = [s.name for s in skills_mod.load(cfg.root)]
    except Denial:
        house = []
    return {
        "version": __version__,
        "project": cfg.science_repo,
        "root": str(cfg.root),
        "rules": const.read_text(encoding="utf-8").count("\n### ") if const.is_file() else 0,
        "skills": house,
        "auditor": (f"{cfg.auditor.vendor} · "
                    f"{cfg.auditor.provider}:{cfg.auditor.model}" +
                    (f" · {cfg.auditor.reasoning_effort}" if
                     cfg.auditor.reasoning_effort else "")),
        "generator": (
            "human"
            if (cfg.generator_vendor or "").lower() == "human"
            else (f"{cfg.generator_vendor or 'unset'} · "
                  f"{cfg.generator_provider or 'unset'}:"
                  f"{cfg.generator_model or 'unset'}" +
                  (f" · {cfg.generator_reasoning_effort}" if
                   cfg.generator_reasoning_effort else ""))
        ),
        "runtime_config": projects.runtime_options(cfg),
        "check_contracts": check_contracts(cfg.checks),
        "max_rounds": cfg.max_rounds,
        # Presence, never the value: a console that can show a key can leak one.
        "key_present": (
            connections.ready("openai", "chatgpt")
            if cfg.auditor.provider == "openai_codex"
            else bool(os.environ.get(cfg.auditor.key_env, "").strip())
        ),
        "cycles": cycles,
        "chats": chat_state,
        "tier": tier.as_dict(),
        # Every figure below is derived from the ledger; where it cannot answer,
        # the answer is absent rather than a confident zero.
        "metrics": overview.metrics(cfg, audits),
        "pipeline": overview.pipeline(cfg, audits),
        "findings": overview.findings_by_severity(audits),
        "top_rules": overview.top_rules(audits),
        "usage": usage.summary(cfg),
        "provider_resilience": provider_resilience.snapshot(cfg),
        # Remote jobs are scheduler-owned or detached on the SSH host.  This
        # snapshot only reattaches the live UI to their persistent identifiers.
        "compute": hpc.MANAGER.snapshot(cfg, STREAM_CHANGES.notify),
        # MCP credentials remain in Keychain; the UI receives only configured
        # server/tool policy and hashed call-ledger metadata.
        "mcp": mcp.MANAGER.snapshot(cfg),
        "escalations": escalation_rows,
        "disputes": overview.disputes(cfg),
        "routing": routing_history(cfg.root / cfg.ledger_dir / "routing.jsonl", 40),
        "generator_stream": gen_stream,
        "auditor_stream": aud_stream,
        # In-flight work, if any. Ephemeral by construction: the ledger is still
        # the record, and this vanishes with the process.
        "progress": progress,
        # A build that was in flight when a previous process ended. The ledger
        # holds the rounds that were committed; only this can say one was cut off.
        "interrupted": daemon.interrupted(cfg),
    }


def start_build(cfg: Config, task: str, *, before_start=None,
                attachments=None, chat_id: str = "",
                continuation_cycle: str = "") -> dict:
    """Run a build in the background so the browser can watch it happen.

    The loop is the same one the CLI runs — the console watches it, it does not
    reimplement it, because a second copy could drift on the only thing that
    matters: when the loop stops.
    """
    import threading

    from ..cli.build import preflight, resolve_task, run_loop

    if continuation_cycle:
        if not re.fullmatch(r"[a-f0-9]{16}", continuation_cycle):
            raise ConfigDenial("the human continuation cycle id is invalid")
        prior = StateStore(cfg.root / cfg.state_dir / "state.json").cycle(
            continuation_cycle)
        if prior is None or prior.get("status") != "OPEN" or not prior.get(
                "human_reopened"):
            raise ConfigDenial(
                "that audit cycle is not waiting for a human-authorized revision")
        if prior.get("chat_id") and prior["chat_id"] != chat_id:
            raise ConfigDenial("the audit cycle belongs to a different chat")
        if not is_ancestor(cfg.root, prior["active_sha"], "HEAD"):
            raise ConfigDenial(
                "the project no longer descends from the cycle being revised")
    preflight(cfg)
    resolved = resolve_task(cfg, task.split())
    staged = stage_attachments(cfg, attachments or [])
    if before_start is not None:
        # The console uses this seam to commit its routing decision before the
        # worker thread can begin making generator/auditor commits.
        before_start(resolved)
    slot = daemon.acquire_workspace_slot(cfg)
    try:
        run = TRACKER.start(resolved, chat_id=chat_id)
    except Exception:
        daemon.release_workspace_slot(slot)
        raise
    if staged:
        TRACKER.step("input", f"{len(staged)} attachment(s) received",
                     ", ".join(item["name"] for item in staged))
    try:
        daemon.mark_build(cfg, resolved, chat_id=chat_id,
                          continuation_cycle=continuation_cycle)
    except Exception:
        daemon.release_workspace_slot(slot)
        raise

    def work() -> None:
        recoverable = False
        try:
            def live_step(actor: str, text: str, detail: str = "") -> None:
                TRACKER.step(actor, text, detail)
                daemon.update_build(cfg, actor, detail or text)

            code = run_loop(cfg, resolved, attachments=prompt_section(staged),
                            on_step=live_step,
                            chat_id=chat_id,
                            continuation_cycle=continuation_cycle)
            TRACKER.finish({0: "passed", 11: "escalated"}.get(code, "blocked"))
        except Denial as exc:
            TRACKER.finish("refused", exc.reason)
            daemon.mark_failed(cfg, "refused", exc.reason)
            recoverable = True
        except Exception as exc:                                  # noqa: BLE001
            TRACKER.finish("failed", f"{type(exc).__name__}: {exc}")
            daemon.mark_failed(cfg, "failed", f"{type(exc).__name__}: {exc}")
            recoverable = True
        finally:
            if not recoverable:
                daemon.unmark_build(cfg)
            daemon.release_workspace_slot(slot)

    threading.Thread(target=work, daemon=True).start()
    return {"started": True, "task": resolved.splitlines()[0][:80],
            "attachments": [{k: v for k, v in item.items() if k != "text"}
                            for item in staged]}


DELIVERY_CHOICES = {
    "focus": {"Balanced coverage", "Technical depth",
              "Everyday use and practical experience",
              "Value and purchase recommendation"},
    "format": {"Markdown (.md)", "Plain text (.txt)", "HTML (.html)",
               "PDF (.pdf)", "Word (.docx)"},
    "tone": {"Editorial and readable", "Technical and precise",
             "Concise and direct", "Persuasive but evidence-led"},
}


def _guided_task(text: str, choices) -> str:
    if not isinstance(choices, dict):
        raise ConfigDenial("delivery choices must be an object")
    mode = str(choices.get("mode", ""))
    if mode == "prompt":
        return text
    if mode != "selected":
        raise ConfigDenial("delivery choice mode must be prompt or selected")
    selected = {}
    for key, allowed in DELIVERY_CHOICES.items():
        value = str(choices.get(key, ""))
        if value not in allowed:
            raise ConfigDenial(f"choose a supported {key}")
        selected[key] = value
    task = (text + "\n\nCONFIRMED DELIVERY REQUIREMENTS\n"
            f"- Focus: {selected['focus']}\n"
            f"- Output format: {selected['format']}\n"
            f"- Tone: {selected['tone']}\n"
            "- Produce exactly one primary deliverable. Do not create supporting "
            "or alternate-format files unless the task or configured audit "
            "contract explicitly requires them.")
    if selected["format"] == "PDF (.pdf)":
        task += document_export.export_instructions("pdf")
    elif selected["format"] == "Word (.docx)":
        task += document_export.export_instructions("docx")
    return task


def say(cfg: Config, text: str, *, attachments=None,
        attachment_consent: bool = False, delivery_choices=None,
        chat_id: str = "", continuation_cycle: str = "") -> dict:
    """Route one sentence and run its lane — the same path `talk` takes.

    The sentence submit is the normal action confirmation. Attachments cross a
    separate trust boundary, so both the browser and this server require an
    additional provider-specific confirmation before their contents may enter
    a generator prompt.
    """
    from .. import router as router_mod
    from ..cli import talk as talk_mod

    prepared = list(attachments or [])
    if prepared and not attachment_consent:
        raise TransferError(
            "attachment contents require explicit consent for transmission to "
            f"the configured generator ({cfg.generator_vendor or 'unknown vendor'})")

    if continuation_cycle:
        routing = router_mod.Routing(
            utterance=text, lane="generator", confidence=1.0,
            reasoning="the owner authorized a correction to an escalated cycle",
            restated=text, t=int(time.time()), addressed_to="generator",
            routing_mode="human_continuation", chat_id=chat_id)
    elif delivery_choices is not None:
        task_text = router_mod.MENTION_RE.sub("", text, count=1).strip()
        routing = router_mod.Routing(
            utterance=text, lane="generator", confidence=1.0,
            reasoning="the owner confirmed delivery choices and started the task",
            restated=_guided_task(task_text, delivery_choices), t=int(time.time()),
            addressed_to="generator", routing_mode="guided", chat_id=chat_id)
    else:
        routing = router_mod.route_addressed(
            text, complete=talk_mod._auditor_complete(cfg),
            context=talk_mod._context(cfg))
        routing.chat_id = chat_id
    if not routing.certain:
        talk_mod._record_routing(cfg, routing, "asked for clarification")
        return {"asked": True, "lane": routing.lane, "confidence": routing.confidence,
                "reasoning": routing.reasoning,
                "clarify": routing.clarify or "Is this about the work, or about the "
                                              "standards it is judged by?"}
    attachments_accepted = False

    def generator_lane() -> str:
        nonlocal attachments_accepted
        if TRACKER.running:
            return ("a build is already running; watch it above, or wait for it "
                    "to finish")
        def record_before_start(resolved: str) -> None:
            nonlocal route_recorded
            talk_mod._record_routing(
                cfg, routing, f"building: {resolved.splitlines()[0][:80]}")
            route_recorded = True

        started = start_build(cfg, routing.restated,
                              before_start=record_before_start,
                              attachments=prepared, chat_id=chat_id,
                              continuation_cycle=continuation_cycle)
        attachments_accepted = bool(started["attachments"])
        suffix = (f"\nattachments: "
                  + ", ".join(item["name"] for item in started["attachments"])) \
            if started["attachments"] else ""
        return f"building: {started['task']}{suffix}"

    route_recorded = False
    if prepared and routing.lane != "generator":
        talk_mod._record_routing(
            cfg, routing, "refused: attachments are accepted only for generator tasks")
        return {"asked": False, "lane": routing.lane,
                "confidence": routing.confidence, "reasoning": routing.reasoning,
                "executed": "refused — attachments are accepted only for generator tasks"}
    lanes = {
        "amendment": lambda: talk_mod.lane_amendment(cfg, routing, assume_yes=True),
        "auditor": lambda: talk_mod.lane_auditor(cfg, routing),
        "query": lambda: talk_mod.lane_query(cfg, routing),
        "generator": generator_lane,
        "dispute": lambda: talk_mod.lane_dispute(cfg, routing),
        "resolve": lambda: talk_mod.lane_resolve(cfg, routing, assume_yes=True),
        "project": lambda: talk_mod.lane_project(cfg, routing),
    }
    try:
        executed = lanes[routing.lane]()
    except Denial as exc:
        if not route_recorded:
            talk_mod._record_routing(cfg, routing, f"denied: {exc.reason}")
        return {"asked": False, "lane": routing.lane, "confidence": routing.confidence,
                "reasoning": routing.reasoning, "executed": f"refused — {exc.reason}"}
    if not route_recorded:
        talk_mod._record_routing(cfg, routing, executed)
    return {"asked": False, "lane": routing.lane, "confidence": routing.confidence,
            "reasoning": routing.reasoning, "executed": executed,
            "attachments_accepted": attachments_accepted}


def make_handler(cfg: Config, token: str, touch) -> type:
    class Handler(BaseHTTPRequestHandler):
        server_version = "crossaudit-console"

        def _drain_rejected_body(self) -> None:
            """Consume a small rejected POST body before closing the socket.

            Windows can convert a close with unread inbound bytes into TCP RST,
            discarding the already-written 403.  The bounded, short-timeout
            drain makes denial observable without allowing an unauthenticated
            client to hold a worker indefinitely or allocate from its claimed
            Content-Length.
            """
            try:
                length = int(self.headers.get("content-length", 0))
            except (TypeError, ValueError):
                return
            if not 0 < length <= 64 * 1024:
                return
            previous = self.connection.gettimeout()
            try:
                self.connection.settimeout(0.25)
                remaining = length
                while remaining:
                    block = self.rfile.read(min(remaining, 16 * 1024))
                    if not block:
                        break
                    remaining -= len(block)
            except (OSError, TimeoutError):
                pass
            finally:
                self.connection.settimeout(previous)

        def _deny(self, code: int, why: str | Denial) -> None:
            structured = isinstance(why, Denial)
            body = (json.dumps(why.as_dict()).encode() if structured
                    else str(why).encode())
            self.send_response(code)
            self.send_header("content-type", ("application/json" if structured
                                                else "text/plain; charset=utf-8"))
            self.send_header("content-length", str(len(body)))
            self.send_header("connection", "close")
            self.send_header("cache-control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()
            self.close_connection = True

        def _send(self, body: bytes, ctype: str) -> None:
            self.send_response(200)
            self.send_header("content-type", ctype)
            self.send_header("content-length", str(len(body)))
            self.send_header("content-security-policy",
                             "default-src 'none'; style-src 'unsafe-inline'; "
                             "script-src 'unsafe-inline'; connect-src 'self'; "
                             "img-src 'self' data:; frame-src 'self'")
            self.send_header("referrer-policy", "no-referrer")
            self.send_header("x-content-type-options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _send_download(self, path, filename: str, size: int, *, inline=False) -> None:
            self.send_response(200)
            ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            self.send_header("content-type", ctype)
            self.send_header("content-length", str(size))
            self.send_header("content-disposition",
                             ("inline" if inline else "attachment")
                             + "; filename*=UTF-8''" + quote(filename))
            self.send_header("cache-control", "no-store")
            self.send_header("x-content-type-options", "nosniff")
            self.send_header("content-security-policy", "default-src 'none'; sandbox")
            self.end_headers()
            try:
                with open(path, "rb") as handle:
                    for block in iter(lambda: handle.read(1024 * 1024), b""):
                        self.wfile.write(block)
            except (BrokenPipeError, ConnectionResetError):
                return

        def _send_remote_download(self, process, filename: str, size: int) -> None:
            """Stream one validated remote output without staging it locally."""
            self.send_response(200)
            self.send_header("content-type", "application/octet-stream")
            self.send_header("content-length", str(size))
            self.send_header("content-disposition",
                             "attachment; filename*=UTF-8''" + quote(filename))
            self.send_header("cache-control", "no-store")
            self.send_header("x-content-type-options", "nosniff")
            self.end_headers()
            try:
                assert process.stdout is not None
                for block in iter(lambda: process.stdout.read(1024 * 1024), b""):
                    self.wfile.write(block)
            except (BrokenPipeError, ConnectionResetError, OSError):
                process.terminate()
            finally:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()

        def _authorised(self, query: dict) -> bool:
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
            if host not in ALLOWED_HOSTS:
                return False           # rebinding arrives with someone else's Host
            return secrets.compare_digest((query.get("t") or [""])[0], token)

        def _config(self) -> Config:
            # Runtime model controls replace crossaudit.yml atomically. Every
            # request takes a fresh immutable snapshot so a long-lived console
            # applies the new choice without a restart.
            return load(cfg.path)

        def do_GET(self) -> None:                                   # noqa: N802
            parsed = urlparse(self.path)
            if not self._authorised(parse_qs(parsed.query)):
                self._deny(403, "forbidden: loopback-only, and the session token "
                                "from the printed URL is required")
                return
            touch()
            if parsed.path == "/":
                self._send(PAGE.encode(), "text/html; charset=utf-8")
            elif parsed.path == "/api/state":
                self._send(json.dumps(snapshot(self._config())).encode(), "application/json")
            elif parsed.path == "/api/stream":
                self._stream(cfg, touch)
            elif parsed.path == "/api/projects":
                self._send(json.dumps(projects.snapshot(self._config())).encode(),
                           "application/json")
            elif parsed.path == "/api/projects/stream":
                self._stream_projects(cfg, touch)
            elif parsed.path == "/api/settings":
                self._send(json.dumps(app_settings(self._config())).encode(),
                           "application/json")
            elif parsed.path == "/api/settings/stream":
                self._stream_settings(touch)
            elif parsed.path == "/api/file":
                query = parse_qs(parsed.query)
                try:
                    path, filename, size = resolve_artifact(
                        self._config(), (query.get("path") or [""])[0])
                except TransferError as exc:
                    self._deny(exc.status, exc.reason)
                    return
                inline_types = (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp")
                inline = ((query.get("view") or [""])[0] == "1"
                          and filename.lower().endswith(inline_types))
                self._send_download(path, filename, size, inline=inline)
            elif parsed.path == "/api/preview":
                try:
                    result = preview_artifact(
                        self._config(), (parse_qs(parsed.query).get("path") or [""])[0])
                except TransferError as exc:
                    self._deny(exc.status, exc.reason)
                    return
                self._send(json.dumps(result).encode(), "application/json")
            elif parsed.path == "/api/hpc/file":
                query = parse_qs(parsed.query)
                try:
                    process, filename, size = hpc.MANAGER.open_output(
                        self._config(), (query.get("job") or [""])[0],
                        (query.get("path") or [""])[0])
                except Denial as exc:
                    self._deny(400, exc)
                    return
                self._send_remote_download(process, filename, size)
            else:
                self._deny(404, "no such page")

        def _stream_projects(self, cfg: Config, touch) -> None:
            projects.RELAYS.ensure(cfg, STREAM_CHANGES.notify)
            self.send_response(200)
            self.send_header("content-type", "text/event-stream; charset=utf-8")
            self.send_header("cache-control", "no-store")
            self.send_header("connection", "close")
            self.send_header("content-security-policy",
                             "default-src 'none'; style-src 'unsafe-inline'; "
                             "script-src 'unsafe-inline'; connect-src 'self'")
            self.end_headers()
            last_digest = ""
            last_beat = time.monotonic()
            change_version = STREAM_CHANGES.current()
            try:
                while True:
                    payload = json.dumps(projects.snapshot(self._config()), sort_keys=True)
                    digest = hashlib.sha256(payload.encode()).hexdigest()
                    now = time.monotonic()
                    if digest != last_digest:
                        self.wfile.write(f"data: {payload}\n\n".encode())
                        self.wfile.flush()
                        last_digest, last_beat = digest, now
                        touch()
                    elif now - last_beat > STREAM_HEARTBEAT_S:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                        last_beat = now
                        touch()
                    change_version = STREAM_CHANGES.wait(change_version, 0.5)
            except (BrokenPipeError, ConnectionResetError, OSError):
                return

        def _stream_settings(self, touch) -> None:
            self.send_response(200)
            self.send_header("content-type", "text/event-stream; charset=utf-8")
            self.send_header("cache-control", "no-store")
            self.send_header("connection", "close")
            self.send_header("content-security-policy",
                             "default-src 'none'; style-src 'unsafe-inline'; "
                             "script-src 'unsafe-inline'; connect-src 'self'")
            self.end_headers()
            last_digest = ""
            last_beat = time.monotonic()
            change_version = STREAM_CHANGES.current()
            try:
                while True:
                    payload = json.dumps(app_settings(self._config()), sort_keys=True)
                    digest = hashlib.sha256(payload.encode()).hexdigest()
                    now = time.monotonic()
                    if digest != last_digest:
                        self.wfile.write(f"data: {payload}\n\n".encode())
                        self.wfile.flush()
                        last_digest, last_beat = digest, now
                        touch()
                    elif now - last_beat > STREAM_HEARTBEAT_S:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                        last_beat = now
                        touch()
                    change_version = STREAM_CHANGES.wait(change_version, 1.0)
            except (BrokenPipeError, ConnectionResetError, OSError):
                return

        def _stream(self, cfg: Config, touch) -> None:
            """Push a snapshot whenever anything changes.

            The server re-derives often and sends rarely: a frame goes out only
            when the digest moves, so an idle project costs one heartbeat every
            fifteen seconds rather than a stream of identical payloads. Each push
            counts as activity, otherwise a browser watching a long build in
            silence would look idle and the console would shut itself down.
            """
            self.send_response(200)
            self.send_header("content-type", "text/event-stream; charset=utf-8")
            self.send_header("cache-control", "no-store")
            self.send_header("connection", "close")
            self.send_header("content-security-policy",
                             "default-src 'none'; style-src 'unsafe-inline'; "
                             "script-src 'unsafe-inline'; connect-src 'self'")
            self.end_headers()
            last_digest = ""
            last_beat = time.monotonic()
            change_version = STREAM_CHANGES.current()
            progress_version = PROGRESS_CHANGES.current()
            last_state = None
            try:
                while True:
                    current_progress_version = PROGRESS_CHANGES.current()
                    if (last_state is not None and
                            current_progress_version != progress_version):
                        # A progress step is already held in memory. Reusing the
                        # last full ledger view keeps the composer/loop response
                        # immediate even when git and filesystem scans are slow;
                        # the 100 ms fallback re-derives the durable state next.
                        state = dict(last_state)
                        state["progress"] = TRACKER.snapshot()
                    else:
                        state = snapshot(self._config())
                    progress_version = current_progress_version
                    last_state = state
                    payload = json.dumps(state, sort_keys=True)
                    digest = hashlib.sha256(payload.encode()).hexdigest()
                    now = time.monotonic()
                    if digest != last_digest:
                        self.wfile.write(f"data: {payload}\n\n".encode())
                        self.wfile.flush()
                        last_digest, last_beat = digest, now
                        touch()
                    elif now - last_beat > STREAM_HEARTBEAT_S:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                        last_beat = now
                        touch()
                    # Progress produced in this process wakes every connection
                    # immediately. The short timeout only catches git/controller
                    # writes made by another local CrossAudit process.
                    change_version = STREAM_CHANGES.wait(change_version,
                                                         STREAM_POLL_S)
            except (BrokenPipeError, ConnectionResetError, OSError):
                return                      # the tab closed; nothing to clean up

        def do_POST(self) -> None:                                  # noqa: N802
            parsed = urlparse(self.path)
            if not self._authorised(parse_qs(parsed.query)):
                self._drain_rejected_body()
                self._deny(403, "forbidden")
                return
            if parsed.path not in {"/api/say", "/api/upload", "/api/projects/create",
                                   "/api/projects/open", "/api/projects/resume",
                                   "/api/projects/pin", "/api/projects/delete",
                                   "/api/chats/new", "/api/chats/pin",
                                   "/api/chats/delete",
                                   "/api/github/connect", "/api/github/check",
                                   "/api/workspace/select", "/api/models/refresh",
                                   "/api/runtime/options", "/api/runtime",
                                   "/api/skills",
                                   "/api/settings", "/api/providers/connect",
                                   "/api/doctor", "/api/hpc", "/api/mcp", "/api/admit",
                                   "/api/escalation", "/api/interrupted"}:
                self._deny(404, "no such action")
                return
            touch()
            try:
                length = int(self.headers.get("content-length", 0))
            except ValueError:
                self._deny(400, "bad length")
                return
            if length > MAX_REQUEST_BYTES:
                self._deny(413, "the task and attachments exceed the request limit")
                return
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(payload, dict):
                    raise ValueError("object required")
                if parsed.path == "/api/upload":
                    result = receive_upload_chunk(self._config(), payload)
                    self._send(json.dumps(result).encode(), "application/json")
                    return
                if parsed.path == "/api/projects/create":
                    result = projects.JOBS.start(self._config(), payload,
                                                 STREAM_CHANGES.notify)
                    self._send(json.dumps(result).encode(), "application/json")
                    return
                if parsed.path == "/api/projects/pin":
                    result = projects.set_project_pin(
                        self._config(), str(payload.get("root", "")),
                        payload.get("pinned") is True)
                    STREAM_CHANGES.notify()
                    self._send(json.dumps(result).encode(), "application/json")
                    return
                if parsed.path == "/api/projects/delete":
                    current = self._config()
                    root = str(payload.get("root", ""))
                    if payload.get("action") == "preview":
                        result = projects.project_deletion_preview(current, root)
                    elif payload.get("action") == "delete":
                        result = projects.delete_project(current, root, payload)
                        STREAM_CHANGES.notify()
                    else:
                        raise ConfigDenial("project delete action must be preview or delete")
                    self._send(json.dumps(result).encode(), "application/json")
                    return
                if parsed.path == "/api/chats/new":
                    result = chats.create(
                        self._config(), str(payload.get("title", "New chat")))
                    STREAM_CHANGES.notify()
                    self._send(json.dumps({"chat": result}).encode(), "application/json")
                    return
                if parsed.path == "/api/chats/pin":
                    result = chats.set_chat_pin(
                        self._config(), str(payload.get("chat_id", "")),
                        payload.get("pinned") is True)
                    STREAM_CHANGES.notify()
                    self._send(json.dumps({"chat": result}).encode(), "application/json")
                    return
                if parsed.path == "/api/chats/delete":
                    current = self._config()
                    chat_id = str(payload.get("chat_id", ""))
                    progress = TRACKER.snapshot()
                    if (TRACKER.running and isinstance(progress, dict) and
                            (progress.get("chat_id") or chats.LEGACY_CHAT_ID) == chat_id):
                        raise ConfigDenial(
                            "that chat has a task running; wait for it to finish before deleting")
                    compute = hpc.MANAGER.snapshot(current)
                    if any((row.get("chat_id") or chats.LEGACY_CHAT_ID) == chat_id and
                           row.get("status") not in hpc.TERMINAL_STATES
                           for row in compute.get("jobs", [])):
                        raise ConfigDenial(
                            "that chat has remote compute running; cancel or finish it first")
                    result = chats.delete(current, chat_id)
                    STREAM_CHANGES.notify()
                    self._send(json.dumps({"chat": result}).encode(),
                               "application/json")
                    return
                if parsed.path == "/api/projects/open":
                    result = projects.open_project(self._config(),
                                                   str(payload.get("root", "")))
                    self._send(json.dumps(result).encode(), "application/json")
                    return
                if parsed.path == "/api/projects/resume":
                    result = projects.JOBS.resume(
                        self._config(), str(payload.get("root", "")), payload,
                        STREAM_CHANGES.notify)
                    self._send(json.dumps(result).encode(), "application/json")
                    return
                if parsed.path == "/api/github/connect":
                    result = projects.GITHUB_AUTH.start(STREAM_CHANGES.notify)
                    self._send(json.dumps(result).encode(), "application/json")
                    return
                if parsed.path == "/api/github/check":
                    result = projects.check_repositories(payload)
                    self._send(json.dumps(result).encode(), "application/json")
                    return
                if parsed.path == "/api/workspace/select":
                    result = projects.select_workspace(
                        self._config(), str(payload.get("path", "")))
                    STREAM_CHANGES.notify()
                    self._send(json.dumps(result).encode(), "application/json")
                    return
                if parsed.path == "/api/models/refresh":
                    result = projects.refresh_models(
                        self._config(), str(payload.get("vendor", "")),
                        str(payload.get("role", "")),
                        str(payload.get("method", "api")),
                        str(payload.get("endpoint", "")))
                    self._send(json.dumps(result).encode(), "application/json")
                    return
                if parsed.path == "/api/runtime/options":
                    result = projects.runtime_options(
                        self._config(), str(payload.get("role", "")),
                        str(payload.get("model", "")), live_capabilities=True)
                    self._send(json.dumps(result).encode(), "application/json")
                    return
                if parsed.path == "/api/runtime":
                    # Fast-path refusal matters to the UI: do not leave this
                    # request waiting behind a multi-minute provider turn just
                    # to explain that switching mid-turn is unsafe.
                    if TRACKER.running:
                        raise ConfigDenial(
                            "A loop is running. Model and effort changes apply between "
                            "provider calls, so wait for this task to finish and save again.",
                            issue="runtime_busy", action="wait")
                    with MODEL_SWITCH_LOCK:
                        if TRACKER.running:
                            raise ConfigDenial(
                                "A loop is running. Model and effort changes apply between "
                                "provider calls, so wait for this task to finish and save again.",
                                issue="runtime_busy", action="wait")
                        result = projects.update_runtime(self._config(), payload)
                        provider_resilience.reset(self._config())
                    STREAM_CHANGES.notify()
                    self._send(json.dumps(result).encode(), "application/json")
                    return
                if parsed.path == "/api/skills":
                    if TRACKER.running:
                        raise ConfigDenial(
                            "A loop is running. Project guidance is captured at the start of "
                            "a provider call, so wait for this task to finish and save again.",
                            issue="runtime_busy", action="wait")
                    with MODEL_SWITCH_LOCK:
                        if TRACKER.running:
                            raise ConfigDenial("A loop started while guidance was being saved. Retry when it finishes.")
                        result = projects.update_skill(self._config(), payload)
                    STREAM_CHANGES.notify()
                    self._send(json.dumps(result).encode(), "application/json")
                    return
                if parsed.path == "/api/settings":
                    if os.environ.get("CROSSAUDIT_APP_MODE") != "1":
                        raise ConfigDenial("Keychain settings are available in the macOS app")
                    app_keys.apply(payload)
                    connections.invalidate()
                    provider_resilience.reset(self._config())
                    STREAM_CHANGES.notify()
                    self._send(json.dumps(app_settings(self._config())).encode(),
                               "application/json")
                    return
                if parsed.path == "/api/doctor":
                    if os.environ.get("CROSSAUDIT_APP_MODE") != "1":
                        raise ConfigDenial("Application Doctor repairs are available in the macOS app")
                    action = str(payload.get("action", "scan"))
                    if action == "scan":
                        result = app_doctor.JOBS.start(
                            self._config(), STREAM_CHANGES.notify, force=True)
                    else:
                        result = app_doctor.JOBS.fix(
                            self._config(), action, payload, STREAM_CHANGES.notify)
                    self._send(json.dumps(result).encode(), "application/json")
                    return
                if parsed.path == "/api/hpc":
                    action = str(payload.get("action", ""))
                    current = self._config()
                    if action == "register":
                        result = hpc.MANAGER.register(current, payload)
                    elif action == "probe":
                        result = hpc.MANAGER.probe(current, str(payload.get("host_id", "")))
                    elif action == "remove":
                        result = hpc.MANAGER.remove(current, str(payload.get("host_id", "")))
                    elif action == "submit":
                        attachments = (resolve_upload_batch(
                            current, payload.get("upload_batch"))
                            if payload.get("upload_batch") else [])
                        try:
                            result = hpc.MANAGER.submit(
                                current, payload, attachments=attachments)
                        finally:
                            retire_uploads(current, attachments)
                    elif action == "refresh":
                        result = {"changed": hpc.MANAGER.refresh(current)}
                    elif action == "logs":
                        result = hpc.MANAGER.logs(current, str(payload.get("job_id", "")))
                    elif action == "outputs":
                        result = {"job_id": str(payload.get("job_id", "")),
                                  "outputs": hpc.MANAGER.outputs(
                                      current, str(payload.get("job_id", "")))}
                    elif action == "cancel":
                        result = hpc.MANAGER.cancel(current, str(payload.get("job_id", "")))
                    else:
                        raise ConfigDenial("unsupported HPC action")
                    STREAM_CHANGES.notify()
                    self._send(json.dumps(result).encode(), "application/json")
                    return
                if parsed.path == "/api/mcp":
                    action = str(payload.get("action", ""))
                    current = self._config()
                    if action == "register":
                        result = mcp.MANAGER.register(current, payload)
                    elif action == "probe":
                        result = mcp.MANAGER.probe(
                            current, str(payload.get("server_id", "")))
                    elif action == "remove":
                        result = mcp.MANAGER.remove(
                            current, str(payload.get("server_id", "")))
                    else:
                        raise ConfigDenial("unsupported MCP action")
                    STREAM_CHANGES.notify()
                    self._send(json.dumps(result).encode(), "application/json")
                    return
                if parsed.path == "/api/providers/connect":
                    if os.environ.get("CROSSAUDIT_APP_MODE") != "1":
                        raise ConfigDenial("provider login is available in the macOS app")
                    result = connections.LOGINS.start(
                        str(payload.get("provider", "")),
                        str(payload.get("method", "")), STREAM_CHANGES.notify)
                    self._send(json.dumps(result).encode(), "application/json")
                    return
                if parsed.path == "/api/admit":
                    result = admit_latest(
                        self._config(), str(payload.get("cycle_id", "")))
                    STREAM_CHANGES.notify()
                    self._send(json.dumps(result).encode(), "application/json")
                    return
                if parsed.path == "/api/escalation":
                    current = self._config()
                    result = StateStore(
                        current.root / current.state_dir / "state.json"
                    ).resolve_escalation(
                        str(payload.get("cycle_id", "")),
                        str(payload.get("action", "")),
                        str(payload.get("reason", "")))
                    STREAM_CHANGES.notify()
                    self._send(json.dumps({
                        "cycle_id": str(payload.get("cycle_id", "")),
                        "status": result["status"],
                        "round": result["round"],
                    }).encode(), "application/json")
                    return
                if parsed.path == "/api/interrupted":
                    current = self._config()
                    interrupted = daemon.interrupted(current)
                    if not interrupted:
                        raise ConfigDenial("there is no interrupted task to recover")
                    action = str(payload.get("action", ""))
                    if action == "retry":
                        result = start_build(
                            current, str(interrupted.get("task", "")),
                            chat_id=str(interrupted.get("chat_id", "")),
                            continuation_cycle=str(
                                interrupted.get("continuation_cycle", "")))
                        result["recovery"] = "restarted_from_last_durable_commit"
                    elif action == "dismiss":
                        daemon.unmark_build(current)
                        result = {"dismissed": True,
                                  "working_tree_preserved": True}
                    else:
                        raise ConfigDenial("interrupted task action must be retry or dismiss")
                    STREAM_CHANGES.notify()
                    self._send(json.dumps(result).encode(), "application/json")
                    return
                text = str(payload.get("text", "")).strip()
                if len(text.encode()) > MAX_UTTERANCE:
                    self._deny(413, "that instruction is longer than this input allows")
                    return
                transfer_kinds = sum(value is not None for value in (
                    payload.get("upload_batch"), payload.get("uploads"),
                    payload.get("attachments")))
                if transfer_kinds > 1:
                    raise TransferError("use one file-transfer method per message")
                if payload.get("upload_batch") is not None:
                    attachments = resolve_upload_batch(self._config(), payload["upload_batch"])
                elif payload.get("uploads") is not None:
                    attachments = resolve_uploads(self._config(), payload.get("uploads"))
                else:
                    attachments = decode_attachments(payload.get("attachments"))
            except TransferError as exc:
                self._deny(exc.status, exc.reason)
                return
            except (json.JSONDecodeError, ValueError):
                self._deny(400, "expected {\"text\": \"...\"}")
                return
            except Denial as exc:
                self._deny(400, exc)
                return
            if not text:
                self._deny(400, "say something")
                return
            try:
                chat = chats.touch(self._config(),
                                   str(payload.get("chat_id", "")), text)
                with MODEL_SWITCH_LOCK:
                    continuation = str(payload.get("continuation_cycle", ""))
                    continuation_args = ({"continuation_cycle": continuation}
                                         if continuation else {})
                    result = say(
                        self._config(), text, attachments=attachments,
                        attachment_consent=payload.get("attachment_consent") is True,
                        delivery_choices=payload.get("delivery_choices"),
                        chat_id=chat["id"], **continuation_args)
                result["chat_id"] = chat["id"]
                STREAM_CHANGES.notify()
            except TransferError as exc:
                self._deny(exc.status, exc.reason)
                return
            except Denial as exc:
                self._deny(400, exc)
                return
            # Routing, amendments, disputes and resolutions change files other
            # than the in-memory progress tracker. Publish those immediately too.
            STREAM_CHANGES.notify()
            self._send(json.dumps(result).encode(), "application/json")

        def log_message(self, *args) -> None:                       # noqa: D102
            pass

    return Handler


def serve(cfg: Config, port: int = 0, *,
          idle_timeout: float = IDLE_TIMEOUT_S,
          register: bool = False) -> tuple[str, ThreadingHTTPServer]:
    """Start the console. Returns (url carrying the session token, server)."""
    token = secrets.token_urlsafe(24)
    last = [time.monotonic()]

    def touch() -> None:
        last[0] = time.monotonic()

    httpd = _ConsoleHTTPServer(("127.0.0.1", port), make_handler(cfg, token, touch))

    def idle_watch() -> None:
        while not httpd.stop_event.wait(5):
            # A closed window must never end a running build: idleness is only
            # grounds for shutting down when there is nothing in flight.
            if TRACKER.running:
                last[0] = time.monotonic()
                continue
            if time.monotonic() - last[0] > idle_timeout:
                httpd.shutdown()
                return

    httpd.idle_thread = threading.Thread(target=idle_watch, daemon=True)
    httpd.idle_thread.start()
    port_in_use = httpd.server_address[1]
    if register:
        # So a later invocation can find this console rather than start a rival.
        daemon.write_run(cfg, pid=os.getpid(), port=port_in_use, token=token)
    return f"http://127.0.0.1:{port_in_use}/?t={token}", httpd
